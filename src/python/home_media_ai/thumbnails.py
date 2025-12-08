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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    use_local_mapping: bool = True,
    commit: bool = True
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
        commit: Whether to commit the session after updating (default True).

    Returns:
        Relative path to generated thumbnail, or None if generation failed.
    """
    try:
        # Find best source: prefer JPEG derivative over RAW original
        source_media = _get_best_source(media, session)

        try:
            source_path = Path(source_media.get_full_path(use_local_mapping=use_local_mapping))
        except Exception as e:
            logger.error(f"Failed to resolve path for media {media.id}: {e}")
            return None

        try:
            if not source_path.exists():
                logger.error(f"Source file not found: {source_path}")
                return None
        except OSError as e:
            logger.error(f"Error checking file existence for media {media.id} at {source_path}: {e}")
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
        if commit:
            session.commit()

        # Don't log every successful thumbnail to reduce I/O contention
        return relative_path

    except Exception as e:
        # Get media info before any session operations that might fail
        try:
            media_id = media.id
            media_path = f"{media.storage_root}/{media.directory}/{media.filename}" if media.directory else f"{media.storage_root}/{media.filename}"
        except:
            media_id = "unknown"
            media_path = "unknown"
        logger.error(f"Failed to generate thumbnail for media {media_id} ({media_path}): {e}")
        if commit:
            try:
                session.rollback()
            except:
                pass
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
    use_local_mapping: bool = True,
    commit_interval: int = 100,
    error_log_file: Optional[str] = None
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
        commit_interval: Commit changes every N items to avoid long transactions.
        error_log_file: Optional path to write failed files list (CSV format).

    Returns:
        Tuple of (successful_count, failed_count).
    """
    # Query all media without thumbnails (regardless of original/derivative status)
    query = session.query(Media).filter(
        Media.thumbnail_path.is_(None)
    )

    if limit:
        query = query.limit(limit)

    media_items = query.all()
    successful = 0
    failed = 0
    total = len(media_items)
    failed_files = []  # Track failed files for error log

    # Open error log file if specified
    error_log = None
    if error_log_file:
        error_log = open(error_log_file, 'w', encoding='utf-8')
        error_log.write("media_id,storage_root,directory,filename,full_path,error\n")

    try:
        for idx, media in enumerate(media_items, 1):
            try:
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
                    # Log failed file
                    try:
                        media_path = f"{media.storage_root}/{media.directory}/{media.filename}" if media.directory else f"{media.storage_root}/{media.filename}"
                        failed_files.append({
                            'id': media.id,
                            'storage_root': media.storage_root,
                            'directory': media.directory or '',
                            'filename': media.filename,
                            'path': media_path,
                            'error': 'Failed to generate thumbnail'
                        })
                        if error_log:
                            error_log.write(f'{media.id},"{media.storage_root}","{media.directory or ""}","{media.filename}","{media_path}","Failed to generate thumbnail"\n')
                            error_log.flush()
                    except:
                        pass
            except Exception as e:
                logger.error(f"Unexpected error generating thumbnail for media {media.id}: {e}")
                failed += 1
                # Log failed file
                try:
                    media_path = f"{media.storage_root}/{media.directory}/{media.filename}" if media.directory else f"{media.storage_root}/{media.filename}"
                    failed_files.append({
                        'id': media.id,
                        'storage_root': media.storage_root,
                        'directory': media.directory or '',
                        'filename': media.filename,
                        'path': media_path,
                        'error': str(e)
                    })
                    if error_log:
                        error_log.write(f'{media.id},"{media.storage_root}","{media.directory or ""}","{media.filename}","{media_path}","{str(e)}"\n')
                        error_log.flush()
                except:
                    pass

            # Commit periodically to save progress
            if idx % commit_interval == 0:
                session.commit()
                logger.info(f"Progress: {idx}/{total} processed ({successful} successful, {failed} failed)")

        # Final commit
        session.commit()
        logger.info(f"Generated {successful} thumbnails, {failed} failed")

        if error_log_file and failed > 0:
            logger.info(f"Failed files list written to: {error_log_file}")

        return successful, failed
    finally:
        if error_log:
            error_log.close()


