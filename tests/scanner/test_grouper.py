"""Unit tests for scanner.grouper module."""

from pathlib import Path

import pytest

from home_media.models import FileFormat, FileRole, Image
from home_media.scanner.grouper import group_files_by_base_name, group_files_to_images


class TestGroupFilesByBaseName:
    """Tests for group_files_by_base_name() function."""

    def test_group_single_file(self, tmp_path):
        """Test grouping a single file."""
        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_text("test")

        result = group_files_by_base_name([file1])

        assert len(result) == 1
        assert "IMG_1234" in result
        assert result["IMG_1234"] == [file1]

    def test_group_related_files(self, tmp_path):
        """Test grouping related files by base name."""
        file1 = tmp_path / "IMG_1234.jpg"
        file2 = tmp_path / "IMG_1234.CR2"
        file3 = tmp_path / "IMG_1234.xmp"

        for f in [file1, file2, file3]:
            f.write_text("test")

        result = group_files_by_base_name([file1, file2, file3])

        assert len(result) == 1
        assert "IMG_1234" in result
        assert len(result["IMG_1234"]) == 3
        assert set(result["IMG_1234"]) == {file1, file2, file3}

    def test_group_multiple_images(self, tmp_path):
        """Test grouping files from multiple images."""
        img1_files = [
            tmp_path / "IMG_1234.jpg",
            tmp_path / "IMG_1234.CR2",
        ]
        img2_files = [
            tmp_path / "IMG_5678.jpg",
            tmp_path / "IMG_5678.NEF",
        ]

        for f in img1_files + img2_files:
            f.write_text("test")

        result = group_files_by_base_name(img1_files + img2_files)

        assert len(result) == 2
        assert "IMG_1234" in result
        assert "IMG_5678" in result
        assert len(result["IMG_1234"]) == 2
        assert len(result["IMG_5678"]) == 2

    def test_group_with_derivatives(self, tmp_path):
        """Test grouping files with numbered derivatives."""
        files = [
            tmp_path / "IMG_1234.CR2",
            tmp_path / "IMG_1234.jpg",
            tmp_path / "IMG_1234_001.jpg",
            tmp_path / "IMG_1234_002.jpg",
        ]

        for f in files:
            f.write_text("test")

        result = group_files_by_base_name(files)

        assert len(result) == 1
        assert "IMG_1234" in result
        assert len(result["IMG_1234"]) == 4

    def test_group_pixel_raw_files(self, tmp_path):
        """Test grouping Google Pixel RAW files."""
        files = [
            tmp_path / "PXL_20251210_200246684.jpg",
            tmp_path / "PXL_20251210_200246684.RAW-01.COVER.jpg",
            tmp_path / "PXL_20251210_200246684.RAW-02.ORIGINAL.dng",
        ]

        for f in files:
            f.write_text("test")

        result = group_files_by_base_name(files)

        assert len(result) == 1
        assert "PXL_20251210_200246684" in result
        assert len(result["PXL_20251210_200246684"]) == 3

    def test_group_empty_list(self):
        """Test grouping empty file list."""
        result = group_files_by_base_name([])
        assert result == {}

    def test_group_skips_non_files(self, tmp_path):
        """Test that non-file paths are skipped."""
        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_text("test")
        dir1 = tmp_path / "subdir"
        dir1.mkdir()

        result = group_files_by_base_name([file1, dir1])

        assert len(result) == 1
        assert "IMG_1234" in result


