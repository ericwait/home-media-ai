"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_image_path(temp_dir: Path) -> Path:
    """Create a sample image file path (doesn't create actual file)."""
    return temp_dir / "IMG_1234.jpg"


@pytest.fixture
def sample_raw_path(temp_dir: Path) -> Path:
    """Create a sample RAW file path."""
    return temp_dir / "IMG_1234.CR2"


@pytest.fixture
def sample_xmp_path(temp_dir: Path) -> Path:
    """Create a sample XMP sidecar file path."""
    return temp_dir / "IMG_1234.xmp"


@pytest.fixture
def sample_image_files(temp_dir: Path) -> dict[str, Path]:
    """Create a collection of related sample image files."""
    return {
        "raw": temp_dir / "IMG_1234.CR2",
        "jpeg": temp_dir / "IMG_1234.jpg",
        "xmp": temp_dir / "IMG_1234.xmp",
        "edited": temp_dir / "IMG_1234-edited.jpg",
    }