def _process_thumbnail_batch_worker(args: tuple) -> tuple[int, int, list[dict]]:
    """Worker function for multiprocessing - must be picklable (top-level function).

    Args:
        args: Tuple of (media_batch, db_url, settings_dict, worker_id)

    Returns:
        Tuple of (successful_count, failed_count, failed_files_list)
    """
    import os
    import time
    media_batch, db_url, settings, worker_id = args

    # Log PID to verify we're using multiple processes
    logger.info(f"Worker {worker_id} starting in PID {os.getpid()}")

    batch_start = time.time()

    # Create a new session for this process
    engine = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    successful = 0
    failed = 0
    failed_files = []

    try:
        # Batch query all media items with eager loading of derivatives
        query_start = time.time()
        from sqlalchemy.orm import joinedload
        media_ids = [m['id'] for m in media_batch]
        media_objects = session.query(Media).options(
            joinedload(Media.derivatives)
        ).filter(Media.id.in_(media_ids)).all()
        query_time = time.time() - query_start

        # Create a lookup dict
        media_lookup = {m.id: m for m in media_objects}

        processing_start = time.time()

        for media_dict in media_batch:
            try:
                media = media_lookup.get(media_dict['id'])
                if not media:
                    # Don't log per-item warnings to reduce I/O
                    failed += 1
                    continue

                # Skip if thumbnail already exists
                if media.thumbnail_path:
                    continue

                result = generate_thumbnail(
                    media=media,
                    session=session,
                    max_dimension=settings['max_dimension'],
                    quality=settings['quality'],
                    suffix=settings['suffix'],
                    normalize_histogram=settings['normalize_histogram'],
                    use_local_mapping=settings['use_local_mapping']
                )

                if result:
                    successful += 1
                else:
                    failed += 1
                    media_path = f"{media.storage_root}/{media.directory}/{media.filename}" if media.directory else f"{media.storage_root}/{media.filename}"
                    failed_files.append({
                        'id': media.id,
                        'storage_root': media.storage_root,
                        'directory': media.directory or '',
                        'filename': media.filename,
                        'path': media_path,
                        'error': 'Failed to generate thumbnail'
                    })

            except Exception as e:
                # Only log errors, not every failure, to reduce I/O
                failed += 1
                try:
                    media_path = f"{media_dict['storage_root']}/{media_dict['directory']}/{media_dict['filename']}" if media_dict['directory'] else f"{media_dict['storage_root']}/{media_dict['filename']}"
                    failed_files.append({
                        'id': media_dict['id'],
                        'storage_root': media_dict['storage_root'],
                        'directory': media_dict.get('directory', ''),
                        'filename': media_dict['filename'],
                        'path': media_path,
                        'error': str(e)
                    })
                except:
                    pass

        # Commit all changes for this batch
        commit_start = time.time()
        session.commit()
        commit_time = time.time() - commit_start

        processing_time = time.time() - processing_start
        total_time = time.time() - batch_start

        logger.info(f"Worker {worker_id}: Completed batch - {successful} successful, {failed} failed | "
                   f"Query: {query_time:.2f}s, Processing: {processing_time:.2f}s, Commit: {commit_time:.2f}s, Total: {total_time:.2f}s")

    finally:
        session.close()
        engine.dispose()

    return successful, failed, failed_files


def _process_thumbnail_batch(
    media_batch: list[dict],
    db_url: str,
    max_dimension: int,
    quality: int,
    suffix: str,
    normalize_histogram: bool,
    use_local_mapping: bool,
    thread_id: int
) -> tuple[int, int, list[dict]]:
    """Process a batch of thumbnails in a worker thread.

    Args:
        media_batch: List of media item dicts with id, storage_root, directory, filename
        db_url: Database connection URL
        max_dimension: Maximum dimension for thumbnails
        quality: JPEG quality
        suffix: Thumbnail filename suffix
        normalize_histogram: Apply histogram normalization
        use_local_mapping: Use local path mapping from config
        thread_id: Thread identifier for logging

    Returns:
        Tuple of (successful_count, failed_count, failed_files_list)
    """
    # Create a new session for this thread
    engine = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    successful = 0
    failed = 0
    failed_files = []

    try:
        for media_dict in media_batch:
            try:
                # Fetch the media object
                media = session.query(Media).filter(Media.id == media_dict['id']).first()
                if not media:
                    logger.warning(f"Thread {thread_id}: Media {media_dict['id']} not found")
                    failed += 1
                    continue

                # Skip if thumbnail already exists (might have been processed by another thread)
                if media.thumbnail_path:
                    continue

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
                    media_path = f"{media.storage_root}/{media.directory}/{media.filename}" if media.directory else f"{media.storage_root}/{media.filename}"
                    failed_files.append({
                        'id': media.id,
                        'storage_root': media.storage_root,
                        'directory': media.directory or '',
                        'filename': media.filename,
                        'path': media_path,
                        'error': 'Failed to generate thumbnail'
                    })

            except Exception as e:
                logger.error(f"Thread {thread_id}: Error processing media {media_dict['id']}: {e}")
                failed += 1
                try:
                    media_path = f"{media_dict['storage_root']}/{media_dict['directory']}/{media_dict['filename']}" if media_dict['directory'] else f"{media_dict['storage_root']}/{media_dict['filename']}"
                    failed_files.append({
                        'id': media_dict['id'],
                        'storage_root': media_dict['storage_root'],
                        'directory': media_dict.get('directory', ''),
                        'filename': media_dict['filename'],
                        'path': media_path,
                        'error': str(e)
                    })
                except:
                    pass

        # Commit all changes for this batch
        session.commit()
        logger.info(f"Thread {thread_id}: Completed batch - {successful} successful, {failed} failed")

    finally:
        session.close()
        engine.dispose()

    return successful, failed, failed_files


