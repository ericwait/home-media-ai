"""Unit tests for FileFormat and FileRole enums."""

import pytest

from home_media.models import FileFormat, FileRole


class TestFileRole:
    """Tests for the FileRole enum."""

    def test_file_role_values(self):
        """Test that all FileRole values exist."""
        assert FileRole.ORIGINAL
        assert FileRole.COVER
        assert FileRole.SIDECAR
        assert FileRole.EXPORT
        assert FileRole.DERIVATIVE
        assert FileRole.UNKNOWN

    def test_file_role_count(self):
        """Test the expected number of FileRole values."""
        assert len(FileRole) == 6


class TestFileFormat:
    """Tests for the FileFormat enum."""

    def test_raw_formats_exist(self):
        """Test that all RAW formats are defined."""
        raw_formats = [
            FileFormat.CR2, FileFormat.CR3, FileFormat.NEF,
            FileFormat.ARW, FileFormat.DNG, FileFormat.RAF,
            FileFormat.ORF, FileFormat.RW2
        ]
        for fmt in raw_formats:
            assert fmt

    def test_standard_formats_exist(self):
        """Test that standard image formats are defined."""
        standard_formats = [
            FileFormat.JPEG, FileFormat.PNG, FileFormat.TIFF,
            FileFormat.HEIC, FileFormat.HEIF, FileFormat.WEBP
        ]
        for fmt in standard_formats:
            assert fmt

    def test_sidecar_formats_exist(self):
        """Test that sidecar formats are defined."""
        assert FileFormat.XMP
        assert FileFormat.THM

    def test_video_formats_exist(self):
        """Test that video formats are defined."""
        assert FileFormat.MP4
        assert FileFormat.MOV
        assert FileFormat.AVI

    def test_unknown_format_exists(self):
        """Test that UNKNOWN format exists."""
        assert FileFormat.UNKNOWN


class TestFileFormatFromExtension:
    """Tests for FileFormat.from_extension() method."""

    @pytest.mark.parametrize("extension,expected", [
        ("jpg", FileFormat.JPEG),
        ("jpeg", FileFormat.JPEG),
        (".jpg", FileFormat.JPEG),
        (".jpeg", FileFormat.JPEG),
        ("JPG", FileFormat.JPEG),
        ("JPEG", FileFormat.JPEG),
    ])
    def test_jpeg_variations(self, extension, expected):
        """Test JPEG extension variations are all recognized."""
        assert FileFormat.from_extension(extension) == expected

    @pytest.mark.parametrize("extension,expected", [
        ("tif", FileFormat.TIFF),
        ("tiff", FileFormat.TIFF),
        (".tif", FileFormat.TIFF),
        (".tiff", FileFormat.TIFF),
    ])
    def test_tiff_variations(self, extension, expected):
        """Test TIFF extension variations are recognized."""
        assert FileFormat.from_extension(extension) == expected

    @pytest.mark.parametrize("extension,expected", [
        ("cr2", FileFormat.CR2),
        ("CR2", FileFormat.CR2),
        (".cr2", FileFormat.CR2),
        ("cr3", FileFormat.CR3),
        ("nef", FileFormat.NEF),
        ("arw", FileFormat.ARW),
        ("dng", FileFormat.DNG),
        ("raf", FileFormat.RAF),
        ("orf", FileFormat.ORF),
        ("rw2", FileFormat.RW2),
    ])
    def test_raw_formats(self, extension, expected):
        """Test RAW format extensions are recognized."""
        assert FileFormat.from_extension(extension) == expected

    @pytest.mark.parametrize("extension,expected", [
        ("png", FileFormat.PNG),
        ("heic", FileFormat.HEIC),
        ("heif", FileFormat.HEIF),
        ("webp", FileFormat.WEBP),
    ])
    def test_standard_formats(self, extension, expected):
        """Test standard image format extensions."""
        assert FileFormat.from_extension(extension) == expected

    @pytest.mark.parametrize("extension,expected", [
        ("xmp", FileFormat.XMP),
        ("thm", FileFormat.THM),
    ])
    def test_sidecar_formats(self, extension, expected):
        """Test sidecar format extensions."""
        assert FileFormat.from_extension(extension) == expected

    @pytest.mark.parametrize("extension,expected", [
        ("mp4", FileFormat.MP4),
        ("mov", FileFormat.MOV),
        ("avi", FileFormat.AVI),
    ])
    def test_video_formats(self, extension, expected):
        """Test video format extensions."""
        assert FileFormat.from_extension(extension) == expected

    @pytest.mark.parametrize("extension", [
        "txt", "pdf", "doc", "unknown", "xyz", "",
    ])
    def test_unknown_extensions(self, extension):
        """Test that unknown extensions return UNKNOWN."""
        assert FileFormat.from_extension(extension) == FileFormat.UNKNOWN


