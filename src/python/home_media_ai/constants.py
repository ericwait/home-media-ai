"""Shared constants for the home_media_ai package.

This module contains common definitions used across multiple modules
to maintain consistency and avoid duplication.
"""

# Media type extension mappings
# Used by scanner, exif_extractor, and other modules
MEDIA_TYPE_EXTENSIONS = {
    'raw_image': {'.dng', '.cr2', '.nef', '.arw'},
    'jpeg': {'.jpg', '.jpeg'},
    'png': {'.png'},
    'tiff': {'.tif', '.tiff'},
    'heic': {'.heic', '.heif'},
    'video': {'.mp4', '.mov', '.avi'}
}

# Convenience access to RAW extensions only
RAW_EXTENSIONS = MEDIA_TYPE_EXTENSIONS['raw_image']
