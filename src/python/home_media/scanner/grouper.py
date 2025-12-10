"""
Group files into Images based on their base names.

This module takes a list of file paths and groups them into Image objects,
where each Image represents a moment in time and may contain multiple files
(RAW, JPEG, XMP sidecar, etc.).
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from home_media.models.image import Image, ImageFile
from home_media.scanner.patterns import extract_base_name


def group_files_to_images(
    file_paths: List[Path],
    photos_root: Optional[Path] = None,
) -> List[Image]:
    """
    Group a list of file paths into Image objects.

    Each Image represents a moment in time. Files with the same base_name
    are grouped together (e.g., RAW + JPEG + XMP sidecar).

    Args:
        file_paths: List of paths to image files
        photos_root: Root directory for calculating relative subdirectories.
                    If None, uses the parent directory of the first file.

    Returns:
        List of Image objects, each containing its related ImageFiles
    """
    if not file_paths:
        return []

    # Determine photos_root if not provided
    if photos_root is None:
        photos_root = file_paths[0].parent

    # Group files by (base_name, subdirectory)
    groups: Dict[tuple, List[Path]] = defaultdict(list)

    for file_path in file_paths:
        if not file_path.is_file():
            continue

        base_name, _ = extract_base_name(file_path.name)

        # Calculate subdirectory relative to photos_root
        try:
            subdirectory = str(file_path.parent.relative_to(photos_root))
        except ValueError:
            # File is not under photos_root, use parent directory name
            subdirectory = file_path.parent.name

        # Use (base_name, subdirectory) as the grouping key
        key = (base_name, subdirectory)
        groups[key].append(file_path)

    # Create Image objects from groups
    images = []
    for (base_name, subdirectory), paths in groups.items():
        image = Image(base_name=base_name, subdirectory=subdirectory)

        for file_path in paths:
            image_file = ImageFile.from_path(file_path, base_name)
            image.add_file(image_file)

        images.append(image)

    return images


def group_files_by_base_name(
    file_paths: List[Path],
) -> Dict[str, List[Path]]:
    """
    Group file paths by their base names (simple grouping).

    This is a simpler version that just groups files by base_name
    without creating full Image objects.

    Args:
        file_paths: List of paths to image files

    Returns:
        Dictionary mapping base_name to list of file paths
    """
    groups: Dict[str, List[Path]] = defaultdict(list)

    for file_path in file_paths:
        if not file_path.is_file():
            continue

        base_name, _ = extract_base_name(file_path.name)
        groups[base_name].append(file_path)

    return dict(groups)
