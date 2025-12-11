"""Unit tests for ImageFile and Image dataclasses."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from home_media.models import FileFormat, FileRole, Image, ImageFile


class TestImageFileCreation:
    """Tests for ImageFile creation and initialization."""

    def test_imagefile_manual_creation(self):
        """Test manual ImageFile creation with all fields."""
        file_path = Path("/photos/IMG_1234.jpg")
        now = datetime.now()

        img_file = ImageFile(
            filename="IMG_1234.jpg",
            suffix=".jpg",
            extension=".jpg",
            file_path=file_path,
            file_size_bytes=1024000,
            file_created_at=now,
            file_modified_at=now,
            format=FileFormat.JPEG,
            role=FileRole.ORIGINAL,
        )

        assert img_file.filename == "IMG_1234.jpg"
        assert img_file.suffix == ".jpg"
        assert img_file.extension == ".jpg"
        assert img_file.file_path == file_path
        assert img_file.file_size_bytes == 1024000
        assert img_file.format == FileFormat.JPEG
        assert img_file.role == FileRole.ORIGINAL
        assert img_file.file_hash is None
        assert img_file.width is None
        assert img_file.height is None

    def test_imagefile_from_path(self, tmp_path):
        """Test ImageFile.from_path() creates correct instance."""
        # Create a temporary file
        test_file = tmp_path / "IMG_1234.jpg"
        test_file.write_text("test content")

        img_file = ImageFile.from_path(test_file, "IMG_1234")

        assert img_file.filename == "IMG_1234.jpg"
        assert img_file.suffix == ".jpg"
        assert img_file.extension == ".jpg"
        assert img_file.file_path == test_file
        assert img_file.file_size_bytes > 0
        assert img_file.format == FileFormat.JPEG
        assert img_file.role == FileRole.ORIGINAL
        assert isinstance(img_file.file_created_at, datetime)
        assert isinstance(img_file.file_modified_at, datetime)

    def test_imagefile_from_path_raw_file(self, tmp_path):
        """Test ImageFile.from_path() correctly identifies RAW files."""
        test_file = tmp_path / "IMG_1234.CR2"
        test_file.write_text("test raw content")

        img_file = ImageFile.from_path(test_file, "IMG_1234")

        assert img_file.format == FileFormat.CR2
        assert img_file.role == FileRole.ORIGINAL

    def test_imagefile_from_path_with_complex_suffix(self, tmp_path):
        """Test ImageFile.from_path() handles complex suffixes."""
        test_file = tmp_path / "IMG_1234-edited.jpg"
        test_file.write_text("test content")

        img_file = ImageFile.from_path(test_file, "IMG_1234")

        assert img_file.filename == "IMG_1234-edited.jpg"
        assert img_file.suffix == "-edited.jpg"
        assert img_file.extension == ".jpg"


class TestImageFileRoleInference:
    """Tests for ImageFile._infer_role() static method."""

    @pytest.mark.parametrize("suffix,fmt,expected_role", [
        (".xmp", FileFormat.XMP, FileRole.SIDECAR),
        (".thm", FileFormat.THM, FileRole.SIDECAR),
        (".COVER.jpg", FileFormat.JPEG, FileRole.COVER),
        (".cover.jpg", FileFormat.JPEG, FileRole.COVER),
        (".ORIGINAL.dng", FileFormat.DNG, FileRole.ORIGINAL),
        ("_001.jpg", FileFormat.JPEG, FileRole.DERIVATIVE),
        ("_002.jpg", FileFormat.JPEG, FileRole.DERIVATIVE),
        ("_099.jpg", FileFormat.JPEG, FileRole.DERIVATIVE),
        (".CR2", FileFormat.CR2, FileRole.ORIGINAL),
        (".NEF", FileFormat.NEF, FileRole.ORIGINAL),
        (".jpg", FileFormat.JPEG, FileRole.ORIGINAL),
        (".jpeg", FileFormat.JPEG, FileRole.ORIGINAL),
        ("-edited.jpg", FileFormat.JPEG, FileRole.EXPORT),
        ("-export.jpg", FileFormat.JPEG, FileRole.EXPORT),
    ])
    def test_infer_role(self, suffix, fmt, expected_role):
        """Test role inference for various suffix and format combinations."""
        assert ImageFile._infer_role(suffix, fmt) == expected_role

    def test_infer_role_unknown(self):
        """Test that unrecognized patterns return UNKNOWN."""
        result = ImageFile._infer_role(".unknown", FileFormat.UNKNOWN)
        assert result == FileRole.UNKNOWN


class TestImageFileHash:
    """Tests for ImageFile.populate_hash() method."""

    def test_populate_hash_success(self, tmp_path):
        """Test successful hash calculation."""
        test_file = tmp_path / "test.jpg"
        test_content = b"test image content"
        test_file.write_bytes(test_content)

        img_file = ImageFile.from_path(test_file, "test")
        result = img_file.populate_hash()

        assert result is True
        assert img_file.file_hash is not None
        assert len(img_file.file_hash) == 64  # SHA256 hex digest length

    def test_populate_hash_different_algorithms(self, tmp_path):
        """Test hash calculation with different algorithms."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test content")

        img_file = ImageFile.from_path(test_file, "test")

        # SHA256
        img_file.populate_hash("sha256")
        sha256_hash = img_file.file_hash
        assert len(sha256_hash) == 64

        # MD5
        img_file.populate_hash("md5")
        md5_hash = img_file.file_hash
        assert len(md5_hash) == 32
        assert md5_hash != sha256_hash

    def test_populate_hash_nonexistent_file(self, tmp_path):
        """Test hash calculation fails gracefully for nonexistent file."""
        nonexistent = tmp_path / "nonexistent.jpg"

        img_file = ImageFile(
            filename="nonexistent.jpg",
            suffix=".jpg",
            extension=".jpg",
            file_path=nonexistent,
            file_size_bytes=0,
            file_created_at=datetime.now(),
            file_modified_at=datetime.now(),
        )

        result = img_file.populate_hash()
        assert result is False
        assert img_file.file_hash is None


