#!/usr/bin/env python3
"""
Unit tests for io module.

Run with pytest:
    pytest tests/test_io.py -v

Or with unittest:
    python -m unittest tests.test_io
"""

import unittest
import tempfile
from pathlib import Path
import sys
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.io import read_image_as_array, read_image_metadata

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestReadImageAsArray(unittest.TestCase):
    """Test reading images as NumPy arrays."""

    def test_read_jpeg_fixture(self):
        """Test reading JPEG fixture file."""
        jpeg_path = FIXTURES_DIR / '2024-10-11_12-19-49.jpg'

        if not jpeg_path.exists():
            self.skipTest(f"Fixture not found: {jpeg_path}")

        img_array = read_image_as_array(jpeg_path)

        # Verify it's a numpy array
        self.assertIsInstance(img_array, np.ndarray)

        # JPEG should be uint8
        self.assertEqual(img_array.dtype, np.uint8)

        # Should have 3 dimensions (height, width, channels) or 2 (grayscale)
        self.assertIn(len(img_array.shape), [2, 3])

        # If RGB, should have 3 channels
        if len(img_array.shape) == 3:
            self.assertEqual(img_array.shape[2], 3)

        # Should have reasonable dimensions (not 0x0)
        self.assertGreater(img_array.shape[0], 0)
        self.assertGreater(img_array.shape[1], 0)

    def test_read_dng_fixture(self):
        """Test reading DNG RAW fixture file."""
        dng_path = FIXTURES_DIR / '2024-10-11_12-19-50.dng'

        if not dng_path.exists():
            self.skipTest(f"Fixture not found: {dng_path}")

        # Check if rawpy is available
        try:
            import rawpy
        except ImportError:
            self.skipTest("rawpy not installed")

        img_array = read_image_as_array(dng_path)

        # Verify it's a numpy array
        self.assertIsInstance(img_array, np.ndarray)

        # RAW files processed by rawpy should be uint16
        self.assertEqual(img_array.dtype, np.uint16)

        # Should have 3 dimensions (RGB)
        self.assertEqual(len(img_array.shape), 3)
        self.assertEqual(img_array.shape[2], 3)

        # Should have reasonable dimensions
        self.assertGreater(img_array.shape[0], 0)
        self.assertGreater(img_array.shape[1], 0)

    def test_read_dng_explicit_media_type(self):
        """Test reading DNG with explicit media type."""
        dng_path = FIXTURES_DIR / '2024-10-11_12-19-51.dng'

        if not dng_path.exists():
            self.skipTest(f"Fixture not found: {dng_path}")

        try:
            import rawpy
        except ImportError:
            self.skipTest("rawpy not installed")

        img_array = read_image_as_array(dng_path, media_type='raw_image')

        self.assertIsInstance(img_array, np.ndarray)
        self.assertEqual(img_array.dtype, np.uint16)

    def test_read_jpeg_with_explicit_media_type(self):
        """Test reading JPEG with explicit media type."""
        jpeg_path = FIXTURES_DIR / '2024-10-11_12-19-51.jpg'

        if not jpeg_path.exists():
            self.skipTest(f"Fixture not found: {jpeg_path}")

        img_array = read_image_as_array(jpeg_path, media_type='jpeg')

        self.assertIsInstance(img_array, np.ndarray)
        self.assertEqual(img_array.dtype, np.uint8)

    def test_read_nonexistent_file(self):
        """Test reading nonexistent file raises error."""
        with self.assertRaises(FileNotFoundError):
            read_image_as_array('/nonexistent/file.jpg')

    def test_read_unsupported_extension(self):
        """Test reading file with unsupported extension raises error."""
        # Create temporary file with unsupported extension
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp:
            tmp.write(b"not an image")
            tmp_path = tmp.name

        try:
            with self.assertRaises(ValueError) as context:
                read_image_as_array(tmp_path)

            self.assertIn('Unrecognized', str(context.exception))
        finally:
            Path(tmp_path).unlink()

    def test_same_image_different_formats_similar_shape(self):
        """Test that JPEG and DNG of same scene have similar dimensions."""
        # These fixtures should be pairs from the same scene
        jpeg_path = FIXTURES_DIR / '2024-10-11_12-19-51.jpg'
        dng_path = FIXTURES_DIR / '2024-10-11_12-19-51.dng'

        if not jpeg_path.exists() or not dng_path.exists():
            self.skipTest("Fixture pair not found")

        try:
            import rawpy
        except ImportError:
            self.skipTest("rawpy not installed")

        jpeg_array = read_image_as_array(jpeg_path)
        dng_array = read_image_as_array(dng_path)

        # They should have same height and width (or very close)
        # Allow some variation due to processing
        height_diff = abs(jpeg_array.shape[0] - dng_array.shape[0])
        width_diff = abs(jpeg_array.shape[1] - dng_array.shape[1])

        self.assertLess(height_diff, 100, "Heights should be similar")
        self.assertLess(width_diff, 100, "Widths should be similar")


