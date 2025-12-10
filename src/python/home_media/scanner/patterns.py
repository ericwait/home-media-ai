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
    match = re.match(r"^(.+?)(_\d+)?$", name_without_ext)
    if match:
        base_name = match.group(1)
    else:
        base_name = name_without_ext

    # Calculate the suffix (everything after base_name)
    suffix = filename[len(base_name):]

    return base_name, suffix


def is_sidecar_file(filename: str) -> bool:
    """
    Check if a file is a sidecar/metadata file.

    Args:
        filename: The filename to check

    Returns:
        True if this is a sidecar file (XMP, THM, etc.)
    """
    lower = filename.lower()
    return (
        lower.endswith(".xmp")
        or lower.endswith(".thm")
        or ".xmp" in lower  # Handles .jpg.xmp
    )


def is_raw_file(filename: str) -> bool:
    """
    Check if a file is a RAW image file.

    Args:
        filename: The filename to check

    Returns:
        True if this is a RAW file
    """
    raw_extensions = {
        ".cr2", ".cr3", ".nef", ".arw", ".dng",
        ".raf", ".orf", ".rw2", ".raw"
    }
    ext = Path(filename).suffix.lower()
    return ext in raw_extensions


def is_image_file(filename: str) -> bool:
    """
    Check if a file is an image file (RAW or standard).

    Args:
        filename: The filename to check

    Returns:
        True if this is an image file
    """
    image_extensions = {
        # RAW
        ".cr2", ".cr3", ".nef", ".arw", ".dng",
        ".raf", ".orf", ".rw2", ".raw",
        # Standard
        ".jpg", ".jpeg", ".png", ".tiff", ".tif",
        ".heic", ".heif", ".webp",
    }
    ext = Path(filename).suffix.lower()
    return ext in image_extensions


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
