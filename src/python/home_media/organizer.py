"""
Module for organizing and moving image files.
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from home_media.config import get_photos_root, load_config
from home_media.models.image import Image
from home_media.scanner.directory import scan_directory
from home_media.utils import parse_date_from_filename

logger = logging.getLogger(__name__)


class OrganizationResult:
    """Track results of an organization run."""
    def __init__(self):
        self.images_processed = 0
        self.files_moved = 0
        self.files_skipped = 0
        self.errors = []

    def add_error(self, file_path: Path, error: str):
        self.errors.append((file_path, error))

    def __str__(self):
        return (
            f"Processed {self.images_processed} images. "
            f"Moved {self.files_moved} files. "
            f"Skipped {self.files_skipped} files. "
            f"Errors: {len(self.errors)}"
        )


def organize_directory(
    source_dir: Path,
    config_path: Optional[Path] = None,
    dry_run: bool = True
) -> OrganizationResult:
    """
    Organize images from source_dir into the library structure.

    Args:
        source_dir: Directory to scan for images.
        config_path: Path to config file.
        dry_run: If True, only log actions without moving files.

    Returns:
        OrganizationResult with stats.
    """
    result = OrganizationResult()

    if not source_dir.exists():
        logger.error("Source directory not found: %s", source_dir)
        return result

    # Load configuration
    try:
        config = load_config(config_path)
        destination_root = get_photos_root(config)
    except Exception as e:
        logger.error("Configuration error: %s", e)
        return result

    if not destination_root.exists() and not dry_run:
        try:
            destination_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error("Could not create destination root: %s", e)
            return result

    logger.info("Scanning source directory: %s", source_dir)
    # We need EXIF to determine dates for renaming
    images_df, _ = scan_directory(source_dir, extract_exif=True, recursive=True)

    # Convert DataFrame back to list of Images (or we could modify scan_directory, 
    # but for now we can't easily get the objects back from DF if the DF creation 
    # consumed them or if scan_directory doesn't return them. 
    # Wait, scan_directory returns DFs. The Image objects are internal to scan_directory 
    # before DF conversion.
    # Actually, looking at scan_directory code:
    # images_df = images_to_dataframe(images)
    # It returns DFs. The DFs contain dicts. We lose the Image methods/objects.
    # 
    # This is a limitation of the current scanner.py.
    # However, I need the logic to calculate canonical names which is on the Image class.
    # I should either:
    # 1. Update scan_directory to return Image objects (or have a variant).
    # 2. Re-instantiate Image objects from DF data?
    # 3. Refactor scan_directory to separate the "get images" from "make df".
    
    # Let's check scanner/directory.py again.
    # It calls `group_files_to_images` then `images_to_dataframe`.
    # I should probably expose a function that returns the objects.
    
    # For now, I will RE-IMPLEMENT the scanning part here using the existing components
    # to get the objects, avoiding the DF conversion.
    
    from home_media.scanner.directory import _collect_files
    from home_media.scanner.grouper import group_files_to_images
    
    files = _collect_files(source_dir, recursive=True, include_sidecars=True)
    images = group_files_to_images(files, source_dir)
    
    # Populate EXIF
    for image in images:
        image.populate_from_exif()

    logger.info("Found %d image groups to process", len(images))

    for image in images:
        process_image(image, destination_root, result, dry_run)

    if not dry_run:
        cleanup_empty_directories(source_dir)

    return result


def cleanup_empty_directories(directory: Path):
    """
    Recursively remove empty directories.
    
    Args:
        directory: Root directory to clean up
    """
    if not directory.exists():
        return

    # Walk bottom-up to ensure we clean up nested empty dirs
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in dirs:
            dir_path = Path(root) / name
            try:
                # Check if directory is empty (os.rmdir fails if not empty anyway)
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    logger.info("Removed empty directory: %s", dir_path)
            except OSError as e:
                # Directory might not be empty or permission error
                logger.debug("Could not remove directory %s: %s", dir_path, e)


def process_image(
    image: Image,
    destination_root: Path,
    result: OrganizationResult,
    dry_run: bool
):
    """
    Process a single Image group: determine target and move files.
    """
    result.images_processed += 1

    # Determine canonical date
    if not image.captured_at:
        # Try to parse date from filename first
        filename_date = parse_date_from_filename(image.base_name)
        
        if filename_date:
            target_date = filename_date
            logger.info("No EXIF for %s, parsed date from filename: %s", image.base_name, target_date)
        elif image.earliest_file_date:
            target_date = image.earliest_file_date
            logger.warning("No EXIF or filename date for %s, using file date: %s", image.base_name, target_date)
        else:
            logger.warning("No date found for %s. Skipping.", image.base_name)
            result.add_error(Path(image.base_name), "No date found")
            return
    else:
        target_date = image.captured_at

    # Calculate target directory: root/yyyy/mm/dd
    target_subdir = target_date.strftime("%Y/%m/%d")
    target_dir = destination_root / target_subdir

    # Calculate target base name: yyyy-mm-dd_HH-MM-SS
    target_base_name = target_date.strftime("%Y-%m-%d_%H-%M-%S")

    # Find unique base name to avoid collisions
    final_base_name = _get_unique_base_name(target_dir, target_base_name, image.suffixes)

    # Move files
    for file in image.files:
        # Construct new filename
        # New name = FinalBaseName + Suffix
        # Note: suffix includes extension, e.g. ".CR2" or "-edit.jpg"
        new_filename = final_base_name + file.suffix
        target_path = target_dir / new_filename

        if dry_run:
            logger.info("[DRY RUN] Move: %s -> %s", file.file_path, target_path)
            result.files_moved += 1
        else:
            try:
                # Ensure dir exists
                target_dir.mkdir(parents=True, exist_ok=True)
                
                logger.info("Moving: %s -> %s", file.file_path.name, target_path)
                shutil.move(str(file.file_path), str(target_path))
                result.files_moved += 1
            except Exception as e:
                logger.error("Failed to move %s: %s", file.file_path, e)
                result.add_error(file.file_path, str(e))


def _get_unique_base_name(directory: Path, base_name: str, suffixes: List[str]) -> str:
    """
    Find a unique base name in directory that doesn't conflict for ANY of the suffixes.
    
    Args:
        directory: Target directory
        base_name: Preferred base name
        suffixes: List of suffixes that will be attached to base name
    
    Returns:
        Unique base name (possibly with sequence number)
    """
    if not directory.exists():
        return base_name

    candidate = base_name
    sequence = 1

    while True:
        conflict = False
        for suffix in suffixes:
            target_path = directory / (candidate + suffix)
            if target_path.exists():
                conflict = True
                break
        
        if not conflict:
            return candidate

        # Generate next candidate
        candidate = f"{base_name}_{sequence:03d}"
        sequence += 1
