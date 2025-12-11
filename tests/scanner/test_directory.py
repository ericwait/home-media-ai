"""Unit tests for scanner.directory module."""

from pathlib import Path

import pandas as pd
import pytest

from home_media.scanner.directory import (
    count_files_in_directory,
    image_files_to_dataframe,
    images_to_dataframe,
    list_subdirectories,
    scan_directory,
)


class TestListSubdirectories:
    """Tests for list_subdirectories() function."""

    def test_list_subdirectories_empty(self, tmp_path):
        """Test listing subdirectories in empty directory."""
        result = list_subdirectories(tmp_path)
        assert result == []

    def test_list_subdirectories_with_dirs(self, tmp_path):
        """Test listing subdirectories."""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir2").mkdir()
        (tmp_path / "dir3").mkdir()

        result = list_subdirectories(tmp_path)

        assert len(result) == 3
        dir_names = {d.name for d in result}
        assert dir_names == {"dir1", "dir2", "dir3"}

    def test_list_subdirectories_ignores_files(self, tmp_path):
        """Test that files are not included in subdirectory list."""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "file.txt").write_text("test")

        result = list_subdirectories(tmp_path)

        assert len(result) == 1
        assert result[0].name == "dir1"

    def test_list_subdirectories_recursive(self, tmp_path):
        """Test recursive subdirectory listing."""
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "subdir1").mkdir()
        (tmp_path / "dir2").mkdir()

        result = list_subdirectories(tmp_path, recursive=True)

        assert len(result) >= 3  # dir1, dir1/subdir1, dir2
        dir_names = {d.name for d in result}
        assert "dir1" in dir_names
        assert "dir2" in dir_names
        assert "subdir1" in dir_names


class TestCountFilesInDirectory:
    """Tests for count_files_in_directory() function."""

    def test_count_empty_directory(self, tmp_path):
        """Test counting files in empty directory."""
        count = count_files_in_directory(tmp_path)
        assert count == 0

    def test_count_image_files(self, tmp_path):
        """Test counting image files."""
        (tmp_path / "photo1.jpg").write_text("test")
        (tmp_path / "photo2.CR2").write_text("test")
        (tmp_path / "photo3.png").write_text("test")
        (tmp_path / "document.txt").write_text("test")

        count = count_files_in_directory(tmp_path)

        assert count == 3  # Only image files

    def test_count_with_sidecars(self, tmp_path):
        """Test counting with sidecar files included."""
        (tmp_path / "photo1.jpg").write_text("test")
        (tmp_path / "photo1.xmp").write_text("test")
        (tmp_path / "photo2.CR2").write_text("test")

        count = count_files_in_directory(tmp_path, include_sidecars=True)

        assert count == 3  # jpg, CR2, xmp

    def test_count_without_sidecars(self, tmp_path):
        """Test counting without sidecar files."""
        (tmp_path / "photo1.jpg").write_text("test")
        (tmp_path / "photo1.xmp").write_text("test")
        (tmp_path / "photo2.CR2").write_text("test")

        count = count_files_in_directory(tmp_path, include_sidecars=False)

        assert count == 2  # Only jpg and CR2

    def test_count_recursive(self, tmp_path):
        """Test recursive file counting."""
        (tmp_path / "photo1.jpg").write_text("test")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "photo2.jpg").write_text("test")

        count = count_files_in_directory(tmp_path, recursive=True)

        assert count == 2


