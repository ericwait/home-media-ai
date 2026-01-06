from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple, TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from .media import Media, MediaType
from .utils import calculate_file_hash, split_file_path

if TYPE_CHECKING:
    from .scanner import FileInfo


class MediaImporter:
    def __init__(self, database_uri: str, storage_root: Optional[str] = None, use_config: bool = True,
                 generate_thumbnails: bool = False):
        """Initialize MediaImporter.

        Args:
            database_uri: Database connection string
            storage_root: The root path where media is stored (e.g., '/volume1/photos').
                         If provided, file paths will be split into storage_root/directory/filename.
                         If None, will try to load from config.
            use_config: Whether to load configuration from config.yaml for storage_root.
                       If True and storage_root is None, will use config.scanning.storage_root.
            generate_thumbnails: Whether to generate thumbnails during import.
        """
        self.engine = create_engine(database_uri)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.generate_thumbnails = generate_thumbnails

        # Determine storage root
        if storage_root:
            self.storage_root = storage_root
        elif use_config:
            try:
                from .config import get_path_resolver
                resolver = get_path_resolver()
                self.storage_root = resolver.get_storage_root_for_import()
            except (ImportError, ValueError):
                # Config not available or not configured
                self.storage_root = None
        else:
            self.storage_root = None

        self._media_types_cache = {}
        self._load_media_types()

    def _generate_thumbnail_for_media(self, media: Media) -> None:
        """Generate thumbnail for a media item if enabled.

        Args:
            media: The Media object to generate thumbnail for.
        """
        if not self.generate_thumbnails:
            return

        # Only generate for image originals
        if not media.is_original or media.media_type_id != self._media_types_cache.get('image', 1):
            return

        try:
            from .thumbnails import generate_thumbnail
            generate_thumbnail(media, self.session)
        except Exception as e:
            # Log but don't fail import on thumbnail errors
            import logging
            logging.getLogger(__name__).warning(f"Failed to generate thumbnail for {media.filename}: {e}")

    def _load_media_types(self):
        for media_type in self.session.query(MediaType).all():
            self._media_types_cache[media_type.name] = media_type.id

    def _get_media_type_id(self, media_type_name: str) -> int:
        if media_type_name not in self._media_types_cache:
            media_type = MediaType(name=media_type_name)
            self.session.add(media_type)
            self.session.flush()
            self._media_types_cache[media_type_name] = media_type.id
        return self._media_types_cache[media_type_name]


    def _file_exists_in_db(self, file_hash: str, filename: str) -> Optional[Media]:
        """Check if file exists by hash or filename.

        Args:
            file_hash: SHA-256 hash of the file
            filename: Name of the file

        Returns:
            Media object if found, None otherwise
        """
        return self.session.query(Media).filter(
            (Media.file_hash == file_hash) | (Media.filename == filename)
        ).first()

    def import_file(self, file_info: FileInfo, origin_id: Optional[int] = None) -> Tuple[Optional[Media], bool]:
        """Import a file into the database.

        Args:
            file_info: File information including path and metadata
            origin_id: ID of the original file if this is a derivative

        Returns:
            Tuple of (Media object or None, was_created boolean)
            was_created is True if the file was newly imported, False if it already existed
        """
        try:
            file_hash = calculate_file_hash(file_info.path)
        except OSError as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to calculate hash for {file_info.path}: {e}")
            return None, False

        # Split the file path into components
        storage_root, directory, filename = split_file_path(file_info.path, self.storage_root)

        if existing_media := self._file_exists_in_db(file_hash, filename):
            return existing_media, False  # Already exists

        media_type_id = self._get_media_type_id(file_info.media_type)

        # Extract EXIF data from FileInfo
        exif_data = file_info.exif_data or {}

        media = Media(
            storage_root=storage_root,
            directory=directory,
            filename=filename,
            file_path=file_info.path,
            file_hash=file_hash,
            file_size=file_info.size,
            file_ext=file_info.extension,
            media_type_id=media_type_id,
            created=file_info.timestamp,
            is_original=origin_id is None,
            origin_id=origin_id,
            exif_data=exif_data,
            # Extract specific EXIF fields into dedicated columns
            gps_latitude=exif_data.get('gps_latitude'),
            gps_longitude=exif_data.get('gps_longitude'),
            gps_altitude=exif_data.get('gps_altitude'),
            camera_make=exif_data.get('camera_make'),
            camera_model=exif_data.get('camera_model'),
            lens_model=exif_data.get('lens_model'),
            width=exif_data.get('width'),
            height=exif_data.get('height'),
            rating=exif_data.get('rating')
        )

        try:
            self.session.add(media)
            self.session.flush()
            # Generate thumbnail for newly imported media
            self._generate_thumbnail_for_media(media)
            return media, True  # Newly created
        except IntegrityError as e:
            import logging
            logging.getLogger(__name__).error(f"IntegrityError for {filename}: {e}")
            self.session.rollback()
            return self._file_exists_in_db(file_hash, filename), False

    def import_file_pairs(self, file_pairs: Iterator[Tuple[FileInfo, Optional[FileInfo]]], progress_callback=None) -> Dict[str, int]:
        stats = {'imported': 0, 'skipped': 0, 'errors': 0}
        batch_size = 100
        processed = 0

        for original_file, derivative_file in file_pairs:
            try:
                # Import original file
                original_media, was_created = self.import_file(original_file)

                if original_media is None:
                    stats['errors'] += 1
                    continue

                # Track original stats
                if was_created:
                    stats['imported'] += 1
                else:
                    stats['skipped'] += 1

                # Import derivative if it exists
                if derivative_file:
                    derivative_media, deriv_was_created = self.import_file(
                        derivative_file,
                        origin_id=original_media.id
                    )
                    if derivative_media:
                        if deriv_was_created:
                            stats['imported'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        stats['errors'] += 1

                processed += 1
                if processed % batch_size == 0:
                    self.session.commit()
                    if progress_callback:
                        progress_callback(f"Processed {processed} pairs: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")

            except Exception as e:
                stats['errors'] += 1
                self.session.rollback()
                if progress_callback:
                    progress_callback(f"Error processing {original_file.path}: {e}")

        # Final commit
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()

        return stats

    def bulk_import_files(self, files: List[FileInfo], progress_callback=None) -> Dict[str, int]:
        stats = {'imported': 0, 'skipped': 0, 'errors': 0}
        batch_size = 100

        media_objects = []
        for file_info in files:
            try:
                file_hash = calculate_file_hash(file_info.path)

                # Split the file path into components
                storage_root, directory, filename = split_file_path(file_info.path, self.storage_root)

                if self._file_exists_in_db(file_hash, filename):
                    stats['skipped'] += 1
                    continue

                media_type_id = self._get_media_type_id(file_info.media_type)

                # Extract EXIF data from FileInfo
                exif_data = file_info.exif_data or {}

                media = Media(
                    storage_root  = storage_root,
                    directory     = directory,
                    filename      = filename,
                    file_path     = file_info.path,
                    file_hash     = file_hash,
                    file_size     = file_info.size,
                    file_ext      = file_info.extension,
                    media_type_id = media_type_id,
                    created       = file_info.timestamp,
                    is_original   = True,
                    exif_data     = exif_data,
                      # Extract specific EXIF fields
                    gps_latitude  = exif_data.get('gps_latitude'),
                    gps_longitude = exif_data.get('gps_longitude'),
                    gps_altitude  = exif_data.get('gps_altitude'),
                    camera_make   = exif_data.get('camera_make'),
                    camera_model  = exif_data.get('camera_model'),
                    lens_model    = exif_data.get('lens_model'),
                    width         = exif_data.get('width'),
                    height        = exif_data.get('height'),
                    rating        = exif_data.get('rating')
                )

                media_objects.append(media)

                if len(media_objects) >= batch_size:
                    try:
                        self._bulk_save_objects(media_objects, stats)
                        media_objects = []

                        if progress_callback:
                            progress_callback(f"Imported {stats['imported']} files, skipped {stats['skipped']}")
                    except Exception:
                        self.session.rollback()
                        stats['errors'] += len(media_objects)
                        media_objects = []

            except Exception:
                stats['errors'] += 1

        # Process remaining objects
        if media_objects:
            try:
                self._bulk_save_objects(media_objects, stats)
            except Exception:
                self.session.rollback()
                stats['errors'] += len(media_objects)

        return stats

    # TODO Rename this here and in `bulk_import_files`
    def _bulk_save_objects(self, media_objects, stats):
        self.session.bulk_save_objects(media_objects)
        self.session.commit()
        stats['imported'] += len(media_objects)

    def close(self):
        self.session.close()
