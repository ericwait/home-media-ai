"""Rating synchronization between database and file metadata.

This module provides utilities for writing ratings to EXIF metadata
and XMP sidecar files, keeping them in sync with database values.
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from sqlalchemy.orm import Session

from .media import Media

logger = logging.getLogger(__name__)

# XMP namespace definitions
XMP_NAMESPACES = {
    'x': 'adobe:ns:meta/',
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
    'xmpRights': 'http://ns.adobe.com/xap/1.0/rights/',
}

# Register namespaces for ElementTree
for prefix, uri in XMP_NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def sync_rating_to_file(
    media: Media,
    rating: int,
    session: Session,
    use_local_mapping: bool = True,
    file_path: Optional[Path] = None
) -> bool:
    """Sync rating to both database and file metadata.

    Updates the rating in the database and writes it to:
    - EXIF metadata for JPEG/TIFF files
    - XMP sidecar file for RAW files

    Args:
        media: Media object to update.
        rating: Rating value (0-5, where 0 means unrated).
        session: Database session.
        use_local_mapping: Use local path mapping from config (ignored if file_path provided).
        file_path: Optional pre-resolved file path. If provided, uses this instead of
                  calling media.get_full_path().

    Returns:
        True if sync was successful, False otherwise.
    """
    if not 0 <= rating <= 5:
        logger.error(f"Invalid rating value: {rating}. Must be 0-5.")
        return False

    try:
        # Update database first
        media.rating = rating
        session.commit()

        # Get file path
        if file_path is None:
            file_path = Path(media.get_full_path(use_local_mapping=use_local_mapping))
        else:
            file_path = Path(file_path)

        if not file_path.exists():
            logger.warning(f"File not found for rating sync: {file_path}")
            return True  # DB updated successfully, file just not found

        # Determine sync method based on file type
        ext = media.file_ext.lower()

        if ext in ('.jpg', '.jpeg', '.tiff', '.tif'):
            # Write to EXIF
            success = _write_rating_to_exif(file_path, rating)
        else:
            # Write to XMP sidecar
            success = _write_rating_to_xmp_sidecar(file_path, rating)

        if success:
            logger.info(f"Synced rating {rating} to file: {file_path.name}")
        else:
            logger.warning(f"Failed to write rating to file: {file_path.name}")

        return success

    except Exception as e:
        logger.error(f"Failed to sync rating for media {media.id}: {e}")
        session.rollback()
        return False


def _write_rating_to_exif(file_path: Path, rating: int) -> bool:
    """Write rating to EXIF metadata in JPEG/TIFF file.

    Uses piexif to update the XMP rating in the EXIF data.

    Args:
        file_path: Path to the image file.
        rating: Rating value (0-5).

    Returns:
        True if successful, False otherwise.
    """
    try:
        import piexif
        from PIL import Image

        # Load existing EXIF data
        try:
            exif_dict = piexif.load(str(file_path))
        except Exception:
            exif_dict = {'0th': {}, '1st': {}, 'Exif': {}, 'GPS': {}, 'Interop': {}}

        # Rating is stored in the 0th IFD with tag 18246 (Rating)
        # Also commonly stored in XMP as xmp:Rating
        RATING_TAG = 18246  # Microsoft Rating tag

        if rating == 0:
            # Remove rating if set to 0 (unrated)
            if RATING_TAG in exif_dict['0th']:
                del exif_dict['0th'][RATING_TAG]
        else:
            exif_dict['0th'][RATING_TAG] = rating

        # Convert back to bytes and save
        exif_bytes = piexif.dump(exif_dict)

        # Re-save image with updated EXIF
        img = Image.open(file_path)
        img.save(str(file_path), exif=exif_bytes, quality='keep')

        return True

    except ImportError:
        logger.warning("piexif not installed, cannot write EXIF rating")
        return False
    except Exception as e:
        logger.error(f"Failed to write EXIF rating: {e}")
        return False


def _write_rating_to_xmp_sidecar(file_path: Path, rating: int) -> bool:
    """Write rating to XMP sidecar file.

    Creates or updates an XMP sidecar file with the rating.

    Args:
        file_path: Path to the original media file.
        rating: Rating value (0-5).

    Returns:
        True if successful, False otherwise.
    """
    try:
        # XMP sidecar path (same name, .xmp extension)
        xmp_path = file_path.with_suffix('.xmp')

        if xmp_path.exists():
            # Update existing XMP file
            tree = ET.parse(xmp_path)
            root = tree.getroot()
        else:
            # Create new XMP file
            root = _create_xmp_template()

        # Find or create the RDF Description element
        rdf_ns = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
        xmp_ns = '{http://ns.adobe.com/xap/1.0/}'

        rdf = root.find(f'.//{rdf_ns}RDF')
        if rdf is None:
            rdf = ET.SubElement(root, f'{rdf_ns}RDF')

        desc = rdf.find(f'{rdf_ns}Description')
        if desc is None:
            desc = ET.SubElement(rdf, f'{rdf_ns}Description')
            desc.set(f'{rdf_ns}about', '')

        # Set the rating
        if rating == 0:
            # Remove rating element if set to 0
            rating_elem = desc.find(f'{xmp_ns}Rating')
            if rating_elem is not None:
                desc.remove(rating_elem)
        else:
            rating_elem = desc.find(f'{xmp_ns}Rating')
            if rating_elem is None:
                rating_elem = ET.SubElement(desc, f'{xmp_ns}Rating')
            rating_elem.text = str(rating)

        # Update modification date
        modify_elem = desc.find(f'{xmp_ns}ModifyDate')
        if modify_elem is None:
            modify_elem = ET.SubElement(desc, f'{xmp_ns}ModifyDate')
        modify_elem.text = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        # Write XMP file
        tree = ET.ElementTree(root)
        tree.write(xmp_path, encoding='utf-8', xml_declaration=True)

        return True

    except Exception as e:
        logger.error(f"Failed to write XMP sidecar: {e}")
        return False


def _create_xmp_template() -> ET.Element:
    """Create a minimal XMP template structure.

    Returns:
        Root element of XMP structure.
    """
    root = ET.Element('{adobe:ns:meta/}xmpmeta')
    root.set('{adobe:ns:meta/}xmptk', 'home-media-ai')

    rdf = ET.SubElement(root, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF')
    desc = ET.SubElement(rdf, '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
    desc.set('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about', '')

    return root


def read_rating_from_file(
    file_path: Union[str, Path]
) -> Optional[int]:
    """Read rating from file metadata or XMP sidecar.

    Args:
        file_path: Path to the media file.

    Returns:
        Rating value (1-5), or None if no rating found.
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    # Try EXIF for JPEG/TIFF
    if ext in ('.jpg', '.jpeg', '.tiff', '.tif'):
        rating = _read_rating_from_exif(file_path)
        if rating is not None:
            return rating

    # Try XMP sidecar
    xmp_path = file_path.with_suffix('.xmp')
    if xmp_path.exists():
        return _read_rating_from_xmp(xmp_path)

    return None


