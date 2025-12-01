"""Thumbnail generation and management for media files.

This module provides utilities for generating optimized thumbnails with
histogram normalization for uniform appearance during rating workflows.
"""

import logging
from pathlib import Path
from typing import Optional, Union
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from .media import Media
from .io import read_image_as_array, normalize_to_uint8
from .utils import infer_media_type_from_extension

logger = logging.getLogger(__name__)

# Default thumbnail settings
DEFAULT_MAX_DIMENSION = 800
DEFAULT_QUALITY = 85
DEFAULT_SUFFIX = "_thumb"


def generate_thumbnail(
    media: Media,
    session: Session,
    output_dir: Optional[Union[str, Path]] = None,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    quality: int = DEFAULT_QUALITY,
    suffix: str = DEFAULT_SUFFIX,
    normalize_histogram: bool = True,
    use_local_mapping: bool = True
) -> Optional[str]:
    """Generate a thumbnail for a media item with optional histogram normalization.

    Prioritizes JPEG derivatives over RAW originals for faster processing.
    Saves thumbnail in the same directory as the source file.

    Args:
        media: Media object to generate thumbnail for.
        session: Database session for updating media record.
        output_dir: Optional override for output directory. If None, uses same dir as source.
        max_dimension: Maximum dimension (width or height) for thumbnail.
        quality: JPEG quality (1-100).
        suffix: Suffix to append to filename (e.g., "_thumb").
        normalize_histogram: Apply histogram equalization for uniform appearance.
        use_local_mapping: Use local path mapping from config.

    Returns:
        Relative path to generated thumbnail, or None if generation failed.
    """
    try:
        # Find best source: prefer JPEG derivative over RAW original
        source_media = _get_best_source(media, session)
        source_path = Path(source_media.get_full_path(use_local_mapping=use_local_mapping))

        if not source_path.exists():
            logger.error(f"Source file not found: {source_path}")
            return None

        # Determine output path
        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = source_path.parent

        # Create thumbnail filename
        stem = Path(media.filename).stem
        thumb_filename = f"{stem}{suffix}.jpg"
        thumb_path = output_dir / thumb_filename

        # Load and process image
        img_array = read_image_as_array(source_path)
        img_array = normalize_to_uint8(img_array)
        img = Image.fromarray(img_array)

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Apply histogram normalization for uniform appearance
        if normalize_histogram:
            img = _normalize_histogram(img)

        # Resize maintaining aspect ratio
        img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # Save thumbnail
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(thumb_path, 'JPEG', quality=quality, optimize=True)

        # Calculate relative path for database storage
        if media.storage_root and media.directory:
            relative_path = str(Path(media.directory) / thumb_filename)
        else:
            relative_path = thumb_filename

        # Update database
        media.thumbnail_path = relative_path
        session.commit()

        logger.info(f"Generated thumbnail: {thumb_path}")
        return relative_path

    except Exception as e:
        logger.error(f"Failed to generate thumbnail for media {media.id}: {e}")
        session.rollback()
        return None


def _get_best_source(media: Media, session: Session) -> Media:
    """Find the best source for thumbnail generation.

    Prioritizes JPEG derivatives over RAW originals for performance.

    Args:
        media: The media item to find source for.
        session: Database session.

    Returns:
        Best source Media object (derivative or original).
    """
    # If this is already a JPEG, use it
    if media.file_ext.lower() in ('.jpg', '.jpeg'):
        return media

    # If this has derivatives, prefer JPEG derivative
    if media.derivatives:
        for derivative in media.derivatives:
            if derivative.file_ext.lower() in ('.jpg', '.jpeg'):
                return derivative

    # Fall back to the original
    return media


def _normalize_histogram(img: Image.Image) -> Image.Image:
    """Apply adaptive histogram equalization for uniform appearance.

    Uses CLAHE-like approach by equalizing each channel separately
    with limited contrast enhancement to avoid over-saturation.

    Args:
        img: PIL Image in RGB mode.

    Returns:
        Histogram-normalized PIL Image.
    """
    # Convert to LAB color space for better perceptual results
    # We'll use a simpler approach: equalize the luminance channel
    # by converting to YCbCr, equalizing Y, then converting back

    # Simple approach: autocontrast with cutoff
    # This normalizes contrast without over-saturating
    img = ImageOps.autocontrast(img, cutoff=2)

    return img