class TestFileFormatFromFilename:
    """Tests for FileFormat.from_filename() method."""

    @pytest.mark.parametrize("filename,expected", [
        ("photo.jpg", FileFormat.JPEG),
        ("image.CR2", FileFormat.CR2),
        ("/path/to/photo.jpg", FileFormat.JPEG),
        ("/photos/2025/01/IMG_1234.CR2", FileFormat.CR2),
        ("sidecar.xmp", FileFormat.XMP),
        ("thumbnail.thm", FileFormat.THM),
        ("video.mp4", FileFormat.MP4),
        ("C:\\Windows\\path\\photo.NEF", FileFormat.NEF),
    ])
    def test_from_filename(self, filename, expected):
        """Test FileFormat detection from various filename formats."""
        assert FileFormat.from_filename(filename) == expected

    def test_from_filename_no_extension(self):
        """Test filename without extension returns UNKNOWN."""
        assert FileFormat.from_filename("no_extension") == FileFormat.UNKNOWN


class TestFileFormatProperties:
    """Tests for FileFormat property methods."""

    @pytest.mark.parametrize("fmt", [
        FileFormat.CR2, FileFormat.CR3, FileFormat.NEF,
        FileFormat.ARW, FileFormat.DNG, FileFormat.RAF,
        FileFormat.ORF, FileFormat.RW2, FileFormat.TIFF
    ])
    def test_is_raw_true(self, fmt):
        """Test is_raw property returns True for RAW formats."""
        assert fmt.is_raw is True

    @pytest.mark.parametrize("fmt", [
        FileFormat.JPEG, FileFormat.PNG, FileFormat.HEIC,
        FileFormat.XMP, FileFormat.MP4, FileFormat.UNKNOWN
    ])
    def test_is_raw_false(self, fmt):
        """Test is_raw property returns False for non-RAW formats."""
        assert fmt.is_raw is False

    @pytest.mark.parametrize("fmt", [
        FileFormat.JPEG, FileFormat.PNG,
        FileFormat.HEIC, FileFormat.HEIF, FileFormat.WEBP,
        # RAW formats are also images
        FileFormat.CR2, FileFormat.NEF, FileFormat.DNG
    ])
    def test_is_image_true(self, fmt):
        """Test is_image property returns True for image formats."""
        assert fmt.is_image is True

    @pytest.mark.parametrize("fmt", [
        FileFormat.XMP, FileFormat.THM,
        FileFormat.MP4, FileFormat.MOV,
        FileFormat.UNKNOWN
    ])
    def test_is_image_false(self, fmt):
        """Test is_image property returns False for non-image formats."""
        assert fmt.is_image is False

    @pytest.mark.parametrize("fmt", [
        FileFormat.XMP, FileFormat.THM
    ])
    def test_is_sidecar_true(self, fmt):
        """Test is_sidecar property returns True for sidecar formats."""
        assert fmt.is_sidecar is True

    @pytest.mark.parametrize("fmt", [
        FileFormat.JPEG, FileFormat.CR2, FileFormat.MP4, FileFormat.UNKNOWN
    ])
    def test_is_sidecar_false(self, fmt):
        """Test is_sidecar property returns False for non-sidecar formats."""
        assert fmt.is_sidecar is False

    @pytest.mark.parametrize("fmt", [
        FileFormat.MP4, FileFormat.MOV, FileFormat.AVI
    ])
    def test_is_video_true(self, fmt):
        """Test is_video property returns True for video formats."""
        assert fmt.is_video is True

    @pytest.mark.parametrize("fmt", [
        FileFormat.JPEG, FileFormat.CR2, FileFormat.XMP, FileFormat.UNKNOWN
    ])
    def test_is_video_false(self, fmt):
        """Test is_video property returns False for non-video formats."""
        assert fmt.is_video is False