def _read_rating_from_exif(file_path: Path) -> Optional[int]:
    """Read rating from EXIF metadata.

    Args:
        file_path: Path to the image file.

    Returns:
        Rating value (1-5), or None if not found.
    """
    try:
        import piexif

        exif_dict = piexif.load(str(file_path))
        RATING_TAG = 18246

        if RATING_TAG in exif_dict.get('0th', {}):
            rating = exif_dict['0th'][RATING_TAG]
            if 1 <= rating <= 5:
                return rating

    except Exception:
        pass

    return None


def _read_rating_from_xmp(xmp_path: Path) -> Optional[int]:
    """Read rating from XMP sidecar file.

    Args:
        xmp_path: Path to the XMP file.

    Returns:
        Rating value (1-5), or None if not found.
    """
    try:
        tree = ET.parse(xmp_path)
        root = tree.getroot()

        xmp_ns = '{http://ns.adobe.com/xap/1.0/}'

        # Find rating element
        for elem in root.iter():
            if elem.tag == f'{xmp_ns}Rating':
                rating = int(elem.text)
                if 1 <= rating <= 5:
                    return rating

    except Exception:
        pass

    return None


def batch_sync_ratings(
    session: Session,
    media_ids: list[int] = None,
    use_local_mapping: bool = True
) -> tuple[int, int]:
    """Sync ratings from database to files for multiple media items.

    Args:
        session: Database session.
        media_ids: List of media IDs to sync, or None for all with ratings.
        use_local_mapping: Use local path mapping from config.

    Returns:
        Tuple of (successful_count, failed_count).
    """
    if media_ids:
        media_items = session.query(Media).filter(Media.id.in_(media_ids)).all()
    else:
        # Sync all media with ratings
        media_items = session.query(Media).filter(
            Media.rating.is_not(None),
            Media.rating > 0
        ).all()

    successful = 0
    failed = 0

    for media in media_items:
        if media.rating:
            result = sync_rating_to_file(
                media=media,
                rating=media.rating,
                session=session,
                use_local_mapping=use_local_mapping
            )
            if result:
                successful += 1
            else:
                failed += 1

    logger.info(f"Batch sync complete: {successful} successful, {failed} failed")
    return successful, failed