def generate_missing_thumbnails(
    session: Session,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    quality: int = DEFAULT_QUALITY,
    suffix: str = DEFAULT_SUFFIX,
    normalize_histogram: bool = True,
    limit: Optional[int] = None,
    use_local_mapping: bool = True
) -> tuple[int, int]:
    """Generate thumbnails for all media items that don't have one.

    Args:
        session: Database session.
        max_dimension: Maximum dimension for thumbnails.
        quality: JPEG quality.
        suffix: Thumbnail filename suffix.
        normalize_histogram: Apply histogram normalization.
        limit: Maximum number of thumbnails to generate (None for all).
        use_local_mapping: Use local path mapping from config.

    Returns:
        Tuple of (successful_count, failed_count).
    """
    # Query media without thumbnails (only originals)
    query = session.query(Media).filter(
        Media.thumbnail_path.is_(None),
        Media.is_original == True,
        Media.media_type_id == 1  # Assuming 1 is 'image' type
    )

    if limit:
        query = query.limit(limit)

    media_items = query.all()
    successful = 0
    failed = 0

    for media in media_items:
        result = generate_thumbnail(
            media=media,
            session=session,
            max_dimension=max_dimension,
            quality=quality,
            suffix=suffix,
            normalize_histogram=normalize_histogram,
            use_local_mapping=use_local_mapping
        )
        if result:
            successful += 1
        else:
            failed += 1

    logger.info(f"Generated {successful} thumbnails, {failed} failed")
    return successful, failed


def _generate_thumbnail_worker(args: tuple) -> tuple[int, bool]:
    """Worker function for parallel thumbnail generation.

    Args:
        args: Tuple of (media_id, database_uri, settings_dict)

    Returns:
        Tuple of (media_id, success)
    """
    media_id, database_uri, settings = args

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(database_uri)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            media = session.query(Media).filter(Media.id == media_id).first()
            if not media:
                return media_id, False

            result = generate_thumbnail(
                media=media,
                session=session,
                max_dimension=settings['max_dimension'],
                quality=settings['quality'],
                suffix=settings['suffix'],
                normalize_histogram=settings['normalize_histogram'],
                use_local_mapping=settings['use_local_mapping']
            )
            return media_id, result is not None
        finally:
            session.close()
            engine.dispose()

    except Exception as e:
        logger.error(f"Worker error for media {media_id}: {e}")
        return media_id, False


def generate_missing_thumbnails_parallel(
    session: Session,
    database_uri: str,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    quality: int = DEFAULT_QUALITY,
    suffix: str = DEFAULT_SUFFIX,
    normalize_histogram: bool = True,
    limit: Optional[int] = None,
    use_local_mapping: bool = True,
    workers: Optional[int] = None
) -> tuple[int, int]:
    """Generate thumbnails in parallel using multiple processes.

    Args:
        session: Database session for querying media items.
        database_uri: Database connection string for worker processes.
        max_dimension: Maximum dimension for thumbnails.
        quality: JPEG quality.
        suffix: Thumbnail filename suffix.
        normalize_histogram: Apply histogram normalization.
        limit: Maximum number of thumbnails to generate (None for all).
        use_local_mapping: Use local path mapping from config.
        workers: Number of worker processes (None for CPU count).

    Returns:
        Tuple of (successful_count, failed_count).
    """
    # Query media IDs without thumbnails
    query = session.query(Media.id).filter(
        Media.thumbnail_path.is_(None),
        Media.is_original == True,
        Media.media_type_id == 1
    )

    if limit:
        query = query.limit(limit)

    media_ids = [row[0] for row in query.all()]

    if not media_ids:
        logger.info("No thumbnails to generate")
        return 0, 0

    # Prepare settings dict for workers
    settings = {
        'max_dimension': max_dimension,
        'quality': quality,
        'suffix': suffix,
        'normalize_histogram': normalize_histogram,
        'use_local_mapping': use_local_mapping
    }

    # Prepare worker arguments
    worker_args = [(media_id, database_uri, settings) for media_id in media_ids]

    # Use CPU count if workers not specified
    if workers is None:
        workers = multiprocessing.cpu_count()

    successful = 0
    failed = 0

    logger.info(f"Generating {len(media_ids)} thumbnails with {workers} workers")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_generate_thumbnail_worker, args): args[0] for args in worker_args}

        for future in as_completed(futures):
            media_id = futures[future]
            try:
                _, success = future.result()
                if success:
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Future error for media {media_id}: {e}")
                failed += 1

            # Progress logging
            total_done = successful + failed
            if total_done % 100 == 0:
                logger.info(f"Progress: {total_done}/{len(media_ids)} ({successful} successful, {failed} failed)")

    logger.info(f"Generated {successful} thumbnails, {failed} failed")
    return successful, failed


