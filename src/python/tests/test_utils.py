#!/usr/bin/env python3
"""
Unit tests for utils module.

Run with pytest:
    pytest tests/test_utils.py -v

Or with unittest:
    python -m unittest tests.test_utils
"""

import unittest
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.utils import (
    infer_media_type_from_extension,
    get_all_supported_extensions,
    calculate_file_hash,
    split_file_path,
    validate_file_extension,
    normalize_extension
)


class TestMediaTypeInference(unittest.TestCase):
    """Test media type inference from file extensions."""

    def test_infer_jpeg_extensions(self):
        """Test JPEG extension inference."""
        self.assertEqual(infer_media_type_from_extension('.jpg'), 'jpeg')
        self.assertEqual(infer_media_type_from_extension('.jpeg'), 'jpeg')
        self.assertEqual(infer_media_type_from_extension('.JPG'), 'jpeg')
        self.assertEqual(infer_media_type_from_extension('jpg'), 'jpeg')  # Without dot

    def test_infer_raw_extensions(self):
        """Test RAW image extension inference."""
        self.assertEqual(infer_media_type_from_extension('.dng'), 'raw_image')
        self.assertEqual(infer_media_type_from_extension('.cr2'), 'raw_image')
        self.assertEqual(infer_media_type_from_extension('.nef'), 'raw_image')
        self.assertEqual(infer_media_type_from_extension('.arw'), 'raw_image')
        self.assertEqual(infer_media_type_from_extension('.CR2'), 'raw_image')  # Case insensitive

    def test_infer_other_formats(self):
        """Test other image format inference."""
        self.assertEqual(infer_media_type_from_extension('.png'), 'png')
        self.assertEqual(infer_media_type_from_extension('.tif'), 'tiff')
        self.assertEqual(infer_media_type_from_extension('.tiff'), 'tiff')
        self.assertEqual(infer_media_type_from_extension('.heic'), 'heic')
        self.assertEqual(infer_media_type_from_extension('.heif'), 'heic')

    def test_infer_video_extensions(self):
        """Test video extension inference."""
        self.assertEqual(infer_media_type_from_extension('.mp4'), 'video')
        self.assertEqual(infer_media_type_from_extension('.mov'), 'video')
        self.assertEqual(infer_media_type_from_extension('.avi'), 'video')

    def test_infer_unknown_extension(self):
        """Test unknown extension returns None."""
        self.assertIsNone(infer_media_type_from_extension('.unknown'))
        self.assertIsNone(infer_media_type_from_extension('.txt'))
        self.assertIsNone(infer_media_type_from_extension('.pdf'))


class TestSupportedExtensions(unittest.TestCase):
    """Test supported extensions functionality."""

    def test_get_all_supported_extensions(self):
        """Test getting all supported extensions."""
        extensions = get_all_supported_extensions()

        self.assertIsInstance(extensions, set)
        self.assertGreater(len(extensions), 0)

        # Check some expected extensions are present
        self.assertIn('.jpg', extensions)
        self.assertIn('.dng', extensions)
        self.assertIn('.png', extensions)
        self.assertIn('.mp4', extensions)