class TestImageFileDimensions:
    """Tests for ImageFile.populate_dimensions() method."""

    def test_populate_dimensions_pillow(self, tmp_path):
        """Test dimension extraction using Pillow for JPEG."""
        from PIL import Image as PILImage

        # Create a real test image
        test_file = tmp_path / "test.jpg"
        img = PILImage.new("RGB", (800, 600), color="red")
        img.save(test_file)

        img_file = ImageFile.from_path(test_file, "test")
        result = img_file.populate_dimensions()

        assert result is True
        assert img_file.width == 800
        assert img_file.height == 600

    def test_populate_dimensions_nonexistent_file(self, tmp_path):
        """Test dimension extraction fails for nonexistent file."""
        nonexistent = tmp_path / "nonexistent.jpg"

        img_file = ImageFile(
            filename="nonexistent.jpg",
            suffix=".jpg",
            extension=".jpg",
            file_path=nonexistent,
            file_size_bytes=0,
            file_created_at=datetime.now(),
            file_modified_at=datetime.now(),
            format=FileFormat.JPEG,
        )

        result = img_file.populate_dimensions()
        assert result is False
        assert img_file.width is None
        assert img_file.height is None

    def test_populate_dimensions_non_image_file(self, tmp_path):
        """Test dimension extraction returns False for non-image files."""
        test_file = tmp_path / "test.xmp"
        test_file.write_text("not an image")

        img_file = ImageFile.from_path(test_file, "test")
        result = img_file.populate_dimensions()

        assert result is False
        assert img_file.width is None
        assert img_file.height is None


class TestImageFileToDict:
    """Tests for ImageFile.to_dict() method."""

    def test_to_dict(self, tmp_path):
        """Test ImageFile serialization to dictionary."""
        test_file = tmp_path / "IMG_1234.jpg"
        test_file.write_text("test")

        img_file = ImageFile.from_path(test_file, "IMG_1234")
        img_file.width = 1920
        img_file.height = 1080
        img_file.file_hash = "abc123"

        result = img_file.to_dict()

        assert result["filename"] == "IMG_1234.jpg"
        assert result["suffix"] == ".jpg"
        assert result["extension"] == ".jpg"
        assert result["file_path"] == str(test_file)
        assert result["format"] == "jpg"
        assert result["role"] == "ORIGINAL"
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["file_hash"] == "abc123"
        assert isinstance(result["file_size_bytes"], int)


