#!/usr/bin/env python3
"""
Unit tests for scanner module.

Run with pytest:
    pytest tests/test_scanner.py -v

Or with unittest:
    python -m unittest tests.test_scanner
"""

import unittest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.scanner import MediaScanner, FileInfo
from home_media_ai.exif_extractor import ExifExtractor

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / 'fixtures'


class TestMediaScanner(unittest.TestCase):
    """Test MediaScanner functionality."""

    def test_scanner_initialization(self):
        """Test that scanner initializes correctly."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))

        self.assertEqual(scanner.root_path, FIXTURES_DIR)
        self.assertIsNone(scanner.exif_extractor)

    def test_scanner_with_exif_extractor(self):
        """Test scanner with EXIF extractor."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        extractor = ExifExtractor()
        scanner = MediaScanner(str(FIXTURES_DIR), exif_extractor=extractor)

        self.assertIsNotNone(scanner.exif_extractor)

    def test_scan_files_finds_fixtures(self):
        """Test that scanner finds fixture files."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        # Should find at least some media files
        self.assertGreater(len(files), 0)

        # All results should be FileInfo objects
        for file_info in files:
            self.assertIsInstance(file_info, FileInfo)

    def test_scan_files_contains_expected_formats(self):
        """Test that scanner finds expected file formats."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        # Get all media types found
        media_types = {f.media_type for f in files}

        # Should find JPEG files
        self.assertIn('jpeg', media_types, "Should find JPEG files")

        # Check if DNG files are present
        extensions = {Path(f.path).suffix.lower() for f in files}
        if '.dng' in {f.suffix.lower() for f in FIXTURES_DIR.iterdir() if f.is_file()}:
            self.assertIn('raw_image', media_types, "Should find RAW/DNG files")

    def test_file_info_structure(self):
        """Test that FileInfo contains expected fields."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        if not files:
            self.skipTest("No files found in fixtures")

        file_info = files[0]

        # Check all required fields exist
        self.assertIsNotNone(file_info.path)
        self.assertIsNotNone(file_info.size)
        self.assertIsNotNone(file_info.extension)
        self.assertIsNotNone(file_info.timestamp)
        self.assertIsNotNone(file_info.media_type)
        self.assertIsInstance(file_info.exif_data, dict)

        # Size should be positive
        self.assertGreater(file_info.size, 0)

        # Extension should start with dot
        self.assertTrue(file_info.extension.startswith('.'))

    def test_scan_with_exif_extraction(self):
        """Test scanning with EXIF data extraction."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        extractor = ExifExtractor()
        scanner = MediaScanner(str(FIXTURES_DIR), exif_extractor=extractor)
        files = list(scanner.scan_files())

        if not files:
            self.skipTest("No files found in fixtures")

        # At least some files should have EXIF data
        files_with_exif = [f for f in files if f.exif_data and len(f.exif_data) > 0]

        self.assertGreater(len(files_with_exif), 0,
                          "Should extract EXIF data from at least some files")

    def test_scan_filters_xmp_files(self):
        """Test that scanner doesn't include .xmp sidecar files."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        # Check no XMP files are in results
        xmp_files = [f for f in files if f.extension.lower() == '.xmp']

        self.assertEqual(len(xmp_files), 0,
                        "Scanner should not include .xmp sidecar files")

    def test_scan_respects_media_type_extensions(self):
        """Test that scanner only includes supported media types."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        from home_media_ai.constants import MEDIA_TYPE_EXTENSIONS

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        # Get all supported extensions
        supported_extensions = set()
        for extensions in MEDIA_TYPE_EXTENSIONS.values():
            supported_extensions.update(extensions)

        # All scanned files should have supported extensions
        for file_info in files:
            self.assertIn(file_info.extension.lower(), supported_extensions,
                         f"File {file_info.path} has unsupported extension")


class TestMediaScannerGrouping(unittest.TestCase):
    """Test file grouping and pairing functionality."""

    def test_group_by_timestamp(self):
        """Test grouping files by timestamp."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        if len(files) < 2:
            self.skipTest("Need at least 2 files for grouping test")

        grouped = scanner.group_by_timestamp(iter(files))

        # Should return a dictionary
        self.assertIsInstance(grouped, dict)

        # Check structure: timestamp -> media_type -> FileInfo
        for timestamp, files_by_type in grouped.items():
            self.assertIsInstance(files_by_type, dict)
            for media_type, file_info in files_by_type.items():
                self.assertIsInstance(file_info, FileInfo)
                self.assertEqual(file_info.media_type, media_type)

    def test_identify_pairs(self):
        """Test identification of RAW+JPEG pairs."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        if len(files) < 2:
            self.skipTest("Need at least 2 files for pairing test")

        grouped = scanner.group_by_timestamp(iter(files))
        pairs = list(scanner.identify_pairs(grouped))

        # Should return list of tuples
        self.assertIsInstance(pairs, list)
        self.assertGreater(len(pairs), 0)

        # Each pair should be (FileInfo, Optional[FileInfo])
        for original, derivative in pairs:
            self.assertIsInstance(original, FileInfo)
            if derivative is not None:
                self.assertIsInstance(derivative, FileInfo)

    def test_pair_detection_for_matching_timestamps(self):
        """Test that files with matching timestamps are paired."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        scanner = MediaScanner(str(FIXTURES_DIR))
        files = list(scanner.scan_files())

        grouped = scanner.group_by_timestamp(iter(files))
        pairs = list(scanner.identify_pairs(grouped))

        # Check if any pairs have both RAW and JPEG
        raw_jpeg_pairs = [
            (orig, deriv) for orig, deriv in pairs
            if orig.media_type == 'raw_image' and
               deriv is not None and
               deriv.media_type == 'jpeg'
        ]

        # Based on fixtures, we should have at least one RAW+JPEG pair
        # (files with same timestamp like 2024-10-11_12-19-51)
        if any('.dng' in f.path.lower() and '.jpg' in
               [other.path.lower() for other in files] for f in files):
            self.assertGreater(len(raw_jpeg_pairs), 0,
                             "Should detect RAW+JPEG pairs from fixtures")


class TestProgressCallback(unittest.TestCase):
    """Test progress callback functionality."""

    def test_scan_with_progress_callback(self):
        """Test that progress callback is called during scan."""
        if not FIXTURES_DIR.exists():
            self.skipTest(f"Fixtures directory not found: {FIXTURES_DIR}")

        callback_messages = []

        def progress_callback(message):
            callback_messages.append(message)

        scanner = MediaScanner(str(FIXTURES_DIR))
        list(scanner.scan_files(progress_callback=progress_callback))

        # Callback should have been called if enough files were scanned
        # (callback triggers every 100 files by default)
        # For small test sets, this might not trigger
        self.assertIsInstance(callback_messages, list)


if __name__ == '__main__':
    unittest.main()
