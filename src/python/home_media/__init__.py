"""
HomeMedia - AI-powered home media management and classification system.

This package provides tools for managing, classifying, and analyzing home media
files (images and videos) using AI/ML techniques.

Core Concepts:
- Image: A moment in time (a single capture event)
- ImageFile: A file representing part of an Image (RAW, JPEG, XMP, etc.)

Usage:
    from home_media.scanner import scan_directory
    from pathlib import Path

    images_df, files_df = scan_directory(Path("/photos/2025/01/01"))
    print(f"Found {len(images_df)} images with {len(files_df)} files")
"""

from home_media.__version__ import __version__
from home_media.models import FileFormat, FileRole, Image, ImageFile
from home_media.scanner import (
    ExifData,
    extract_base_name,
    extract_exif_metadata,
    group_files_to_images,
    list_subdirectories,
    scan_directory,
)

__all__ = [
    "__version__",
    # Models
    "FileFormat",
    "FileRole",
    "Image",
    "ImageFile",
    # Scanner
    "ExifData",
    "extract_base_name",
    "extract_exif_metadata",
    "group_files_to_images",
    "list_subdirectories",
    "scan_directory",
]
