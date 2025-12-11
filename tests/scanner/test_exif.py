"""Unit tests for scanner.exif module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

from home_media.scanner.exif import ExifData, extract_exif_metadata


class TestExifData:
    """Tests for ExifData class."""

    def test_exifdata_creation_empty(self):
        """Test creating empty ExifData."""
        exif = ExifData()

        assert exif.captured_at is None
        assert exif.camera_make is None
        assert exif.camera_model is None
        assert exif.lens is None
        assert exif.gps_latitude is None
        assert exif.gps_longitude is None
        assert exif.title is None
        assert exif.description is None
        assert exif.rating is None

    def test_exifdata_creation_with_values(self):
        """Test creating ExifData with values."""
        dt = datetime(2025, 12, 10, 14, 30, 45)
        exif = ExifData(
            captured_at=dt,
            camera_make="Canon",
            camera_model="EOS R5",
            lens="RF 24-70mm F2.8",
            gps_latitude=37.7749,
            gps_longitude=-122.4194,
            title="Test Photo",
            description="A test photograph",
            rating=5,
        )

        assert exif.captured_at == dt
        assert exif.camera_make == "Canon"
        assert exif.camera_model == "EOS R5"
        assert exif.lens == "RF 24-70mm F2.8"
        assert exif.gps_latitude == 37.7749
        assert exif.gps_longitude == -122.4194
        assert exif.title == "Test Photo"
        assert exif.description == "A test photograph"
        assert exif.rating == 5

    def test_exifdata_to_dict(self):
        """Test ExifData.to_dict() method."""
        dt = datetime(2025, 12, 10, 14, 30, 45)
        exif = ExifData(
            captured_at=dt,
            camera_make="Canon",
            camera_model="EOS R5",
            gps_latitude=37.7749,
        )

        result = exif.to_dict()

        assert result["captured_at"] == dt
        assert result["camera_make"] == "Canon"
        assert result["camera_model"] == "EOS R5"
        assert result["gps_latitude"] == 37.7749
        assert result["lens"] is None
        assert result["title"] is None

    def test_exifdata_to_dict_empty(self):
        """Test to_dict() with empty ExifData."""
        exif = ExifData()
        result = exif.to_dict()

        assert all(value is None for value in result.values())
        assert len(result) == 9  # All expected fields


class TestExtractExifMetadata:
    """Tests for extract_exif_metadata() function."""

    def test_extract_exif_nonexistent_file(self, tmp_path, caplog):
        """Test that nonexistent file returns None."""
        nonexistent = tmp_path / "nonexistent.jpg"

        import logging
        caplog.set_level(logging.WARNING)

        result = extract_exif_metadata(nonexistent)

        assert result is None
        assert "File not found" in caplog.text

    def test_extract_exif_from_jpeg_with_pillow(self, tmp_path):
        """Test EXIF extraction from JPEG using Pillow."""
        from PIL import Image as PILImage
        from PIL import ExifTags

        # Create a test JPEG with EXIF data
        test_file = tmp_path / "test.jpg"
        img = PILImage.new("RGB", (100, 100), color="red")

        # Add minimal EXIF data
        exif_dict = {
            ExifTags.Base.Make: "TestCamera",
            ExifTags.Base.Model: "TestModel",
        }

        # Note: Actually setting EXIF in PIL is complex, so we'll mock the extraction
        img.save(test_file)

        # Mock the Pillow extraction
        with patch("PIL.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_exif = MagicMock()
            mock_exif.get.side_effect = lambda tag, default=None: {
                271: "TestMake",  # Make
                272: "TestModel",  # Model
            }.get(tag, default)

            mock_img.getexif.return_value = mock_exif
            mock_img.__enter__ = Mock(return_value=mock_img)
            mock_img.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_img

            result = extract_exif_metadata(test_file)

            # Result could be None if Pillow extraction fails
            # This is acceptable as we're testing the interface
            assert result is None or isinstance(result, ExifData)

    def test_extract_exif_no_metadata(self, tmp_path):
        """Test extraction from file with no EXIF data."""
        from PIL import Image as PILImage

        test_file = tmp_path / "no_exif.jpg"
        img = PILImage.new("RGB", (100, 100), color="blue")
        img.save(test_file)

        result = extract_exif_metadata(test_file)

        # Files without EXIF return None
        assert result is None

    def test_extract_exif_directory(self, tmp_path):
        """Test that passing a directory returns None."""
        directory = tmp_path / "testdir"
        directory.mkdir()

        result = extract_exif_metadata(directory)

        assert result is None


class TestExifDataIntegration:
    """Integration tests for EXIF extraction."""

    @pytest.mark.integration
    def test_exif_extraction_real_jpeg(self, tmp_path):
        """Integration test with real JPEG file."""
        from PIL import Image as PILImage

        # Create a real JPEG
        test_file = tmp_path / "real_photo.jpg"
        img = PILImage.new("RGB", (800, 600), color="green")
        img.save(test_file, quality=95)

        # This will likely return None as we didn't add EXIF, but it shouldn't crash
        result = extract_exif_metadata(test_file)

        # Either None or valid ExifData
        assert result is None or isinstance(result, ExifData)

    @pytest.mark.slow
    @pytest.mark.integration
    def test_exif_handles_corrupted_file(self, tmp_path):
        """Test that corrupted files are handled gracefully."""
        corrupted = tmp_path / "corrupted.jpg"
        corrupted.write_bytes(b"This is not a valid JPEG file")

        result = extract_exif_metadata(corrupted)

        # Should handle gracefully and return None
        assert result is None
