"""
File utilities for Home Media AI.

This module provides utilities for working with media files, including
file type detection, metadata extraction, and file system operations.

Functions:
    get_file_info: Extract comprehensive file information
    is_image_file: Check if file is a supported image format
    is_video_file: Check if file is a supported video format
    create_directory: Safely create directories
    safe_filename: Generate safe filenames for cross-platform compatibility
    format_file_size: Format file sizes in human-readable format
    setup_temp_directory: Set up temporary directory for processing
    
Example:
    >>> from home_media_ai.utils import get_file_info, is_image_file
    >>> info = get_file_info('/path/to/image.jpg')
    >>> if is_image_file('/path/to/file.jpg'):
    ...     print("This is an image file")
"""

import os
import re
import magic
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from datetime import datetime
import logging

try:
    import exifread
    EXIF_AVAILABLE = True
except ImportError:
    EXIF_AVAILABLE = False
    logging.warning("exifread not available, EXIF data extraction disabled")

logger = logging.getLogger(__name__)

# Supported file formats
SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', 
    '.webp', '.ico', '.psd', '.raw', '.cr2', '.nef', '.arw'
}

SUPPORTED_VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', 
    '.m4v', '.3gp', '.mpg', '.mpeg', '.m2v', '.mts', '.mxf'
}


