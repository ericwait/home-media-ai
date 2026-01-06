"""
EXIF metadata extraction for image files.

This module extracts metadata from both RAW and standard image files:
- RAW files (CR2, CR3, NEF, DNG, etc.): Uses exifread library
- Standard formats (JPEG, PNG, TIFF): Uses Pillow/PIL library

Extracted metadata includes:
- Capture timestamp (DateTimeOriginal)
- Camera make and model
- Lens information
- GPS coordinates
- User metadata (title, description, rating)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ExifData:
    """
    Container for extracted EXIF metadata.

    Attributes:
        captured_at: When the photo was taken
        camera_make: Camera manufacturer
        camera_model: Camera model name
        lens: Lens model/description
        gps_latitude: GPS latitude (decimal degrees)
        gps_longitude: GPS longitude (decimal degrees)
        title: Image title
        description: Image description
        rating: User rating (0-5)
    """

    def __init__(
        self,
        captured_at: Optional[datetime] = None,
        camera_make: Optional[str] = None,
        camera_model: Optional[str] = None,
        lens: Optional[str] = None,
        gps_latitude: Optional[float] = None,
        gps_longitude: Optional[float] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        rating: Optional[int] = None,
    ):
        self.captured_at = captured_at
        self.camera_make = camera_make
        self.camera_model = camera_model
        self.lens = lens
        self.gps_latitude = gps_latitude
        self.gps_longitude = gps_longitude
        self.title = title
        self.description = description
        self.rating = rating

    def to_dict(self) -> Dict[str, Optional[str | datetime | float | int]]:
        """Convert to dictionary for easy attribute assignment."""
        return {
            "captured_at": self.captured_at,
            "camera_make": self.camera_make,
            "camera_model": self.camera_model,
            "lens": self.lens,
            "gps_latitude": self.gps_latitude,
            "gps_longitude": self.gps_longitude,
            "title": self.title,
            "description": self.description,
            "rating": self.rating,
        }


def extract_exif_metadata(file_path: Path) -> Optional[ExifData]:
    """
    Extract EXIF metadata from an image file.

    This function attempts to extract metadata using:
    1. exifread for RAW files (CR2, CR3, NEF, DNG, etc.)
    2. Pillow/PIL for standard formats (JPEG, PNG, TIFF)

    Returns None if the file cannot be read or has no EXIF data.

    Args:
        file_path: Path to the image file

    Returns:
        ExifData object with extracted metadata, or None if extraction fails

    Example:
        >>> exif = extract_exif_metadata(Path("/photos/IMG_1234.CR2"))
        >>> if exif:
        ...     print(f"Captured: {exif.captured_at}")
        ...     print(f"Camera: {exif.camera_make} {exif.camera_model}")
    """
    if not file_path.exists() or not file_path.is_file():
        logger.warning("File not found or not a file: %s", file_path)
        return None

    if file_path.stat().st_size == 0:
        logger.warning("File is empty (0 bytes): %s", file_path)
        return None

    # Determine file type and use appropriate extraction method
    from home_media.models.enums import FileFormat

    file_format = FileFormat.from_filename(file_path.name)

    try:
        # For RAW files and HEIC/HEIF (which Pillow often can't handle without plugins), use exifread
        if file_format.is_raw or file_format in (FileFormat.HEIC, FileFormat.HEIF):
            return _extract_with_exifread(file_path)
        # For standard formats, use Pillow
        else:
            return _extract_with_pillow(file_path)
    except Exception as e:
        logger.error("Failed to extract EXIF from %s: %s", file_path, e)
        return None


def _extract_with_exifread(file_path: Path) -> Optional[ExifData]:
    """
    Extract EXIF metadata using exifread library.

    This method works well with RAW files (CR2, CR3, NEF, DNG, etc.)
    that Pillow cannot read.

    Args:
        file_path: Path to the RAW image file

    Returns:
        ExifData object or None if extraction fails
    """
    try:
        import exifread
    except ImportError:
        logger.error("exifread not installed. Install with: pip install exifread")
        return None

    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)

            if not tags:
                logger.debug("No EXIF data found in %s", file_path)
                return None

            # Extract capture datetime
            captured_at = _parse_datetime(
                tags.get("EXIF DateTimeOriginal") or
                tags.get("Image DateTime") or
                tags.get("EXIF DateTimeDigitized")
            )

            # Extract camera info
            camera_make = _clean_string(str(tags.get("Image Make", "")))
            camera_model = _clean_string(str(tags.get("Image Model", "")))
            lens = _clean_string(
                str(tags.get("EXIF LensModel", "")) or
                str(tags.get("EXIF LensMake", ""))
            )

            # Extract GPS coordinates
            gps_latitude, gps_longitude = _parse_exifread_gps(tags)

            # Extract user metadata
            title = _clean_string(str(tags.get("Image ImageDescription", "")))
            description = _clean_string(str(tags.get("EXIF UserComment", "")))
            rating = None
            if "Image Rating" in tags:
                try:
                    rating = int(str(tags["Image Rating"]))
                except (ValueError, TypeError):
                    pass

            return ExifData(
                captured_at=captured_at,
                camera_make=camera_make,
                camera_model=camera_model,
                lens=lens,
                gps_latitude=gps_latitude,
                gps_longitude=gps_longitude,
                title=title,
                description=description,
                rating=rating,
            )

    except Exception as e:
        logger.warning("exifread failed to extract EXIF from %s: %s", file_path, e)
        return None


def _extract_with_pillow(file_path: Path) -> Optional[ExifData]:
    """
    Extract EXIF metadata using Pillow/PIL.

    Args:
        file_path: Path to the image file

    Returns:
        ExifData object or None if extraction fails
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
    except ImportError:
        logger.error("Pillow not installed. Install with: pip install Pillow")
        return None

    try:
        with Image.open(file_path) as img:
            exif_data = img.getexif()

            if not exif_data or isinstance(exif_data, int):
                logger.debug("No valid EXIF data found in %s", file_path)
                return None

            # Parse standard EXIF tags
            exif_dict = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif_data.items()}

            # Extract GPS data if present
            gps_latitude, gps_longitude = None, None
            if "GPSInfo" in exif_dict:
                gps_raw = exif_dict["GPSInfo"]
                if isinstance(gps_raw, dict) or hasattr(gps_raw, "items"):
                    try:
                        gps_info = {GPSTAGS.get(tag_id, tag_id): value for tag_id, value in gps_raw.items()}
                        gps_latitude, gps_longitude = _parse_gps_coords(gps_info)
                    except Exception as e:
                        logger.debug("Failed to process GPSInfo dict: %s", e)
                else:
                    logger.debug("GPSInfo is not a dict (type: %s), skipping GPS extraction.", type(gps_raw))

            # Parse datetime
            captured_at = _parse_datetime(
                exif_dict.get("DateTimeOriginal") or
                exif_dict.get("DateTime") or
                exif_dict.get("DateTimeDigitized")
            )

            # Extract camera info
            camera_make = _clean_string(exif_dict.get("Make"))
            camera_model = _clean_string(exif_dict.get("Model"))
            lens = _clean_string(exif_dict.get("LensModel") or exif_dict.get("LensMake"))

            # Extract user metadata (may not be present in all files)
            title = _clean_string(exif_dict.get("ImageDescription"))
            description = _clean_string(exif_dict.get("UserComment"))
            rating = exif_dict.get("Rating")

            return ExifData(
                captured_at=captured_at,
                camera_make=camera_make,
                camera_model=camera_model,
                lens=lens,
                gps_latitude=gps_latitude,
                gps_longitude=gps_longitude,
                title=title,
                description=description,
                rating=rating,
            )

    except Exception as e:
        logger.warning("Pillow failed to extract EXIF from %s: %s", file_path, e)
        return None


