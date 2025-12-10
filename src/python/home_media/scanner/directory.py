"""
Directory scanning for discovering image files.

This module provides functions to scan directories for image files
and return the results as pandas DataFrames for easy analysis.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from home_media.models.image import Image
from home_media.scanner.grouper import group_files_to_images
from home_media.scanner.patterns import is_image_file, is_sidecar_file


def scan_directory(
    directory: Path,
    photos_root: Optional[Path] = None,
    recursive: bool = False,
    include_sidecars: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Scan a directory for image files and return DataFrames.

    Args:
        directory: Directory to scan
        photos_root: Root directory for calculating relative subdirectories.
                    If None, uses the scanned directory.
        recursive: If True, scan subdirectories recursively
        include_sidecars: If True, include sidecar files (XMP, etc.)

    Returns:
        Tuple of (images_df, files_df):
        - images_df: DataFrame with one row per Image (moment in time)
        - files_df: DataFrame with one row per file, linked to images by base_name

    Example:
        >>> images_df, files_df = scan_directory(Path("/photos/2025/01/01"))
        >>> print(f"Found {len(images_df)} images with {len(files_df)} files")
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

    # Convert to DataFrames
    images_df = images_to_dataframe(images)
    files_df = image_files_to_dataframe(images)

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

    if recursive:
        iterator = directory.rglob("*")
    else:
        iterator = directory.iterdir()

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


def image_files_to_dataframe(images: List[Image]) -> pd.DataFrame:
    """
    Convert all ImageFiles from a list of Images to a pandas DataFrame.

    Args:
        images: List of Image objects

    Returns:
        DataFrame with one row per ImageFile, with base_name for linking
    """
    if not images:
        return pd.DataFrame()

    data = []
    for image in images:
        for file in image.files:
            file_dict = file.to_dict()
            # Add image identifiers for linking
            file_dict["base_name"] = image.base_name
            file_dict["subdirectory"] = image.subdirectory
            data.append(file_dict)

    return pd.DataFrame(data)


def list_subdirectories(directory: Path) -> List[Path]:
    """
    List all subdirectories in a directory.

    Args:
        directory: Directory to scan

    Returns:
        List of subdirectory paths, sorted alphabetically
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    subdirs = [d for d in directory.iterdir() if d.is_dir()]
    return sorted(subdirs)


def count_files_in_directory(directory: Path, recursive: bool = False) -> int:
    """
    Count the number of image files in a directory.

    Args:
        directory: Directory to scan
        recursive: If True, count files in subdirectories too

    Returns:
        Number of image files
    """
    files = _collect_files(directory, recursive=recursive, include_sidecars=True)
    return len(files)
