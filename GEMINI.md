# GEMINI Project Context: home-media-ai

## Project Overview

This project, `home-media`, is a Python library for managing and analyzing home media collections (images and eventually videos). It is designed to be a foundation for an AI-powered classification system. The current implementation focuses on the "media scanning and modeling" phase.

The core architecture is that of a library, intended to be imported and used in other Python scripts or Jupyter notebooks.

**Key Components:**

* **Technology Stack**: Python 3.11, managed with a Conda environment (`environment.yaml`). It uses Pandas for data manipulation, Pillow and ExifRead for image metadata, and Pytest for testing.
* **Data Models (`src/python/home_media/models`):**
    * `Image`: Represents a single abstract "moment in time" or capture event.
    * `ImageFile`: Represents a concrete file on disk (e.g., `IMG_1234.CR2`, `IMG_1234.JPG`). An `Image` can be composed of multiple `ImageFile` objects.
    * `FileFormat` & `FileRole`: Enums used to classify files by their type (e.g., `CR2`, `JPEG`) and their function (e.g., `ORIGINAL`, `SIDECAR`).
* **Scanner Module (`src/python/home_media/scanner`):**
    * This is the main entry point for using the library. The `scan_directory` function traverses file paths, groups related files (like a RAW+JPEG pair) into a single `Image` object, and can optionally extract metadata like EXIF info, image dimensions, and file hashes.
    * The output is conveniently provided as two Pandas DataFrames: one for `Images` and one for `ImageFiles`.

## Building and Running

The project is configured for a Mamba environment.

**1. Environment Setup:**

To set up the development environment and install dependencies:

```bash
# Create and activate the mamba environment
mamba env create -f environment.yaml
mamba activate home-media

# Install the package in editable mode
pip install -e .
```

**2. Running Tests:**

The project has a comprehensive test suite using `pytest`. Test configuration is in `pytest.ini` and `pyproject.toml`.

```bash
# Run all tests
pytest

# Run tests with a code coverage report in the terminal
pytest --cov=home_media --cov-report=term-missing

# Generate an HTML coverage report
pytest --cov=home_media --cov-report=html
# Then open htmlcov/index.html in a browser
```

**3. Example Usage (from `README.md`):**

The library is used by importing its functions.

```python
from home_media import scan_directory
from pathlib import Path

# Scan a directory to get image and file dataframes
images_df, files_df = scan_directory(Path("/path/to/your/photos"))

print(f"Found {len(images_df)} images with {len(files_df)} files")
print(images_df.head())
```

## Development Conventions

* **Testing is a Priority:** The project maintains high test coverage (target is 80%+) and has extensive tests for models and scanner logic. See `TESTING.md` for detailed guidelines. Tests are marked with `unit`, `integration`, and `slow`.
* **CI/CD:** GitHub Actions are configured in `.github/workflows` to automate testing on pushes and pull requests across Windows, macOS, and Ubuntu.
* **Incremental Development:** The philosophy is to build and test small, stable components deliberately before moving to the next feature.
* **Code Style:** The code uses modern Python features like dataclasses and type hints. It is well-documented with docstrings explaining the purpose of modules, classes, and functions.
* **Entry Points:** There is no single "main" script. The primary user-facing function is `home_media.scanner.scan_directory`.
