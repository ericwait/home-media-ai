"""Unit tests for scanner.patterns module."""

import pytest

from home_media.scanner.patterns import (
    extract_base_name,
    get_all_extensions,
    get_final_extension,
    is_image_file,
    is_raw_file,
    is_sidecar_file,
)


class TestExtractBaseName:
    """Tests for extract_base_name() function."""

    @pytest.mark.parametrize("filename,expected_base,expected_suffix", [
        # Simple cases
        ("photo.jpg", "photo", ".jpg"),
        ("image.CR2", "image", ".CR2"),
        ("file.png", "file", ".png"),

        # Standard datetime patterns
        ("2025-01-01_00-28-40.jpg", "2025-01-01_00-28-40", ".jpg"),
        ("2025-01-01_00-28-40.CR3", "2025-01-01_00-28-40", ".CR3"),

        # Numbered derivatives
        ("2025-01-01_00-28-40_001.jpg", "2025-01-01_00-28-40", "_001.jpg"),
        ("2025-01-01_00-28-40_002.jpg", "2025-01-01_00-28-40", "_002.jpg"),
        ("photo_001.jpg", "photo", "_001.jpg"),
        ("photo_999.jpg", "photo", "_999.jpg"),

        # XMP sidecars (multi-extension)
        ("photo.jpg.xmp", "photo", ".jpg.xmp"),
        ("image.CR2.xmp", "image", ".CR2.xmp"),
        ("2025-01-01_00-28-40.jpg.xmp", "2025-01-01_00-28-40", ".jpg.xmp"),

        # Google Pixel RAW patterns
        ("PXL_20251210_200246684.RAW-01.COVER.jpg", "PXL_20251210_200246684", ".RAW-01.COVER.jpg"),
        ("PXL_20251210_200246684.RAW-02.ORIGINAL.dng", "PXL_20251210_200246684", ".RAW-02.ORIGINAL.dng"),
        ("PXL_20251210_200246684.jpg", "PXL_20251210_200246684", ".jpg"),

        # Complex cases
        ("IMG_1234-edited.jpg", "IMG_1234-edited", ".jpg"),
        ("IMG_1234-edited_001.jpg", "IMG_1234-edited", "_001.jpg"),
    ])
    def test_extract_base_name_patterns(self, filename, expected_base, expected_suffix):
        """Test base name extraction for various filename patterns."""
        base, suffix = extract_base_name(filename)
        assert base == expected_base
        assert suffix == expected_suffix

    def test_extract_base_name_pixel_case_insensitive(self):
        """Test that Pixel RAW pattern is case-insensitive."""
        base1, suffix1 = extract_base_name("PXL_20251210_200246684.RAW-01.COVER.jpg")
        base2, suffix2 = extract_base_name("PXL_20251210_200246684.raw-01.COVER.jpg")

        assert base1 == base2 == "PXL_20251210_200246684"

    def test_extract_base_name_no_extension(self):
        """Test filename without extension."""
        base, suffix = extract_base_name("no_extension")
        assert base == "no_extension"
        assert suffix == ""

    def test_extract_base_name_multiple_dots(self):
        """Test filename with multiple dots."""
        base, suffix = extract_base_name("my.photo.file.jpg")
        assert base == "my"
        assert suffix == ".photo.file.jpg"


class TestIsImageFile:
    """Tests for is_image_file() function."""

    @pytest.mark.parametrize("filename", [
        "photo.jpg",
        "image.jpeg",
        "picture.png",
        "raw.CR2",
        "raw.CR3",
        "raw.NEF",
        "raw.ARW",
        "raw.DNG",
        "heic.HEIC",
        "webp.webp",
    ])
    def test_is_image_file_true(self, filename):
        """Test that image files are recognized."""
        assert is_image_file(filename) is True

    @pytest.mark.parametrize("filename", [
        "sidecar.xmp",
        "thumbnail.thm",
        "video.mp4",
        "video.mov",
        "document.txt",
        "unknown.xyz",
    ])
    def test_is_image_file_false(self, filename):
        """Test that non-image files return False."""
        assert is_image_file(filename) is False


