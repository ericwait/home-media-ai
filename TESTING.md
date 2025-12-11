# Testing Guide

This document describes the testing setup and best practices for the home-media project.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [CI/CD Integration](#cicd-integration)
- [Writing Tests](#writing-tests)
- [Coverage Reports](#coverage-reports)

## Quick Start

### Install Test Dependencies

The test dependencies are included in the conda environment:

```bash
# Activate the conda environment
conda activate home-media

# Or create/update the environment
conda env create -f environment.yaml
# or
conda env update -f environment.yaml --prune
```

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/models/test_enums.py

# Run specific test class
pytest tests/models/test_enums.py::TestFileFormat

# Run specific test
pytest tests/models/test_enums.py::TestFileFormat::test_raw_formats_exist
```

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── models/
│   ├── __init__.py
│   ├── test_enums.py        # FileFormat and FileRole tests
│   └── test_image.py        # ImageFile and Image tests
└── scanner/
    ├── __init__.py
    ├── test_patterns.py     # Pattern extraction tests
    ├── test_grouper.py      # File grouping tests
    ├── test_exif.py         # EXIF extraction tests
    └── test_directory.py    # Directory scanning tests
```

### Test Coverage

The test suite covers:

- **Models** (`home_media.models`)
  - `FileFormat` enum with 20+ formats
  - `FileRole` enum
  - `ImageFile` dataclass and methods
  - `Image` dataclass and metadata handling

- **Scanner** (`home_media.scanner`)
  - Filename pattern extraction
  - File grouping logic
  - EXIF metadata extraction
  - Directory scanning and DataFrame conversion

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=home_media --cov-report=term-missing

# Run with HTML coverage report
pytest --cov=home_media --cov-report=html
# Open htmlcov/index.html in browser

# Run with XML coverage (for CI/CD)
pytest --cov=home_media --cov-report=xml
```

### Test Filtering

```bash
# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run tests matching pattern
pytest -k "test_extract"

# Run tests in parallel (faster)
pytest -n auto
```

### Verbose Output

```bash
# Show all test names and results
pytest -v

# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Stop on first failure
pytest -x

# Show test durations
pytest --durations=10
```

## CI/CD Integration

### GitHub Actions Workflows

The project has two CI/CD workflows:

#### 1. **Tests Workflow** (`.github/workflows/tests.yml`)

Runs on every push and pull request to `main` and `develop` branches.

- **Multi-OS Testing**: Ubuntu, Windows, macOS
- **Python Version**: 3.11
- **Coverage**: Generates coverage reports and uploads to Codecov
- **Linting**: Checks code formatting with black, ruff, and isort

#### 2. **Main Branch Validation** (`.github/workflows/main-push.yml`)

Runs on every push to `main` branch.

- **Full Test Suite**: Runs all tests with coverage
- **Coverage Threshold**: Enforces minimum 70% coverage
- **Artifacts**: Uploads HTML and XML coverage reports

### Triggering CI/CD

```bash
# Push to trigger CI/CD on main branch
git push origin main

# Create pull request to trigger tests
git push origin feature-branch
# Then create PR on GitHub

# Manual workflow trigger
# Go to GitHub Actions tab and click "Run workflow"
```

### CI/CD Test Markers

Tests can be marked for different CI scenarios:

```python
@pytest.mark.unit
def test_something_fast():
    pass

@pytest.mark.integration
def test_something_with_io():
    pass

@pytest.mark.slow
def test_something_expensive():
    pass
```

## Writing Tests

### Test File Naming

- Test files must start with `test_`
- Test classes must start with `Test`
- Test functions must start with `test_`

### Using Fixtures

```python
def test_with_temp_directory(tmp_path):
    """tmp_path is a built-in pytest fixture."""
    test_file = tmp_path / "test.jpg"
    test_file.write_text("test")
    assert test_file.exists()

def test_with_custom_fixture(sample_image_files):
    """Use custom fixtures from conftest.py."""
    assert "raw" in sample_image_files
    assert "jpeg" in sample_image_files
```

### Parametrized Tests

```python
@pytest.mark.parametrize("extension,expected", [
    ("jpg", FileFormat.JPEG),
    ("CR2", FileFormat.CR2),
    ("png", FileFormat.PNG),
])
def test_file_format_detection(extension, expected):
    assert FileFormat.from_extension(extension) == expected
```

### Testing Exceptions

```python
def test_scan_nonexistent_directory(tmp_path):
    nonexistent = tmp_path / "nonexistent"
    with pytest.raises(FileNotFoundError):
        scan_directory(nonexistent)
```

### Mocking

```python
from unittest.mock import Mock, patch

def test_with_mock():
    with patch("home_media.scanner.exif.extract_exif_metadata") as mock_extract:
        mock_extract.return_value = ExifData(camera_make="Canon")
        # Test code using the mock
```

## Coverage Reports

### Viewing Coverage

```bash
# Terminal report
pytest --cov=home_media --cov-report=term-missing

# HTML report (interactive)
pytest --cov=home_media --cov-report=html
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux

# XML report (for CI/CD)
pytest --cov=home_media --cov-report=xml
```

### Coverage Configuration

Coverage is configured in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/python/home_media"]
omit = [
    "*/tests/*",
    "*/test_*.py",
]

[tool.coverage.report]
precision = 2
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
```

### Coverage Goals

- **Target**: 80%+ overall coverage
- **Minimum**: 70% for CI/CD to pass (enforced on main branch)
- **Critical Paths**: 90%+ coverage for core functionality

## Best Practices

### DO

✅ Write tests for new features
✅ Use descriptive test names
✅ Test edge cases and error conditions
✅ Keep tests independent and isolated
✅ Use fixtures for common setup
✅ Parametrize similar test cases
✅ Mock external dependencies
✅ Check both success and failure paths

### DON'T

❌ Test implementation details
❌ Write tests that depend on execution order
❌ Hardcode file paths (use fixtures)
❌ Test third-party library functionality
❌ Ignore test failures
❌ Skip writing tests for "simple" code

## Troubleshooting

### Common Issues

**Issue**: Tests can't find the `home_media` module

```bash
# Solution: Install package in development mode
pip install -e .
```

**Issue**: Tests are slow

```bash
# Solution: Skip slow tests during development
pytest -m "not slow"

# Or run tests in parallel
pytest -n auto
```

**Issue**: Coverage report not generated

```bash
# Solution: Install coverage package
conda install pytest-cov
```

**Issue**: Import errors in tests

```bash
# Solution: Make sure __init__.py files exist in all test directories
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Codecov documentation](https://docs.codecov.com/)
