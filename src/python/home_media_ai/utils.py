"""Common utility functions for the home_media_ai package.

This module contains shared functionality used across multiple modules
to avoid code duplication and maintain consistency.
"""

import hashlib
from pathlib import Path
from typing import Optional, Tuple

from .constants import MEDIA_TYPE_EXTENSIONS


def infer_media_type_from_extension(extension: str) -> Optional[str]:
    """Infer media type from file extension.

    Args:
        extension: File extension including the dot (e.g., '.jpg') or without (e.g., 'jpg').
                  Case-insensitive.

    Returns:
        Media type string (e.g., 'jpeg', 'raw_image', 'png') or None if not recognized.

    Examples:
        >>> infer_media_type_from_extension('.jpg')
        'jpeg'
        >>> infer_media_type_from_extension('CR2')
        'raw_image'
        >>> infer_media_type_from_extension('.unknown')
        None
    """
    # Normalize extension: ensure lowercase and has leading dot
    ext = extension.lower()
    if not ext.startswith('.'):
        ext = '.' + ext

    for media_type, extensions in MEDIA_TYPE_EXTENSIONS.items():
        if ext in extensions:
            return media_type

    return None


def get_all_supported_extensions() -> set:
    """Get a set of all supported file extensions.

    Returns:
        Set of file extensions including the dot (e.g., {'.jpg', '.cr2', ...})

    Example:
        >>> extensions = get_all_supported_extensions()
        >>> '.jpg' in extensions
        True
    """
    all_extensions = set()
    for extensions in MEDIA_TYPE_EXTENSIONS.values():
        all_extensions.update(extensions)
    return all_extensions


def calculate_file_hash(file_path: str, chunk_size: int = 8192) -> str:
    """Calculate SHA-256 hash of a file.

    Reads the file in chunks to handle large files efficiently.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Size of chunks to read at a time (default: 8192 bytes).

    Returns:
        Hexadecimal string representation of the SHA-256 hash.

    Raises:
        OSError: If the file cannot be read.

    Example:
        >>> hash_value = calculate_file_hash('/path/to/image.jpg')
        >>> len(hash_value)
        64
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except OSError:
        raise


def split_file_path(
    full_path: str,
    storage_root: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], str]:
    """Split a file path into storage_root, directory, and filename components.

    This is useful for storing file paths in a database in a normalized way
    that's independent of mount points and allows for path remapping.

    Args:
        full_path: The full absolute path to the file.
        storage_root: Optional storage root path. If provided, will compute
                     directory as relative path from storage_root.
                     If None, uses parent directory as storage_root.

    Returns:
        Tuple of (storage_root, directory, filename) where:
        - storage_root: The mount point or base path
        - directory: Relative path from storage_root to file's parent dir (or None)
        - filename: Just the filename with extension

    Examples:
        >>> # Without storage_root
        >>> split_file_path('/volume1/photos/2024/January/IMG_001.jpg')
        ('/volume1/photos/2024/January', None, 'IMG_001.jpg')

        >>> # With storage_root
        >>> split_file_path(
        ...     '/volume1/photos/2024/January/IMG_001.jpg',
        ...     storage_root='/volume1/photos'
        ... )
        ('/volume1/photos', '2024/January', 'IMG_001.jpg')

        >>> # File not under storage_root
        >>> split_file_path(
        ...     '/other/path/IMG_001.jpg',
        ...     storage_root='/volume1/photos'
        ... )
        ('/other/path', None, 'IMG_001.jpg')
    """
    path_obj = Path(full_path)
    filename = path_obj.name

    if not storage_root:
        # No storage_root provided, use parent directory as storage_root
        return str(path_obj.parent), None, filename

    # If storage_root is provided, calculate relative path
    storage_root_path = Path(storage_root)
    try:
        relative_path = path_obj.parent.relative_to(storage_root_path)
        directory = str(relative_path) if str(relative_path) != '.' else None
        return storage_root, directory, filename
    except ValueError:
        # Path is not relative to storage_root, use the parent as storage_root
        return str(path_obj.parent), None, filename


def validate_file_extension(file_path: str, raise_on_unsupported: bool = False) -> bool:
    """Check if a file has a supported media extension.

    Args:
        file_path: Path to the file to check.
        raise_on_unsupported: If True, raises ValueError for unsupported extensions.
                             If False, returns False instead.

    Returns:
        True if the file extension is supported, False otherwise (when raise_on_unsupported=False).

    Raises:
        ValueError: If the extension is not supported and raise_on_unsupported=True.

    Examples:
        >>> validate_file_extension('photo.jpg')
        True
        >>> validate_file_extension('document.pdf')
        False
        >>> validate_file_extension('document.pdf', raise_on_unsupported=True)
        Traceback (most recent call last):
        ...
        ValueError: Unsupported file extension: .pdf
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    media_type = infer_media_type_from_extension(extension)

    if media_type is None:
        if raise_on_unsupported:
            supported = get_all_supported_extensions()
            raise ValueError(
                f"Unsupported file extension: {extension}. "
                f"Supported extensions: {sorted(supported)}"
            )
        return False

    return True


def normalize_extension(extension: str) -> str:
    """Normalize a file extension to lowercase with leading dot.

    Args:
        extension: File extension with or without leading dot.

    Returns:
        Normalized extension with lowercase and leading dot.

    Examples:
        >>> normalize_extension('JPG')
        '.jpg'
        >>> normalize_extension('.CR2')
        '.cr2'
        >>> normalize_extension('png')
        '.png'
    """
    ext = extension.lower()
    if not ext.startswith('.'):
        ext = '.' + ext
    return ext
