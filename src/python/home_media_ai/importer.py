import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from .media import Base, Media, MediaType
from .scanner import FileInfo


class MediaImporter:
    def __init__(self, database_uri: str):
        self.engine = create_engine(database_uri)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self._media_types_cache = {}
        self._load_media_types()

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

    def _calculate_file_hash(self, file_path: str, chunk_size: int = 8192) -> str:
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except OSError:
            raise

    def _file_exists_in_db(self, file_path: str, file_hash: str) -> Optional[Media]:
        return self.session.query(Media).filter(
            (Media.file_path == file_path) | (Media.file_hash == file_hash)
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
            file_hash = self._calculate_file_hash(file_info.path)
        except OSError:
            return None, False

        existing_media = self._file_exists_in_db(file_info.path, file_hash)
        if existing_media:
            return existing_media, False  # Already exists

        media_type_id = self._get_media_type_id(file_info.media_type)

        # Extract EXIF data from FileInfo
        exif_data = file_info.exif_data or {}

        media = Media(
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
            return media, True  # Newly created
        except IntegrityError:
            self.session.rollback()
            return self._file_exists_in_db(file_info.path, file_hash), False

    def import_file_pairs(self, file_pairs: Iterator[Tuple[FileInfo, Optional[FileInfo]]],
                         progress_callback=None) -> Dict[str, int]:
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
        for i, file_info in enumerate(files):
            try:
                file_hash = self._calculate_file_hash(file_info.path)

                if self._file_exists_in_db(file_info.path, file_hash):
                    stats['skipped'] += 1
                    continue

                media_type_id = self._get_media_type_id(file_info.media_type)

                # Extract EXIF data from FileInfo
                exif_data = file_info.exif_data or {}

                media = Media(
                    file_path=file_info.path,
                    file_hash=file_hash,
                    file_size=file_info.size,
                    file_ext=file_info.extension,
                    media_type_id=media_type_id,
                    created=file_info.timestamp,
                    is_original=True,
                    exif_data=exif_data,
                    # Extract specific EXIF fields
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

                media_objects.append(media)

                if len(media_objects) >= batch_size:
                    try:
                        self.session.bulk_save_objects(media_objects)
                        self.session.commit()
                        stats['imported'] += len(media_objects)
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
                self.session.bulk_save_objects(media_objects)
                self.session.commit()
                stats['imported'] += len(media_objects)
            except Exception:
                self.session.rollback()
                stats['errors'] += len(media_objects)

        return stats

    def close(self):
        self.session.close()