class TestImageCreation:
    """Tests for Image creation and initialization."""

    def test_image_creation(self):
        """Test basic Image creation."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        assert img.base_name == "IMG_1234"
        assert img.subdirectory == "2025/01/01"
        assert img.files == []
        assert img.file_count == 0
        assert img.captured_at is None
        assert isinstance(img.created_at, datetime)
        assert isinstance(img.updated_at, datetime)

    def test_image_with_files(self, tmp_path):
        """Test Image with files added."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        # Create test files
        jpeg_file = tmp_path / "IMG_1234.jpg"
        jpeg_file.write_text("jpeg")
        raw_file = tmp_path / "IMG_1234.CR2"
        raw_file.write_text("raw")

        img.add_file(ImageFile.from_path(jpeg_file, "IMG_1234"))
        img.add_file(ImageFile.from_path(raw_file, "IMG_1234"))

        assert img.file_count == 2
        assert len(img.files) == 2


class TestImageProperties:
    """Tests for Image computed properties."""

    def test_file_count(self, tmp_path):
        """Test file_count property."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")
        assert img.file_count == 0

        test_file = tmp_path / "IMG_1234.jpg"
        test_file.write_text("test")
        img.add_file(ImageFile.from_path(test_file, "IMG_1234"))

        assert img.file_count == 1

    def test_suffixes(self, tmp_path):
        """Test suffixes property."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        files = ["IMG_1234.jpg", "IMG_1234.CR2", "IMG_1234.xmp"]
        for filename in files:
            f = tmp_path / filename
            f.write_text("test")
            img.add_file(ImageFile.from_path(f, "IMG_1234"))

        suffixes = img.suffixes
        assert ".jpg" in suffixes
        assert ".CR2" in suffixes or ".cr2" in suffixes
        assert ".xmp" in suffixes

    def test_total_size_bytes(self, tmp_path):
        """Test total_size_bytes property."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_bytes(b"x" * 1000)
        file2 = tmp_path / "IMG_1234.CR2"
        file2.write_bytes(b"y" * 2000)

        img.add_file(ImageFile.from_path(file1, "IMG_1234"))
        img.add_file(ImageFile.from_path(file2, "IMG_1234"))

        assert img.total_size_bytes == 3000

    def test_has_raw_true(self, tmp_path):
        """Test has_raw property returns True when RAW file exists."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        raw_file = tmp_path / "IMG_1234.CR2"
        raw_file.write_text("raw")
        img.add_file(ImageFile.from_path(raw_file, "IMG_1234"))

        assert img.has_raw is True

    def test_has_raw_false(self, tmp_path):
        """Test has_raw property returns False when no RAW file."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        jpeg_file = tmp_path / "IMG_1234.jpg"
        jpeg_file.write_text("jpeg")
        img.add_file(ImageFile.from_path(jpeg_file, "IMG_1234"))

        assert img.has_raw is False

    def test_has_jpeg(self, tmp_path):
        """Test has_jpeg property."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        jpeg_file = tmp_path / "IMG_1234.jpg"
        jpeg_file.write_text("jpeg")
        img.add_file(ImageFile.from_path(jpeg_file, "IMG_1234"))

        assert img.has_jpeg is True

    def test_has_sidecar(self, tmp_path):
        """Test has_sidecar property."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        xmp_file = tmp_path / "IMG_1234.xmp"
        xmp_file.write_text("xmp")
        img.add_file(ImageFile.from_path(xmp_file, "IMG_1234"))

        assert img.has_sidecar is True

    def test_original_file(self, tmp_path):
        """Test original_file property returns the ORIGINAL file."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        raw_file = tmp_path / "IMG_1234.CR2"
        raw_file.write_text("raw")
        jpeg_file = tmp_path / "IMG_1234.jpg"
        jpeg_file.write_text("jpeg")

        img.add_file(ImageFile.from_path(jpeg_file, "IMG_1234"))
        img.add_file(ImageFile.from_path(raw_file, "IMG_1234"))

        # Refine roles so RAW becomes ORIGINAL and JPEG becomes EXPORT/COVER
        img.refine_file_roles()

        original = img.original_file
        assert original is not None
        assert original.format == FileFormat.CR2

    def test_original_file_no_files(self):
        """Test original_file returns None when no files exist."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")
        assert img.original_file is None


class TestImageRefineFileRoles:
    """Tests for Image.refine_file_roles() method."""

    def test_refine_roles_raw_plus_jpeg(self, tmp_path):
        """Test role refinement when both RAW and JPEG exist."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        raw_file = tmp_path / "IMG_1234.CR2"
        raw_file.write_text("raw")
        jpeg_file = tmp_path / "IMG_1234.jpg"
        jpeg_file.write_text("jpeg")

        img.add_file(ImageFile.from_path(raw_file, "IMG_1234"))
        img.add_file(ImageFile.from_path(jpeg_file, "IMG_1234"))

        img.refine_file_roles()

        # RAW should remain ORIGINAL
        raw = next(f for f in img.files if f.format.is_raw)
        assert raw.role == FileRole.ORIGINAL

        # JPEG should become COVER or EXPORT
        jpeg = next(f for f in img.files if f.format == FileFormat.JPEG)
        assert jpeg.role in (FileRole.COVER, FileRole.EXPORT)

    def test_refine_roles_jpeg_only(self, tmp_path):
        """Test role refinement when only JPEG exists."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        jpeg_file = tmp_path / "IMG_1234.jpg"
        jpeg_file.write_text("jpeg")

        img.add_file(ImageFile.from_path(jpeg_file, "IMG_1234"))
        img.refine_file_roles()

        # Single JPEG should be ORIGINAL
        jpeg = img.files[0]
        assert jpeg.role == FileRole.ORIGINAL


class TestImageCanonicalNames:
    """Tests for Image canonical name generation."""

    def test_get_canonical_name_with_captured_at(self):
        """Test canonical name generation with capture time."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")
        img.captured_at = datetime(2025, 12, 10, 14, 30, 45)

        canonical = img.get_canonical_name()
        assert canonical == "2025-12-10_14-30-45"

    def test_get_canonical_name_without_captured_at(self):
        """Test canonical name returns base_name when no capture time."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        canonical = img.get_canonical_name()
        assert canonical == "IMG_1234"

    def test_get_canonical_name_with_override(self):
        """Test canonical name with overridden capture time."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")
        override_time = datetime(2024, 6, 15, 10, 20, 30)

        canonical = img.get_canonical_name(override_time)
        assert canonical == "2024-06-15_10-20-30"

    def test_get_canonical_subdirectory_with_captured_at(self):
        """Test canonical subdirectory generation."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")
        img.captured_at = datetime(2025, 12, 10, 14, 30, 45)

        canonical = img.get_canonical_subdirectory()
        assert canonical == "2025/12/10"

    def test_get_canonical_subdirectory_without_captured_at(self):
        """Test canonical subdirectory returns current subdirectory when no capture time."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")

        canonical = img.get_canonical_subdirectory()
        assert canonical == "2025/01/01"


class TestImageToDict:
    """Tests for Image.to_dict() method."""

    def test_to_dict(self, tmp_path):
        """Test Image serialization to dictionary."""
        img = Image(base_name="IMG_1234", subdirectory="2025/01/01")
        img.captured_at = datetime(2025, 12, 10, 14, 30, 45)
        img.camera_make = "Canon"
        img.camera_model = "EOS R5"

        test_file = tmp_path / "IMG_1234.jpg"
        test_file.write_text("test")
        img.add_file(ImageFile.from_path(test_file, "IMG_1234"))

        result = img.to_dict()

        assert result["base_name"] == "IMG_1234"
        assert result["subdirectory"] == "2025/01/01"
        assert result["file_count"] == 1
        assert result["has_jpeg"] is True
        assert result["captured_at"] == img.captured_at
        assert result["camera_make"] == "Canon"
        assert result["camera_model"] == "EOS R5"