class TestReadImageMetadata(unittest.TestCase):
    """Test reading image metadata."""

    def test_read_jpeg_metadata(self):
        """Test reading metadata from JPEG fixture."""
        jpeg_path = FIXTURES_DIR / '2024-10-11_12-19-49.jpg'

        if not jpeg_path.exists():
            self.skipTest(f"Fixture not found: {jpeg_path}")

        metadata = read_image_metadata(jpeg_path)

        # Should return a dictionary
        self.assertIsInstance(metadata, dict)

        # Should have basic metadata fields
        self.assertIn('width', metadata)
        self.assertIn('height', metadata)
        self.assertIn('format', metadata)
        self.assertIn('mode', metadata)

        # Width and height should be positive
        self.assertGreater(metadata['width'], 0)
        self.assertGreater(metadata['height'], 0)

        # Format should be JPEG
        self.assertEqual(metadata['format'], 'JPEG')

    def test_read_dng_metadata(self):
        """Test reading metadata from DNG fixture."""
        dng_path = FIXTURES_DIR / '2024-10-11_12-19-50.dng'

        if not dng_path.exists():
            self.skipTest(f"Fixture not found: {dng_path}")

        metadata = read_image_metadata(dng_path)

        # Should return a dictionary
        self.assertIsInstance(metadata, dict)

        # Should have basic metadata fields
        self.assertIn('width', metadata)
        self.assertIn('height', metadata)
        self.assertIn('format', metadata)

        # Width and height should be positive
        self.assertGreater(metadata['width'], 0)
        self.assertGreater(metadata['height'], 0)

    def test_metadata_nonexistent_file(self):
        """Test reading metadata from nonexistent file raises error."""
        with self.assertRaises(FileNotFoundError):
            read_image_metadata('/nonexistent/file.jpg')

    def test_metadata_faster_than_full_read(self):
        """Test that metadata reading is faster than full image read."""
        import time

        jpeg_path = FIXTURES_DIR / '2024-10-11_12-19-49.jpg'

        if not jpeg_path.exists():
            self.skipTest(f"Fixture not found: {jpeg_path}")

        # Time metadata reading
        start = time.time()
        read_image_metadata(jpeg_path)
        metadata_time = time.time() - start

        # Time full image reading
        start = time.time()
        read_image_as_array(jpeg_path)
        full_read_time = time.time() - start

        # Metadata should be significantly faster
        # (at least 2x faster for large images)
        self.assertLess(metadata_time * 2, full_read_time,
                       "Metadata reading should be faster than full read")


class TestImageDataTypes(unittest.TestCase):
    """Test that different image formats preserve appropriate data types."""

    def test_jpeg_returns_uint8(self):
        """Test that JPEG images return uint8 arrays."""
        jpeg_path = FIXTURES_DIR / '2024-10-11_12-19-49.jpg'

        if not jpeg_path.exists():
            self.skipTest(f"Fixture not found: {jpeg_path}")

        img_array = read_image_as_array(jpeg_path)

        # JPEG should always be uint8
        self.assertEqual(img_array.dtype, np.uint8)

        # Values should be in valid range [0, 255]
        self.assertGreaterEqual(img_array.min(), 0)
        self.assertLessEqual(img_array.max(), 255)

    def test_raw_returns_uint16(self):
        """Test that RAW images return uint16 arrays."""
        dng_path = FIXTURES_DIR / '2024-10-11_12-19-50.dng'

        if not dng_path.exists():
            self.skipTest(f"Fixture not found: {dng_path}")

        try:
            import rawpy
        except ImportError:
            self.skipTest("rawpy not installed")

        img_array = read_image_as_array(dng_path)

        # RAW should be uint16
        self.assertEqual(img_array.dtype, np.uint16)

        # Values should be in valid range [0, 65535]
        self.assertGreaterEqual(img_array.min(), 0)
        self.assertLessEqual(img_array.max(), 65535)

    def test_data_range_utilization(self):
        """Test that images utilize a reasonable portion of their data range."""
        jpeg_path = FIXTURES_DIR / '2024-10-11_12-19-49.jpg'

        if not jpeg_path.exists():
            self.skipTest(f"Fixture not found: {jpeg_path}")

        img_array = read_image_as_array(jpeg_path)

        # For a real photo, we expect to use more than just a tiny range
        # (e.g., not all values between 0-10)
        value_range = img_array.max() - img_array.min()
        self.assertGreater(value_range, 50,
                          "Image should use a reasonable portion of value range")


class TestMediaIntegration(unittest.TestCase):
    """Test integration with Media class."""

    def test_media_read_as_array_method_exists(self):
        """Test that Media class has read_as_array method."""
        from home_media_ai import Media

        self.assertTrue(hasattr(Media, 'read_as_array'))
        self.assertTrue(callable(getattr(Media, 'read_as_array')))


if __name__ == '__main__':
    unittest.main()