class TestScanDirectory:
    """Tests for scan_directory() function."""

    def test_scan_nonexistent_directory(self, tmp_path):
        """Test scanning nonexistent directory raises error."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError):
            scan_directory(nonexistent)

    def test_scan_file_not_directory(self, tmp_path):
        """Test scanning a file (not directory) raises error."""
        file = tmp_path / "file.txt"
        file.write_text("test")

        with pytest.raises(NotADirectoryError):
            scan_directory(file)

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning empty directory."""
        images_df, files_df = scan_directory(tmp_path)

        assert isinstance(images_df, pd.DataFrame)
        assert isinstance(files_df, pd.DataFrame)
        assert len(images_df) == 0
        assert len(files_df) == 0

    def test_scan_directory_with_images(self, tmp_path):
        """Test scanning directory with image files."""
        (tmp_path / "IMG_1234.jpg").write_text("test")
        (tmp_path / "IMG_1234.CR2").write_text("test")
        (tmp_path / "IMG_5678.jpg").write_text("test")

        images_df, files_df = scan_directory(tmp_path)

        assert len(images_df) == 2  # Two distinct images
        assert len(files_df) == 3  # Three files total
        assert set(images_df["base_name"]) == {"IMG_1234", "IMG_5678"}

    def test_scan_directory_recursive(self, tmp_path):
        """Test recursive directory scanning."""
        (tmp_path / "IMG_1234.jpg").write_text("test")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "IMG_5678.jpg").write_text("test")

        images_df, files_df = scan_directory(tmp_path, recursive=True)

        assert len(images_df) == 2
        assert len(files_df) == 2

    def test_scan_directory_with_sidecars(self, tmp_path):
        """Test scanning with sidecar files."""
        (tmp_path / "IMG_1234.jpg").write_text("test")
        (tmp_path / "IMG_1234.xmp").write_text("test")

        images_df, files_df = scan_directory(tmp_path, include_sidecars=True)

        assert len(images_df) == 1
        assert len(files_df) == 2  # jpg and xmp
        # Check that has_sidecar is True (convert to bool if needed)
        has_sidecar = images_df.iloc[0]["has_sidecar"]
        assert has_sidecar == True or has_sidecar == 1  # Handle pandas bool conversion

    def test_scan_directory_without_sidecars(self, tmp_path):
        """Test scanning without sidecar files."""
        (tmp_path / "IMG_1234.jpg").write_text("test")
        (tmp_path / "IMG_1234.xmp").write_text("test")

        images_df, files_df = scan_directory(tmp_path, include_sidecars=False)

        assert len(images_df) == 1
        assert len(files_df) == 1  # Only jpg

    def test_scan_directory_dataframe_structure(self, tmp_path):
        """Test that returned DataFrames have expected columns."""
        (tmp_path / "IMG_1234.jpg").write_text("test")

        images_df, files_df = scan_directory(tmp_path)

        # Check images_df columns
        expected_image_cols = [
            "base_name", "subdirectory", "file_count", "has_raw", "has_jpeg"
        ]
        for col in expected_image_cols:
            assert col in images_df.columns

        # Check files_df columns
        expected_file_cols = [
            "filename", "file_path", "file_size_bytes", "format", "role"
        ]
        for col in expected_file_cols:
            assert col in files_df.columns


class TestImagesToDataFrame:
    """Tests for images_to_dataframe() function."""

    def test_images_to_dataframe_empty(self):
        """Test converting empty list to DataFrame."""
        result = images_to_dataframe([])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_images_to_dataframe_single_image(self, tmp_path):
        """Test converting single Image to DataFrame."""
        from home_media.models import Image, ImageFile

        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_text("test")

        image = Image(base_name="IMG_1234", subdirectory="2025/01/01")
        image.add_file(ImageFile.from_path(file1, "IMG_1234"))

        result = images_to_dataframe([image])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["base_name"] == "IMG_1234"
        assert result.iloc[0]["file_count"] == 1


class TestImageFilesToDataFrame:
    """Tests for image_files_to_dataframe() function."""

    def test_image_files_to_dataframe_empty(self):
        """Test converting empty list to DataFrame."""
        result = image_files_to_dataframe([])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_image_files_to_dataframe_single_file(self, tmp_path):
        """Test converting single ImageFile to DataFrame."""
        from home_media.models import ImageFile

        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_text("test")

        img_file = ImageFile.from_path(file1, "IMG_1234")

        result = image_files_to_dataframe([img_file])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["filename"] == "IMG_1234.jpg"


class TestScanDirectoryIntegration:
    """Integration tests for scan_directory()."""

    @pytest.mark.integration
    def test_scan_with_hash_calculation(self, tmp_path):
        """Test scanning with hash calculation enabled."""
        file1 = tmp_path / "IMG_1234.jpg"
        file1.write_bytes(b"test content for hashing")

        images_df, files_df = scan_directory(tmp_path, calculate_hash=True)

        assert len(files_df) == 1
        # Hash should be populated
        assert pd.notna(files_df.iloc[0]["file_hash"])
        assert len(files_df.iloc[0]["file_hash"]) == 64  # SHA256 length

    @pytest.mark.integration
    def test_scan_with_dimensions(self, tmp_path):
        """Test scanning with dimension extraction."""
        from PIL import Image as PILImage

        file1 = tmp_path / "IMG_1234.jpg"
        img = PILImage.new("RGB", (800, 600), color="red")
        img.save(file1)

        images_df, files_df = scan_directory(tmp_path, extract_dimensions=True)

        assert len(files_df) == 1
        assert files_df.iloc[0]["width"] == 800
        assert files_df.iloc[0]["height"] == 600

    @pytest.mark.slow
    @pytest.mark.integration
    def test_scan_full_metadata(self, tmp_path):
        """Test scanning with all metadata extraction enabled."""
        from PIL import Image as PILImage

        file1 = tmp_path / "IMG_1234.jpg"
        img = PILImage.new("RGB", (1920, 1080), color="blue")
        img.save(file1)

        images_df, files_df = scan_directory(
            tmp_path,
            extract_exif=True,
            calculate_hash=True,
            extract_dimensions=True,
        )

        assert len(images_df) == 1
        assert len(files_df) == 1
        # Dimensions and hash should be populated
        assert files_df.iloc[0]["width"] == 1920
        assert files_df.iloc[0]["height"] == 1080
        assert pd.notna(files_df.iloc[0]["file_hash"])