class TestFileHashing(unittest.TestCase):
    """Test file hashing functionality."""

    def test_calculate_hash_simple_file(self):
        """Test hash calculation on a simple text file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write("test content")
            tmp_path = tmp.name

        try:
            hash_value = calculate_file_hash(tmp_path)

            # SHA-256 hash should be 64 characters (hex)
            self.assertEqual(len(hash_value), 64)
            self.assertTrue(all(c in '0123456789abcdef' for c in hash_value))

            # Same content should produce same hash
            hash_value2 = calculate_file_hash(tmp_path)
            self.assertEqual(hash_value, hash_value2)
        finally:
            Path(tmp_path).unlink()

    def test_calculate_hash_empty_file(self):
        """Test hash calculation on empty file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            hash_value = calculate_file_hash(tmp_path)

            # Empty file has a known SHA-256 hash
            expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            self.assertEqual(hash_value, expected)
        finally:
            Path(tmp_path).unlink()

    def test_calculate_hash_nonexistent_file(self):
        """Test hash calculation on nonexistent file raises error."""
        with self.assertRaises(OSError):
            calculate_file_hash("/nonexistent/file.txt")

    def test_calculate_hash_different_chunk_sizes(self):
        """Test hash calculation with different chunk sizes produces same result."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp:
            # Write some data larger than default chunk size
            tmp.write(b"x" * 10000)
            tmp_path = tmp.name

        try:
            hash1 = calculate_file_hash(tmp_path, chunk_size=1024)
            hash2 = calculate_file_hash(tmp_path, chunk_size=4096)
            hash3 = calculate_file_hash(tmp_path, chunk_size=8192)

            self.assertEqual(hash1, hash2)
            self.assertEqual(hash2, hash3)
        finally:
            Path(tmp_path).unlink()


class TestPathSplitting(unittest.TestCase):
    """Test file path splitting functionality."""

    def test_split_path_no_storage_root(self):
        """Test path splitting without storage root."""
        result = split_file_path('/volume1/photos/2024/January/IMG_001.jpg')

        storage_root, directory, filename = result
        self.assertIn('January', storage_root)  # Parent dir becomes storage root
        self.assertIsNone(directory)
        self.assertEqual(filename, 'IMG_001.jpg')

    def test_split_path_with_storage_root(self):
        """Test path splitting with storage root."""
        result = split_file_path(
            '/volume1/photos/2024/January/IMG_001.jpg',
            storage_root='/volume1/photos'
        )

        storage_root, directory, filename = result
        self.assertEqual(storage_root, '/volume1/photos')
        self.assertIn('January', directory)
        self.assertIn('2024', directory)
        self.assertEqual(filename, 'IMG_001.jpg')

    def test_split_path_file_not_under_storage_root(self):
        """Test path splitting when file is not under storage root."""
        result = split_file_path(
            '/other/path/IMG_001.jpg',
            storage_root='/volume1/photos'
        )

        storage_root, directory, filename = result
        self.assertIn('path', storage_root)  # Falls back to parent
        self.assertIsNone(directory)
        self.assertEqual(filename, 'IMG_001.jpg')

    def test_split_path_file_directly_in_storage_root(self):
        """Test path splitting when file is directly in storage root."""
        result = split_file_path(
            '/volume1/photos/IMG_001.jpg',
            storage_root='/volume1/photos'
        )

        storage_root, directory, filename = result
        self.assertEqual(storage_root, '/volume1/photos')
        self.assertIsNone(directory)  # No subdirectory
        self.assertEqual(filename, 'IMG_001.jpg')


class TestFileExtensionValidation(unittest.TestCase):
    """Test file extension validation."""

    def test_validate_supported_extensions(self):
        """Test validation of supported extensions."""
        self.assertTrue(validate_file_extension('photo.jpg'))
        self.assertTrue(validate_file_extension('photo.dng'))
        self.assertTrue(validate_file_extension('photo.png'))
        self.assertTrue(validate_file_extension('/path/to/photo.CR2'))

    def test_validate_unsupported_extensions(self):
        """Test validation of unsupported extensions."""
        self.assertFalse(validate_file_extension('document.pdf'))
        self.assertFalse(validate_file_extension('data.csv'))
        self.assertFalse(validate_file_extension('script.py'))

    def test_validate_unsupported_with_raise(self):
        """Test validation raises error for unsupported extensions."""
        with self.assertRaises(ValueError) as context:
            validate_file_extension('document.pdf', raise_on_unsupported=True)

        self.assertIn('.pdf', str(context.exception))
        self.assertIn('Unsupported', str(context.exception))


class TestExtensionNormalization(unittest.TestCase):
    """Test extension normalization."""

    def test_normalize_lowercase(self):
        """Test normalization converts to lowercase."""
        self.assertEqual(normalize_extension('JPG'), '.jpg')
        self.assertEqual(normalize_extension('CR2'), '.cr2')
        self.assertEqual(normalize_extension('PNG'), '.png')

    def test_normalize_adds_dot(self):
        """Test normalization adds leading dot."""
        self.assertEqual(normalize_extension('jpg'), '.jpg')
        self.assertEqual(normalize_extension('cr2'), '.cr2')

    def test_normalize_preserves_dot(self):
        """Test normalization preserves existing dot."""
        self.assertEqual(normalize_extension('.jpg'), '.jpg')
        self.assertEqual(normalize_extension('.CR2'), '.cr2')

    def test_normalize_various_cases(self):
        """Test normalization with various input formats."""
        self.assertEqual(normalize_extension('JpG'), '.jpg')
        self.assertEqual(normalize_extension('.JpG'), '.jpg')
        self.assertEqual(normalize_extension('JPEG'), '.jpeg')


if __name__ == '__main__':
    unittest.main()
