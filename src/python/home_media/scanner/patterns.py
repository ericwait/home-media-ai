"""
Filename pattern detection for grouping related image files.

This module extracts base names from filenames to group related files
that represent the same Image (moment in time).

Supported patterns:
1. Google Pixel RAW: PXL_20251210_200246684.RAW-01.COVER.jpg
2. Standard datetime: 2025-01-01_00-28-40.jpg, 2025-01-01_00-28-40_001.jpg
3. XMP sidecars: filename.jpg.xmp
4. Numbered derivatives: filename_001.jpg, filename_002.jpg
"""

import re
from pathlib import Path
from typing import Tuple

from home_media.models.enums import FileFormat


def extract_base_name(filename: str) -> Tuple[str, str]:
    """
    Extract the base name from a filename.

    The base name is the common identifier that groups related files.
    For example, "2025-01-01_00-28-40.jpg" and "2025-01-01_00-28-40.CR3"
    both have the base name "2025-01-01_00-28-40".

    Args:
        filename: The filename to analyze

    Returns:
        Tuple of (base_name, suffix)
        - base_name: The common identifier
        - suffix: Everything after the base_name (including extension)

    Examples:
        >>> extract_base_name("2025-01-01_00-28-40.jpg")
        ('2025-01-01_00-28-40', '.jpg')

        >>> extract_base_name("2025-01-01_00-28-40_001.jpg")
        ('2025-01-01_00-28-40', '_001.jpg')

        >>> extract_base_name("PXL_20251210_200246684.RAW-01.COVER.jpg")
        ('PXL_20251210_200246684', '.RAW-01.COVER.jpg')

        >>> extract_base_name("photo.jpg.xmp")
        ('photo', '.jpg.xmp')
    """

    # TODO: Maybe we can think about something more global/flexible later?
    # Given all the names in a directory, it might be possible to find the best patterns or use EXIF data?
    base_name = filename

    # Pattern 1: Google Pixel RAW files (PXL_timestamp.RAW-##.TYPE.ext)
    # Extract everything before ".RAW-"
    if ".RAW-" in filename.upper():
        base_name = re.split(r"\.RAW-", filename, flags=re.IGNORECASE)[0]
        suffix = filename[len(base_name):]
        return base_name, suffix

    # Pattern 2: Standard files - remove all extensions first
    name_without_ext = filename
    while "." in name_without_ext:
        name_without_ext = Path(name_without_ext).stem

    # Pattern 3: Check for numeric suffix like _001, _002 at the end
    # Match exactly 3 digits for derivative versions (e.g., _001, _002)
    match = re.match(r"^(.+?)(_\d{3})$", name_without_ext)
    base_name = match[1] if match else name_without_ext
    # Calculate the suffix (everything after base_name)
    suffix = filename[len(base_name):]

    return base_name, suffix


def is_sidecar_file(filename: str) -> bool:
    """
    Check if a file is a sidecar/metadata file.

    Uses the FileFormat enum to determine if the file is a sidecar.

    Args:
        filename: The filename to check

    Returns:
        True if this is a sidecar file (XMP, THM, etc.)
    """
    return FileFormat.from_filename(filename).is_sidecar


def is_raw_file(filename: str) -> bool:
    """
    Check if a file is a RAW image file.

    Uses the FileFormat enum to determine if the file is a RAW format.

    Args:
        filename: The filename to check

    Returns:
        True if this is a RAW file
    """
    return FileFormat.from_filename(filename).is_raw


def is_image_file(filename: str) -> bool:
    """
    Check if a file is an image file (RAW or standard).

    Uses the FileFormat enum to determine if the file is an image format.

    Args:
        filename: The filename to check

    Returns:
        True if this is an image file
    """
    return FileFormat.from_filename(filename).is_image


def get_final_extension(filename: str) -> str:
    """
    Get the final extension from a filename.

    Handles multi-extension files like "photo.jpg.xmp" -> ".xmp"

    Args:
        filename: The filename to analyze

    Returns:
        The final extension (lowercase, with leading dot)
    """
    return Path(filename).suffix.lower()


def get_all_extensions(filename: str) -> str:
    """
    Get all extensions from a filename.

    Handles multi-extension files like "photo.jpg.xmp" -> ".jpg.xmp"

    Args:
        filename: The filename to analyze

    Returns:
        All extensions concatenated (lowercase)
    """
    name = filename
    extensions = []

    while "." in name:
        ext = Path(name).suffix.lower()
        extensions.insert(0, ext)
        name = Path(name).stem

    return "".join(extensions)