class TestIsRawFile:
    """Tests for is_raw_file() function."""

    @pytest.mark.parametrize("filename", [
        "photo.CR2",
        "photo.CR3",
        "photo.NEF",
        "photo.ARW",
        "photo.DNG",
        "photo.RAF",
        "photo.ORF",
        "photo.RW2",
        "photo.tiff",
    ])
    def test_is_raw_file_true(self, filename):
        """Test that RAW files are recognized."""
        assert is_raw_file(filename) is True

    @pytest.mark.parametrize("filename", [
        "photo.jpg",
        "photo.png",
        "photo.heic",
        "sidecar.xmp",
        "video.mp4",
    ])
    def test_is_raw_file_false(self, filename):
        """Test that non-RAW files return False."""
        assert is_raw_file(filename) is False


class TestIsSidecarFile:
    """Tests for is_sidecar_file() function."""

    @pytest.mark.parametrize("filename", [
        "photo.xmp",
        "photo.XMP",
        "thumbnail.thm",
        "thumbnail.THM",
    ])
    def test_is_sidecar_file_true(self, filename):
        """Test that sidecar files are recognized."""
        assert is_sidecar_file(filename) is True

    @pytest.mark.parametrize("filename", [
        "photo.jpg",
        "photo.CR2",
        "video.mp4",
        "document.txt",
    ])
    def test_is_sidecar_file_false(self, filename):
        """Test that non-sidecar files return False."""
        assert is_sidecar_file(filename) is False


class TestGetFinalExtension:
    """Tests for get_final_extension() function."""

    @pytest.mark.parametrize("filename,expected", [
        ("photo.jpg", ".jpg"),
        ("image.CR2", ".cr2"),
        ("photo.jpg.xmp", ".xmp"),
        ("file.tar.gz", ".gz"),
        ("UPPERCASE.JPG", ".jpg"),
        ("no_extension", ""),
    ])
    def test_get_final_extension(self, filename, expected):
        """Test final extension extraction."""
        assert get_final_extension(filename) == expected

    def test_get_final_extension_lowercase(self):
        """Test that extensions are returned in lowercase."""
        assert get_final_extension("PHOTO.JPG") == ".jpg"
        assert get_final_extension("Image.CR2") == ".cr2"


class TestGetAllExtensions:
    """Tests for get_all_extensions() function."""

    @pytest.mark.parametrize("filename,expected", [
        ("photo.jpg", ".jpg"),
        ("image.CR2", ".cr2"),
        ("photo.jpg.xmp", ".jpg.xmp"),
        ("file.tar.gz", ".tar.gz"),
        ("file.backup.old.txt", ".backup.old.txt"),
        ("no_extension", ""),
        ("UPPERCASE.JPG.XMP", ".jpg.xmp"),
    ])
    def test_get_all_extensions(self, filename, expected):
        """Test extraction of all extensions."""
        assert get_all_extensions(filename) == expected

    def test_get_all_extensions_lowercase(self):
        """Test that all extensions are returned in lowercase."""
        assert get_all_extensions("PHOTO.JPG.XMP") == ".jpg.xmp"
        assert get_all_extensions("File.TAR.GZ") == ".tar.gz"


class TestPatternIntegration:
    """Integration tests for pattern extraction."""

    def test_extract_and_reconstruct(self):
        """Test that base_name + suffix = original filename."""
        filenames = [
            "photo.jpg",
            "2025-01-01_00-28-40.CR2",
            "2025-01-01_00-28-40_001.jpg",
            "PXL_20251210_200246684.RAW-01.COVER.jpg",
            "photo.jpg.xmp",
        ]

        for filename in filenames:
            base, suffix = extract_base_name(filename)
            reconstructed = base + suffix
            assert reconstructed == filename, f"Failed to reconstruct {filename}"

    def test_related_files_same_base(self):
        """Test that related files have the same base name."""
        related_files = [
            "IMG_1234.CR2",
            "IMG_1234.jpg",
            "IMG_1234.xmp",
            "IMG_1234_001.jpg",
        ]

        bases = [extract_base_name(f)[0] for f in related_files]
        assert all(base == "IMG_1234" for base in bases)

    def test_pixel_files_same_base(self):
        """Test that Pixel RAW related files have the same base."""
        pixel_files = [
            "PXL_20251210_200246684.jpg",
            "PXL_20251210_200246684.RAW-01.COVER.jpg",
            "PXL_20251210_200246684.RAW-02.ORIGINAL.dng",
        ]

        bases = [extract_base_name(f)[0] for f in pixel_files]
        assert all(base == "PXL_20251210_200246684" for base in bases)
