"""
Directory scanning for discovering image files.

This module provides functions to scan directories for image files
and return the results as pandas DataFrames for easy analysis.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union

import pandas as pd

from home_media.models.image import Image, ImageFile
from home_media.scanner.grouper import group_files_to_images
from home_media.scanner.patterns import is_image_file, is_sidecar_file


def scan_directory(
    directory: Path,
    photos_root: Optional[Path] = None,
    recursive: bool = False,
    include_sidecars: bool = True,
    extract_exif: bool = False,
    calculate_hash: bool = False,
    extract_dimensions: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Scan a directory for image files and return DataFrames.

    Args:
        directory: Directory to scan
        photos_root: Root directory for calculating relative subdirectories.
                    If None, uses the scanned directory.
        recursive: If True, scan subdirectories recursively
        include_sidecars: If True, include sidecar files (XMP, etc.)
        extract_exif: If True, extract EXIF metadata from original files.
                     This populates captured_at, camera_make, camera_model, etc.
                     Note: This can be slow for large directories.
        calculate_hash: If True, calculate SHA256 hash for each file.
                       Useful for deduplication. Can be slow for large files.
        extract_dimensions: If True, extract image dimensions (width, height).
                           Works for both RAW and standard image formats.

    Returns:
        Tuple of (images_df, files_df):
        - images_df: DataFrame with one row per Image (moment in time)
        - files_df: DataFrame with one row per file, linked to images by base_name

    Example:
        >>> images_df, files_df = scan_directory(Path("/photos/2025/01/01"))
        >>> print(f"Found {len(images_df)} images with {len(files_df)} files")

        >>> # With EXIF extraction
        >>> images_df, files_df = scan_directory(Path("/photos"), extract_exif=True)
        >>> print(images_df[['base_name', 'captured_at', 'camera_model']].head())

        >>> # With full metadata
        >>> images_df, files_df = scan_directory(
        ...     Path("/photos"),
        ...     extract_exif=True,
        ...     calculate_hash=True,
        ...     extract_dimensions=True
        ... )
        >>> print(files_df[['filename', 'width', 'height', 'file_hash']].head())
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    if photos_root is None:
        photos_root = directory

    # Collect all relevant files
    file_paths = _collect_files(
        directory,
        recursive=recursive,
        include_sidecars=include_sidecars,
    )

    # Group files into Images
    images = group_files_to_images(file_paths, photos_root)

    # Extract EXIF metadata if requested
    if extract_exif:
        for image in images:
            image.populate_from_exif()

    # Populate file-level metadata if requested
    if calculate_hash or extract_dimensions:
        for image in images:
            for file in image.files:
                if calculate_hash:
                    file.populate_hash()
                if extract_dimensions:
                    file.populate_dimensions()

    # Convert to DataFrames
    images_df = images_to_dataframe(images)
    files_df  = image_files_to_dataframe(images)

    return images_df, files_df


def _collect_files(
    directory: Path,
    recursive: bool = False,
    include_sidecars: bool = True,
) -> List[Path]:
    """
    Collect all relevant files from a directory.

    Args:
        directory: Directory to scan
        recursive: If True, scan subdirectories recursively
        include_sidecars: If True, include sidecar files

    Returns:
        List of file paths
    """
    files = []

    iterator = directory.rglob("*") if recursive else directory.iterdir()

    for path in iterator:
        if not path.is_file():
            continue

        # Skip hidden files
        if path.name.startswith("."):
            continue

        # Check if it's an image or sidecar file
        if is_image_file(path.name):
            files.append(path)
        elif include_sidecars and is_sidecar_file(path.name):
            files.append(path)

    return files


def images_to_dataframe(images: List[Image]) -> pd.DataFrame:
    """
    Convert a list of Images to a pandas DataFrame.

    Args:
        images: List of Image objects

    Returns:
        DataFrame with one row per Image
    """
    if not images:
        return pd.DataFrame()

    data = [img.to_dict() for img in images]
    return pd.DataFrame(data)


def image_files_to_dataframe(files: Union[List[Image], List[ImageFile]]) -> pd.DataFrame:
    """
    Convert ImageFiles to a pandas DataFrame.

    Args:
        files: Either a list of Image objects (extracts all ImageFiles)
              or a list of ImageFile objects directly

    Returns:
        DataFrame with one row per ImageFile
    """
    if not files:
        return pd.DataFrame()

    data = []

    # Check if we have Images or ImageFiles
    if isinstance(files[0], Image):
        # Extract ImageFiles from Images
        for image in files:
            for file in image.files:
                file_dict = file.to_dict()
                # Add image identifiers for linking
                file_dict["base_name"] = image.base_name
                file_dict["subdirectory"] = image.subdirectory
                data.append(file_dict)
    else:
        # Direct list of ImageFiles
        for file in files:
            data.append(file.to_dict())

    return pd.DataFrame(data)


def list_subdirectories(directory: Path, recursive: bool = False) -> List[Path]:
    """
    List all subdirectories in a directory.

    Args:
        directory: Directory to scan
        recursive: If True, list subdirectories recursively

    Returns:
        List of subdirectory paths, sorted alphabetically
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    subdirs = []

    if recursive:
        # Use rglob to find all subdirectories recursively
        for item in directory.rglob("*"):
            if item.is_dir():
                subdirs.append(item)
    else:
        # Just list immediate subdirectories
        for item in directory.iterdir():
            if item.is_dir():
                subdirs.append(item)

    return sorted(subdirs)


def count_files_in_directory(
    directory: Path,
    recursive: bool = False,
    include_sidecars: bool = True,
) -> int:
    """
    Count the number of image files in a directory.

    Args:
        directory: Directory to scan
        recursive: If True, count files in subdirectories too
        include_sidecars: If True, include sidecar files in the count

    Returns:
        Number of image files
    """
    files = _collect_files(directory, recursive=recursive, include_sidecars=include_sidecars)
    return len(files)