class TestGroupFilesToImages:
    """Tests for group_files_to_images() function."""

    def test_group_single_file_to_image(self, tmp_path):
        """Test grouping a single file into an Image."""
        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_text("test")

        images = group_files_to_images([file1], photos_root=tmp_path)

        assert len(images) == 1
        assert isinstance(images[0], Image)
        assert images[0].base_name == "IMG_1234"
        assert images[0].file_count == 1
        assert images[0].subdirectory == "."

    def test_group_related_files_to_image(self, tmp_path):
        """Test grouping related files into a single Image."""
        files = [
            tmp_path / "IMG_1234.jpg",
            tmp_path / "IMG_1234.CR2",
            tmp_path / "IMG_1234.xmp",
        ]

        for f in files:
            f.write_text("test")

        images = group_files_to_images(files, photos_root=tmp_path)

        assert len(images) == 1
        image = images[0]
        assert image.base_name == "IMG_1234"
        assert image.file_count == 3
        assert image.has_raw is True
        assert image.has_jpeg is True
        assert image.has_sidecar is True

    def test_group_multiple_images(self, tmp_path):
        """Test grouping files from multiple images."""
        files = [
            tmp_path / "IMG_1234.jpg",
            tmp_path / "IMG_1234.CR2",
            tmp_path / "IMG_5678.jpg",
            tmp_path / "IMG_5678.NEF",
        ]

        for f in files:
            f.write_text("test")

        images = group_files_to_images(files, photos_root=tmp_path)

        assert len(images) == 2
        base_names = {img.base_name for img in images}
        assert base_names == {"IMG_1234", "IMG_5678"}

    def test_group_with_subdirectories(self, tmp_path):
        """Test grouping files in subdirectories."""
        subdir1 = tmp_path / "2025" / "01" / "01"
        subdir2 = tmp_path / "2025" / "01" / "02"
        subdir1.mkdir(parents=True)
        subdir2.mkdir(parents=True)

        files = [
            subdir1 / "IMG_1234.jpg",
            subdir1 / "IMG_1234.CR2",
            subdir2 / "IMG_5678.jpg",
        ]

        for f in files:
            f.write_text("test")

        images = group_files_to_images(files, photos_root=tmp_path)

        assert len(images) == 2

        # Find each image and verify subdirectory
        img1 = next(img for img in images if img.base_name == "IMG_1234")
        img2 = next(img for img in images if img.base_name == "IMG_5678")

        assert img1.subdirectory == str(Path("2025") / "01" / "01")
        assert img2.subdirectory == str(Path("2025") / "01" / "02")
        assert img1.file_count == 2
        assert img2.file_count == 1

    def test_group_same_basename_different_subdirs(self, tmp_path):
        """Test that same base name in different subdirs creates separate Images."""
        subdir1 = tmp_path / "dir1"
        subdir2 = tmp_path / "dir2"
        subdir1.mkdir()
        subdir2.mkdir()

        files = [
            subdir1 / "IMG_1234.jpg",
            subdir2 / "IMG_1234.jpg",
        ]

        for f in files:
            f.write_text("test")

        images = group_files_to_images(files, photos_root=tmp_path)

        assert len(images) == 2
        subdirs = {img.subdirectory for img in images}
        assert subdirs == {"dir1", "dir2"}

    def test_group_refines_file_roles(self, tmp_path):
        """Test that file roles are refined after grouping."""
        files = [
            tmp_path / "IMG_1234.CR2",
            tmp_path / "IMG_1234.jpg",
        ]

        for f in files:
            f.write_text("test")

        images = group_files_to_images(files, photos_root=tmp_path)

        assert len(images) == 1
        image = images[0]

        # Find the RAW and JPEG files
        raw_file = next(f for f in image.files if f.format == FileFormat.CR2)
        jpeg_file = next(f for f in image.files if f.format == FileFormat.JPEG)

        # RAW should be ORIGINAL
        assert raw_file.role == FileRole.ORIGINAL

        # JPEG should be EXPORT or COVER (not ORIGINAL since RAW exists)
        assert jpeg_file.role in (FileRole.EXPORT, FileRole.COVER)

    def test_group_empty_list(self):
        """Test grouping empty file list."""
        images = group_files_to_images([])
        assert images == []

    def test_group_without_photos_root(self, tmp_path):
        """Test grouping without specifying photos_root."""
        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_text("test")

        images = group_files_to_images([file1])

        assert len(images) == 1
        # Should use parent directory of first file as root
        assert images[0].subdirectory == "."

    def test_group_pixel_raw_files(self, tmp_path):
        """Test grouping Google Pixel RAW files into Image."""
        files = [
            tmp_path / "PXL_20251210_200246684.jpg",
            tmp_path / "PXL_20251210_200246684.RAW-01.COVER.jpg",
            tmp_path / "PXL_20251210_200246684.RAW-02.ORIGINAL.dng",
        ]

        for f in files:
            f.write_text("test")

        images = group_files_to_images(files, photos_root=tmp_path)

        assert len(images) == 1
        image = images[0]
        assert image.base_name == "PXL_20251210_200246684"
        assert image.file_count == 3

        # Verify roles
        cover = next((f for f in image.files if ".COVER." in f.suffix), None)
        original = next((f for f in image.files if ".ORIGINAL." in f.suffix), None)

        assert cover is not None
        assert original is not None
        assert cover.role == FileRole.COVER
        assert original.role == FileRole.ORIGINAL


class TestGroupFilesToImagesEdgeCases:
    """Edge case tests for group_files_to_images()."""

    def test_group_file_outside_photos_root(self, tmp_path, caplog):
        """Test handling of files outside photos_root."""
        photos_root = tmp_path / "photos"
        photos_root.mkdir()

        outside_file = tmp_path / "outside.jpg"
        outside_file.write_text("test")

        import logging
        caplog.set_level(logging.WARNING)

        images = group_files_to_images([outside_file], photos_root=photos_root)

        assert len(images) == 1
        # Should use parent directory name as fallback
        assert images[0].subdirectory == tmp_path.name
        assert "is not under photos_root" in caplog.text

    def test_group_skips_non_files(self, tmp_path):
        """Test that directories are skipped."""
        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_text("test")
        dir1 = tmp_path / "subdir"
        dir1.mkdir()

        images = group_files_to_images([file1, dir1], photos_root=tmp_path)

        assert len(images) == 1
        assert images[0].base_name == "IMG_1234"