def get_file_info(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Extract comprehensive information about a file.
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        Dictionary containing file information including:
        - Basic info: size, modified time, created time
        - File type and MIME type
        - Hash (MD5) for duplicate detection
        - EXIF data for images (if available)
        
    Example:
        >>> info = get_file_info('/path/to/image.jpg')
        >>> print(f"File size: {info['size_bytes']} bytes")
        >>> print(f"Created: {info['created']}")
        >>> if 'exif' in info:
        ...     print(f"Camera: {info['exif'].get('camera_make', 'Unknown')}")
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    stat = file_path.stat()
    
    # Basic file information
    info = {
        'path': str(file_path.absolute()),
        'filename': file_path.name,
        'extension': file_path.suffix.lower(),
        'size_bytes': stat.st_size,
        'size_human': format_file_size(stat.st_size),
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'created': datetime.fromtimestamp(stat.st_ctime),
    }
    
    # File type detection
    try:
        mime_type = magic.from_file(str(file_path), mime=True)
        info['mime_type'] = mime_type
        info['is_image'] = is_image_file(file_path)
        info['is_video'] = is_video_file(file_path)
    except Exception as e:
        logger.warning(f"Could not determine MIME type for {file_path}: {e}")
        info['mime_type'] = 'unknown'
        info['is_image'] = info['extension'] in SUPPORTED_IMAGE_EXTENSIONS
        info['is_video'] = info['extension'] in SUPPORTED_VIDEO_EXTENSIONS
    
    # Calculate file hash for duplicate detection
    try:
        info['md5_hash'] = _calculate_file_hash(file_path)
    except Exception as e:
        logger.warning(f"Could not calculate hash for {file_path}: {e}")
        info['md5_hash'] = None
    
    # Extract EXIF data for images
    if info['is_image'] and EXIF_AVAILABLE:
        try:
            info['exif'] = _extract_exif_data(file_path)
        except Exception as e:
            logger.debug(f"Could not extract EXIF data from {file_path}: {e}")
            info['exif'] = {}
    
    return info


def is_image_file(file_path: Union[str, Path]) -> bool:
    """Check if a file is a supported image format.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is a supported image format
        
    Example:
        >>> if is_image_file('/path/to/photo.jpg'):
        ...     print("This is an image file")
    """
    extension = Path(file_path).suffix.lower()
    return extension in SUPPORTED_IMAGE_EXTENSIONS


def is_video_file(file_path: Union[str, Path]) -> bool:
    """Check if a file is a supported video format.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is a supported video format
        
    Example:
        >>> if is_video_file('/path/to/video.mp4'):
        ...     print("This is a video file")
    """
    extension = Path(file_path).suffix.lower()
    return extension in SUPPORTED_VIDEO_EXTENSIONS


def create_directory(path: Union[str, Path], exist_ok: bool = True) -> Path:
    """Safely create a directory and its parents.
    
    Args:
        path: Directory path to create
        exist_ok: Whether to raise exception if directory exists
        
    Returns:
        Path object for the created directory
        
    Example:
        >>> output_dir = create_directory('/path/to/output')
        >>> print(f"Created directory: {output_dir}")
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=exist_ok)
    return path


def safe_filename(filename: str, replacement: str = '_') -> str:
    """Generate a safe filename for cross-platform compatibility.
    
    Args:
        filename: Original filename
        replacement: Character to replace unsafe characters with
        
    Returns:
        Safe filename string
        
    Example:
        >>> safe_name = safe_filename('My File: Copy (2).jpg')
        >>> print(safe_name)  # 'My_File__Copy__2_.jpg'
    """
    # Remove or replace characters that are problematic on various filesystems
    unsafe_chars = r'[<>:"/\\|?*\x00-\x1f]'
    safe_name = re.sub(unsafe_chars, replacement, filename)
    
    # Remove trailing dots and spaces (problematic on Windows)
    safe_name = safe_name.rstrip('. ')
    
    # Ensure filename is not empty
    if not safe_name:
        safe_name = 'unnamed_file'
    
    return safe_name


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Human-readable size string (e.g., '1.5 MB', '2.3 GB')
        
    Example:
        >>> size = format_file_size(1536000)
        >>> print(size)  # '1.5 MB'
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def setup_temp_directory(base_path: Optional[Union[str, Path]] = None) -> Path:
    """Set up a temporary directory for processing.
    
    Args:
        base_path: Base path for temporary directory (uses system temp if None)
        
    Returns:
        Path to created temporary directory
        
    Example:
        >>> temp_dir = setup_temp_directory()
        >>> print(f"Temporary directory: {temp_dir}")
    """
    import tempfile
    
    if base_path:
        base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)
        temp_dir = base_path / 'home_media_ai_temp'
    else:
        temp_dir = Path(tempfile.gettempdir()) / 'home_media_ai'
    
    create_directory(temp_dir)
    return temp_dir


def find_media_files(
    directory: Union[str, Path], 
    recursive: bool = True,
    include_images: bool = True,
    include_videos: bool = True
) -> List[Path]:
    """Find all media files in a directory.
    
    Args:
        directory: Directory to search
        recursive: Whether to search subdirectories
        include_images: Whether to include image files
        include_videos: Whether to include video files
        
    Returns:
        List of Path objects for found media files
        
    Example:
        >>> files = find_media_files('/path/to/photos', recursive=True)
        >>> print(f"Found {len(files)} media files")
    """
    directory = Path(directory)
    media_files = []
    
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    extensions = set()
    if include_images:
        extensions.update(SUPPORTED_IMAGE_EXTENSIONS)
    if include_videos:
        extensions.update(SUPPORTED_VIDEO_EXTENSIONS)
    
    search_pattern = "**/*" if recursive else "*"
    
    for file_path in directory.glob(search_pattern):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            media_files.append(file_path)
    
    return sorted(media_files)


def _calculate_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
    """Calculate MD5 hash of a file.
    
    Args:
        file_path: Path to file
        chunk_size: Size of chunks to read at a time
        
    Returns:
        MD5 hash as hexadecimal string
    """
    md5_hash = hashlib.md5()
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            md5_hash.update(chunk)
    
    return md5_hash.hexdigest()


def _extract_exif_data(file_path: Path) -> Dict[str, Any]:
    """Extract EXIF data from an image file.
    
    Args:
        file_path: Path to image file
        
    Returns:
        Dictionary containing EXIF data
    """
    if not EXIF_AVAILABLE:
        return {}
    
    exif_data = {}
    
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            
            # Extract common EXIF fields
            exif_mapping = {
                'camera_make': 'Image Make',
                'camera_model': 'Image Model',
                'datetime': 'EXIF DateTimeOriginal',
                'orientation': 'Image Orientation',
                'flash': 'EXIF Flash',
                'focal_length': 'EXIF FocalLength',
                'aperture': 'EXIF FNumber',
                'iso': 'EXIF ISOSpeedRatings',
                'exposure_time': 'EXIF ExposureTime',
                'gps_latitude': 'GPS GPSLatitude',
                'gps_longitude': 'GPS GPSLongitude',
            }
            
            for key, exif_key in exif_mapping.items():
                if exif_key in tags:
                    exif_data[key] = str(tags[exif_key])
    
    except Exception as e:
        logger.debug(f"Error extracting EXIF data: {e}")
    
    return exif_data