def generate_missing_thumbnails_parallel(
    session: Session,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    quality: int = DEFAULT_QUALITY,
    suffix: str = DEFAULT_SUFFIX,
    normalize_histogram: bool = True,
    limit: Optional[int] = None,
    use_local_mapping: bool = True,
    num_threads: int = 4,
    batch_size: int = 100,
    error_log_file: Optional[str] = None
) -> tuple[int, int]:
    """Generate thumbnails in parallel using multiple threads.

    Args:
        session: Database session (used only for initial query)
        max_dimension: Maximum dimension for thumbnails
        quality: JPEG quality
        suffix: Thumbnail filename suffix
        normalize_histogram: Apply histogram normalization
        limit: Maximum number of thumbnails to generate (None for all)
        use_local_mapping: Use local path mapping from config
        num_threads: Number of worker threads (default 4 for Windows)
        batch_size: Number of items per batch per thread
        error_log_file: Optional path to write failed files list (CSV format)

    Returns:
        Tuple of (successful_count, failed_count)
    """
    # Get database URL from the session (with credentials)
    db_url = session.bind.url.render_as_string(hide_password=False)

    # Query all media without thumbnails - just get IDs and basic info
    query = session.query(
        Media.id,
        Media.storage_root,
        Media.directory,
        Media.filename
    ).filter(Media.thumbnail_path.is_(None))

    if limit:
        query = query.limit(limit)

    media_items = query.all()
    total = len(media_items)
    logger.info(f"Found {total} media items without thumbnails")

    if total == 0:
        return 0, 0

    # Convert to list of dicts for thread workers
    media_list = [
        {
            'id': m.id,
            'storage_root': m.storage_root,
            'directory': m.directory,
            'filename': m.filename
        }
        for m in media_items
    ]

    # Split into batches
    batches = []
    for i in range(0, len(media_list), batch_size):
        batches.append(media_list[i:i + batch_size])

    logger.info(f"Split into {len(batches)} batches of ~{batch_size} items each")
    logger.info(f"Using {num_threads} worker processes")

    # Prepare settings dict
    settings = {
        'max_dimension': max_dimension,
        'quality': quality,
        'suffix': suffix,
        'normalize_histogram': normalize_histogram,
        'use_local_mapping': use_local_mapping
    }

    # Prepare worker arguments
    worker_args = [(batch, db_url, settings, idx) for idx, batch in enumerate(batches)]

    # Open error log file if specified
    error_log = None
    if error_log_file:
        error_log = open(error_log_file, 'w', encoding='utf-8')
        error_log.write("media_id,storage_root,directory,filename,full_path,error\n")

    successful = 0
    failed = 0

    try:
        # Process batches in parallel using multiprocessing
        with ProcessPoolExecutor(max_workers=num_threads) as executor:
            futures = {}
            for args in worker_args:
                future = executor.submit(_process_thumbnail_batch_worker, args)
                futures[future] = args[3]  # worker_id

            # Collect results as they complete
            completed = 0
            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_success, batch_failed, batch_failed_files = future.result()
                    successful += batch_success
                    failed += batch_failed
                    completed += 1

                    # Write failed files to error log
                    if error_log and batch_failed_files:
                        for ff in batch_failed_files:
                            error_log.write(
                                f'{ff["id"]},"{ff["storage_root"]}","{ff["directory"]}","{ff["filename"]}","{ff["path"]}","{ff["error"]}"\n'
                            )
                        error_log.flush()

                    logger.info(f"Progress: {completed}/{len(batches)} batches completed ({successful} successful, {failed} failed)")

                except Exception as e:
                    logger.error(f"Batch {batch_idx} failed with error: {e}")
                    failed += len(batches[batch_idx])

        logger.info(f"All batches completed: {successful} thumbnails generated, {failed} failed")

        if error_log_file and failed > 0:
            logger.info(f"Failed files list written to: {error_log_file}")

        return successful, failed

    finally:
        if error_log:
            error_log.close()


