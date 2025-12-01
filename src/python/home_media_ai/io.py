"""I/O utilities for reading and writing media files.

This module provides helper functions for reading various image formats
and returning them as NumPy arrays with appropriate data types.
"""

from pathlib import Path
from typing import Union
import numpy as np
from PIL import Image

from .utils import infer_media_type_from_extension, get_all_supported_extensions


def normalize_to_uint8(img_array: np.ndarray) -> np.ndarray:
    """Convert image array to uint8 format for PIL/display compatibility.

    Handles various input dtypes:
    - uint8: returned as-is
    - uint16: scaled from 0-65535 to 0-255
    - float: assumed 0-1 range, scaled to 0-255

    Args:
        img_array: NumPy array of any supported dtype.

    Returns:
        NumPy array with dtype uint8.

    Example:
        >>> raw_img = read_image_as_array('photo.CR2')  # uint16
        >>> img_8bit = normalize_to_uint8(raw_img)
        >>> print(img_8bit.dtype)
        uint8
    """
    if img_array.dtype == np.uint8:
        return img_array
    elif img_array.dtype == np.uint16:
        return (img_array / 256).astype(np.uint8)
    elif img_array.dtype in (np.float32, np.float64):
        return (img_array * 255).clip(0, 255).astype(np.uint8)
    else:
        # Fallback: try to convert directly
        return img_array.astype(np.uint8)


def read_image_as_array(
    file_path: Union[str, Path],
    media_type: str = None
) -> np.ndarray:
    """Read an image file and return it as a NumPy array.

    Automatically determines the appropriate reader based on file extension
    or provided media type. Preserves the native data type of the image
    (e.g., uint8 for JPEGs, uint16 for some RAW formats).

    Args:
        file_path: Path to the image file to read.
        media_type: Optional media type hint (e.g., 'raw_image', 'jpeg').
                   If not provided, will be inferred from file extension.

    Returns:
        NumPy array containing the image data with native data type preserved.

    Raises:
        ValueError: If the file extension is not recognized or media type is invalid.
        FileNotFoundError: If the file does not exist.
        ImportError: If required library (rawpy) is not installed for RAW files.

    Examples:
        >>> # Read a JPEG (returns uint8 array)
        >>> img = read_image_as_array('photo.jpg')
        >>> print(img.shape, img.dtype)
        (3024, 4032, 3) uint8

        >>> # Read a RAW file (may return uint16 array)
        >>> raw_img = read_image_as_array('photo.CR2')
        >>> print(raw_img.shape, raw_img.dtype)
        (3024, 4032, 3) uint16

        >>> # Explicitly specify media type
        >>> img = read_image_as_array('photo.dng', media_type='raw_image')
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Determine media type from extension if not provided
    if media_type is None:
        media_type = infer_media_type_from_extension(file_path.suffix.lower())

    if media_type is None:
        raise ValueError(
            f"Unrecognized file extension: {file_path.suffix}. "
            f"Supported extensions: {get_all_supported_extensions()}"
        )

    # Use appropriate reader based on media type
    if media_type == 'raw_image':
        return _read_raw_image(file_path)
    else:
        # Use Pillow for all other image types (JPEG, PNG, TIFF, HEIC, etc.)
        return _read_standard_image(file_path)


def _read_standard_image(file_path: Path) -> np.ndarray:
    """Read standard image formats (JPEG, PNG, TIFF, HEIC) using Pillow.

    Args:
        file_path: Path to the image file.

    Returns:
        NumPy array with the native data type of the image.
    """
    with Image.open(file_path) as img:
        # Convert to RGB if needed (handles RGBA, grayscale, etc.)
        if img.mode not in ('RGB', 'L', 'I', 'I;16'):
            if img.mode == 'RGBA':
                # Keep alpha channel for RGBA images
                img = img
            elif img.mode in ('P', 'PA'):
                # Convert palette images to RGB/RGBA
                img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
            else:
                # Convert other modes to RGB
                img = img.convert('RGB')

        # Convert to numpy array, preserving the data type
        array = np.array(img)

    return array


def _read_raw_image(file_path: Path) -> np.ndarray:
    """Read RAW image formats (CR2, NEF, ARW, DNG) using rawpy.

    Args:
        file_path: Path to the RAW image file.

    Returns:
        NumPy array with the native data type (typically uint16).

    Raises:
        ImportError: If rawpy is not installed.
    """
    try:
        import rawpy
    except ImportError:
        raise ImportError(
            "rawpy is required to read RAW image files. "
            "Install it with: pip install rawpy"
        )

    with rawpy.imread(str(file_path)) as raw:
        # Use postprocess to get a processed RGB image
        # This returns a uint16 array by default for most RAW files
        rgb = raw.postprocess(
            use_camera_wb=True,      # Use camera white balance
            output_bps=16,           # Output 16-bit per channel
            no_auto_bright=False,    # Enable auto brightness
            gamma=(2.222, 4.5),      # Standard gamma correction
        )

    return rgb


def read_image_metadata(file_path: Union[str, Path]) -> dict:
    """Read basic image metadata without loading the full image.

    Args:
        file_path: Path to the image file.

    Returns:
        Dictionary containing basic metadata like width, height, format, mode.

    Example:
        >>> metadata = read_image_metadata('photo.jpg')
        >>> print(metadata)
        {'width': 4032, 'height': 3024, 'format': 'JPEG', 'mode': 'RGB'}
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with Image.open(file_path) as img:
        metadata = {
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'mode': img.mode,
        }

        # Add additional info if available
        if hasattr(img, 'info'):
            metadata['info'] = img.info

    return metadata