def _parse_datetime(value) -> Optional[datetime]:
    """
    Parse EXIF datetime to datetime object.

    Works with both string values and exifread tag objects.
    EXIF datetime format: "YYYY:MM:DD HH:MM:SS"

    Args:
        value: EXIF datetime (string or exifread tag)

    Returns:
        datetime object or None if parsing fails
    """
    if not value:
        return None

    try:
        # Convert to string (handles both plain strings and exifread IfdTag objects)
        datetime_str = str(value)
        # EXIF format: "2025:01:01 12:30:45"
        return datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
    except (ValueError, TypeError) as e:
        logger.debug("Failed to parse datetime '%s': %s", value, e)
        return None


def _parse_gps_coords(gps_info: Dict) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse GPS coordinates from EXIF GPS info.

    GPS coordinates in EXIF are stored as tuples of rational numbers
    (degrees, minutes, seconds) plus a reference (N/S for latitude, E/W for longitude).

    Args:
        gps_info: Dictionary of GPS EXIF tags

    Returns:
        Tuple of (latitude, longitude) in decimal degrees, or (None, None) if parsing fails
    """
    try:
        lat = gps_info.get("GPSLatitude")
        lat_ref = gps_info.get("GPSLatitudeRef")
        lon = gps_info.get("GPSLongitude")
        lon_ref = gps_info.get("GPSLongitudeRef")

        if not all([lat, lat_ref, lon, lon_ref]):
            return None, None

        # Convert from degrees/minutes/seconds to decimal degrees
        latitude = _dms_to_decimal(lat, lat_ref)
        longitude = _dms_to_decimal(lon, lon_ref)

        return latitude, longitude

    except Exception as e:
        logger.debug("Failed to parse GPS coordinates: %s", e)
        return None, None


def _dms_to_decimal(dms: Tuple, ref: str) -> float:
    """
    Convert GPS coordinates from degrees/minutes/seconds to decimal degrees.

    Handles both Pillow-style tuples and exifread-style Ratio objects.

    Args:
        dms: Tuple of (degrees, minutes, seconds) - each can be a number or tuple (numerator, denominator)
        ref: Reference direction ('N', 'S', 'E', 'W', 'North', 'South', 'East', 'West')

    Returns:
        Decimal degrees
    """
    degrees, minutes, seconds = dms

    # Handle rational numbers (stored as tuples)
    if isinstance(degrees, tuple):
        degrees = degrees[0] / degrees[1]
    if isinstance(minutes, tuple):
        minutes = minutes[0] / minutes[1]
    if isinstance(seconds, tuple):
        seconds = seconds[0] / seconds[1]

    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600

    # Apply negative sign for South and West
    if ref in {"S", "W", "South", "West"}:
        decimal = -decimal

    return decimal


def _clean_string(value: Optional[str]) -> Optional[str]:
    """
    Clean and normalize a string value from EXIF.

    Removes trailing nulls, extra whitespace, etc.

    Args:
        value: Raw string value

    Returns:
        Cleaned string or None
    """
    if value is None:
        return None

    # Convert to string if needed
    value = str(value)

    # Strip whitespace and null characters
    value = value.strip().rstrip("\x00")

    # Return None for empty strings
    return value or None


def _parse_exifread_gps(tags: Dict) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse GPS coordinates from exifread tags.

    Args:
        tags: Dictionary of exifread tags

    Returns:
        Tuple of (latitude, longitude) in decimal degrees, or (None, None) if parsing fails
    """
    try:
        lat = tags.get("GPS GPSLatitude")
        lat_ref = tags.get("GPS GPSLatitudeRef")
        lon = tags.get("GPS GPSLongitude")
        lon_ref = tags.get("GPS GPSLongitudeRef")

        if not all([lat, lat_ref, lon, lon_ref]):
            return None, None

        # Convert exifread Ratio objects to tuples for compatibility with _dms_to_decimal
        # exifread returns IfdTag objects with values attribute containing Ratio objects
        lat_values = lat.values
        lon_values = lon.values

        # Convert Ratio objects (with .num and .den) to regular tuples
        lat_dms = tuple((v.num, v.den) for v in lat_values)
        lon_dms = tuple((v.num, v.den) for v in lon_values)

        lat_ref_str = str(lat_ref.values)
        lon_ref_str = str(lon_ref.values)

        # Use the shared conversion function
        latitude = _dms_to_decimal(lat_dms, lat_ref_str)
        longitude = _dms_to_decimal(lon_dms, lon_ref_str)

        return latitude, longitude

    except Exception as e:
        logger.debug("Failed to parse exifread GPS coordinates: %s", e)
        return None, None