def _check_thumbnail_worker(args: tuple) -> tuple[int, bool, bool]:
    """Worker function for parallel thumbnail integrity check.

    Args:
        args: Tuple of (media_id, database_uri, use_local_mapping, regenerate)

    Returns:
        Tuple of (media_id, exists, regenerated)
    """
    media_id, database_uri, use_local_mapping, regenerate = args

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from .config import get_path_resolver

        engine = create_engine(database_uri, pool_pre_ping=True, pool_recycle=300)
        Session = sessionmaker(bind=engine)
        session = Session()
        resolver = get_path_resolver()

        try:
            media = session.query(Media).filter(Media.id == media_id).first()
            if not media or not media.thumbnail_path:
                return media_id, False, False

            thumb_path = resolver.resolve_path(
                media.storage_root,
                media.thumbnail_path,
                ""
            )

            if thumb_path.exists():
                return media_id, True, False
            else:
                if regenerate:
                    media.thumbnail_path = None
                    result = generate_thumbnail(
                        media=media,
                        session=session,
                        use_local_mapping=use_local_mapping
                    )
                    return media_id, False, result is not None
                return media_id, False, False
        finally:
            session.close()
            engine.dispose()

    except Exception as e:
        logger.error(f"Worker error checking thumbnail for media {media_id}: {e}")
        return media_id, False, False


def check_thumbnail_integrity(
    session: Session,
    regenerate: bool = True,
    use_local_mapping: bool = True
) -> tuple[int, int, int]:
    """Check that all thumbnail files exist and optionally regenerate missing ones.

    Args:
        session: Database session.
        regenerate: If True, regenerate missing thumbnails.
        use_local_mapping: Use local path mapping from config.

    Returns:
        Tuple of (valid_count, missing_count, regenerated_count).
    """
    from .config import get_path_resolver

    resolver = get_path_resolver()

    # Query media with thumbnail_path set
    media_items = session.query(Media).filter(
        Media.thumbnail_path.is_not(None)
    ).all()

    valid = 0
    missing = 0
    regenerated = 0

    for media in media_items:
        # Resolve thumbnail path
        thumb_path = resolver.resolve_path(
            media.storage_root,
            media.thumbnail_path,
            ""
        )

        if thumb_path.exists():
            valid += 1
        else:
            missing += 1
            if regenerate:
                # Clear thumbnail_path so it gets regenerated
                media.thumbnail_path = None
                result = generate_thumbnail(
                    media=media,
                    session=session,
                    use_local_mapping=use_local_mapping
                )
                if result:
                    regenerated += 1

    session.commit()
    logger.info(f"Thumbnail integrity check: {valid} valid, {missing} missing, {regenerated} regenerated")
    return valid, missing, regenerated


def check_thumbnail_integrity_parallel(
    session: Session,
    database_uri: str,
    regenerate: bool = True,
    use_local_mapping: bool = True,
    workers: Optional[int] = None
) -> tuple[int, int, int]:
    """Check thumbnail integrity in parallel using multiple processes.

    Args:
        session: Database session for querying media items.
        database_uri: Database connection string for worker processes.
        regenerate: If True, regenerate missing thumbnails.
        use_local_mapping: Use local path mapping from config.
        workers: Number of worker processes (None for CPU count).

    Returns:
        Tuple of (valid_count, missing_count, regenerated_count).
    """
    # Query media IDs with thumbnail_path set
    media_ids = [
        row[0] for row in session.query(Media.id).filter(
            Media.thumbnail_path.is_not(None)
        ).all()
    ]

    if not media_ids:
        logger.info("No thumbnails to check")
        return 0, 0, 0

    # Prepare worker arguments
    worker_args = [
        (media_id, database_uri, use_local_mapping, regenerate)
        for media_id in media_ids
    ]

    if workers is None:
        workers = multiprocessing.cpu_count()

    valid = 0
    missing = 0
    regenerated = 0

    logger.info(f"Checking {len(media_ids)} thumbnails with {workers} workers")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_check_thumbnail_worker, args): args[0]
            for args in worker_args
        }

        for future in as_completed(futures):
            media_id = futures[future]
            try:
                _, exists, was_regenerated = future.result()
                if exists:
                    valid += 1
                else:
                    missing += 1
                    if was_regenerated:
                        regenerated += 1
            except Exception as e:
                logger.error(f"Future error for media {media_id}: {e}")
                missing += 1

            # Progress logging
            total_done = valid + missing
            if total_done % 100 == 0:
                logger.info(f"Progress: {total_done}/{len(media_ids)}")

    logger.info(f"Thumbnail integrity check: {valid} valid, {missing} missing, {regenerated} regenerated")
    return valid, missing, regenerated


def get_thumbnail_path(
    media: Media,
    use_local_mapping: bool = True
) -> Optional[Path]:
    """Get the full path to a media item's thumbnail.

    Args:
        media: Media object.
        use_local_mapping: Use local path mapping from config.

    Returns:
        Path to thumbnail file, or None if no thumbnail exists.
    """
    if not media.thumbnail_path:
        return None

    if use_local_mapping:
        from .config import get_path_resolver
        resolver = get_path_resolver()
        return resolver.resolve_path(
            media.storage_root,
            media.thumbnail_path,
            ""
        )
    else:
        if media.storage_root:
            return Path(media.storage_root) / media.thumbnail_path
        return Path(media.thumbnail_path)