def _check_thumbnail_worker(args: tuple) -> tuple[int, bool, bool]:
    """Worker function for parallel thumbnail integrity check.

    Args:
        args: Tuple of (media_id, database_uri, use_local_mapping, regenerate)

    Returns:
        Tuple of (media_id, exists, regenerated)
    """
    media_id, database_uri, use_local_mapping, regenerate = args

    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy.exc import OperationalError
            from .config import get_path_resolver
            import time

            # More conservative connection pool settings to avoid port exhaustion
            engine = create_engine(
                database_uri,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=2,  # Smaller pool per worker
                max_overflow=0,  # No overflow connections
                pool_timeout=30
            )
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

        except OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Connection error for media {media_id} (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            else:
                logger.error(f"Failed to process media {media_id} after {max_retries} attempts: {e}")
                return media_id, False, False
        except Exception as e:
            logger.error(f"Worker error checking thumbnail for media {media_id}: {e}")
            return media_id, False, False

    return media_id, False, False


def check_thumbnail_integrity(
    session: Session,
    regenerate: bool = True,
    use_local_mapping: bool = True,
    commit_interval: int = 100
) -> tuple[int, int, int]:
    """Check that all thumbnail files exist and optionally regenerate missing ones.

    Args:
        session: Database session.
        regenerate: If True, regenerate missing thumbnails.
        use_local_mapping: Use local path mapping from config.
        commit_interval: Commit changes every N items to avoid long transactions.

    Returns:
        Tuple of (valid_count, missing_count, regenerated_count).
    """
    from .config import get_path_resolver
    from sqlalchemy.exc import OperationalError, InterfaceError

    resolver = get_path_resolver()

    # Query media with thumbnail_path set
    media_items = session.query(Media).filter(
        Media.thumbnail_path.is_not(None)
    ).all()

    valid = 0
    missing = 0
    regenerated = 0
    processed = 0

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
                    use_local_mapping=use_local_mapping,
                    commit=False  # Let check_thumbnail_integrity handle commits
                )
                if result:
                    regenerated += 1

        processed += 1

        # Commit periodically to avoid long transactions and connection timeouts
        if processed % commit_interval == 0:
            try:
                session.commit()
                logger.info(f"Progress: {processed}/{len(media_items)} ({valid} valid, {missing} missing, {regenerated} regenerated)")
            except (OperationalError, InterfaceError) as e:
                logger.error(f"Database error during commit at item {processed}: {e}")
                session.rollback()
                # Try to reconnect
                try:
                    session.commit()
                except Exception as retry_error:
                    logger.error(f"Retry failed: {retry_error}")
                    raise

    # Final commit for any remaining items
    try:
        session.commit()
    except (OperationalError, InterfaceError) as e:
        logger.error(f"Database error during final commit: {e}")
        session.rollback()
        raise

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

    # Submit tasks in batches to avoid overwhelming connection pool
    batch_size = workers * 10  # Keep queue reasonable
    import time

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {}
        submitted = 0

        # Submit initial batch
        for args in worker_args[:batch_size]:
            future = executor.submit(_check_thumbnail_worker, args)
            futures[future] = args[0]
            submitted += 1

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

            # Submit next task if available
            if submitted < len(worker_args):
                args = worker_args[submitted]
                new_future = executor.submit(_check_thumbnail_worker, args)
                futures[new_future] = args[0]
                submitted += 1

                # Small delay every N submissions to reduce port churn on Windows
                if submitted % (workers * 2) == 0:
                    time.sleep(0.1)

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
