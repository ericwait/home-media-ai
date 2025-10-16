# Home Media AI - Python Package

A comprehensive media management and analysis system for organizing and analyzing photo collections with metadata extraction, database management, and machine learning capabilities.

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Package Structure](#package-structure)
- [Live Development](#live-development)
- [Tools and Scripts](#tools-and-scripts)
- [Testing](#testing)

## Quick Start

### Installation

```bash
# Activate your environment
mamba activate home-media-ai

# Install the package (from repository root)
cd src/python
pip install -e .
```

### Configuration Setup

1. **Copy the appropriate config template:**
   ```bash
   # For Windows with UNC paths
   cp config.example.yaml config.yaml
   ```

2. **Edit `config.yaml` with your settings:**
   ```yaml
   # Your local storage root (where files live on this machine)
   default_storage_root: "\\\\tiger\\photo\\RAW"  # Windows UNC path
   # Or: "Z:\\"  # Mapped drive
   # Or: "/mnt/photos"  # Linux/Mac

   path_resolution:
     strategy: "config_only"  # Ignore DB storage_root, use config only

   database:
     uri: "mariadb+mariadbconnector://user:pass@host:3306/home_media_ai"
   ```

3. **Test your configuration:**
   ```python
   from home_media_ai.config import get_config, get_path_resolver

   config = get_config()
   print(f"Default storage root: {config.default_storage_root}")

   # Test path resolution
   resolver = get_path_resolver()
   path = resolver.resolve_path(None, "2024/October", "IMG_001.CR2")
   print(f"Resolved path: {path}")
   ```

## Configuration

### Path Resolution Strategies

The system supports three strategies for resolving file paths:

#### 1. `config_only` (Recommended)
Ignores the database `storage_root` column entirely and uses only the config.

```yaml
default_storage_root: "\\\\tiger\\photo\\RAW"
path_resolution:
  strategy: "config_only"
```

**How it works:**
- Database stores: `storage_root=anything`, `directory=2024/October`, `filename=IMG_001.CR2`
- Resolves to: `\\tiger\photo\RAW\2024\October\IMG_001.CR2`
- The database `storage_root` value is **completely ignored**

**Use when:** You have a single storage location and don't need the database to track mount points.

#### 2. `mapped`
Maps database storage_root values to local paths using a lookup table.

```yaml
storage_roots:
  "tiger/photo/RAW": "\\\\tiger\\photo\\RAW"
  "/volume1/photo/RAW": "\\\\tiger\\photo\\RAW"
default_storage_root: "\\\\tiger\\photo\\RAW"  # Fallback
path_resolution:
  strategy: "mapped"
```

**How it works:**
- Database stores: `storage_root=tiger/photo/RAW`, `directory=2024/October`, `filename=IMG_001.CR2`
- Looks up `tiger/photo/RAW` in `storage_roots` mapping
- Resolves to: `\\tiger\photo\RAW\2024\October\IMG_001.CR2`

**Use when:** You need to map multiple storage locations or work across different machines with different mount points.

#### 3. `database`
Uses the database `storage_root` value directly without any mapping.

```yaml
path_resolution:
  strategy: "database"
```

**How it works:**
- Database stores: `storage_root=\\\\tiger\\photo\\RAW`, `directory=2024/October`, `filename=IMG_001.CR2`
- Uses storage_root directly from database
- Resolves to: `\\tiger\photo\RAW\2024\October\IMG_001.CR2`

**Use when:** Database paths are already correct for the current machine (rarely recommended).

### Configuration File Locations

The system searches for `config.yaml` in this order:

1. Current working directory: `./config.yaml`
2. **Project root** (recommended): `E:\programming\home-media-ai\src\python\config.yaml`
3. User config directory: `~/.config/home-media-ai/config.yaml`

### Windows UNC Path Format

When using Windows network paths in YAML:

```yaml
# Correct: Use double backslashes
default_storage_root: "\\\\tiger\\photo\\RAW"

# Incorrect: Single backslashes won't work
default_storage_root: "\\tiger\photo\RAW"  # Wrong!
```

### Environment Variable Overrides

You can override config values with environment variables:

```powershell
# Windows PowerShell
$env:HOME_MEDIA_AI_URI = "mariadb+mariadbconnector://user:pass@host:3306/db"
$env:PHOTO_ROOT = "\\\\tiger\\photo\\RAW"
```

```bash
# Linux/Mac
export HOME_MEDIA_AI_URI="mariadb+mariadbconnector://user:pass@host:3306/db"
export PHOTO_ROOT="/mnt/photos"
```

## Package Structure

```
src/python/
├── config.yaml                 # Your config file (copy from example)
├── config.example.yaml         # Example config (all platforms)
├── config.dev.yaml             # Development config example
├── config.docker.yaml          # Docker config example
├── config.synology.yaml        # Synology NAS config example
├── home_media_ai/              # Main package
│   ├── __init__.py             # Package exports
│   ├── config.py               # Configuration management
│   ├── constants.py            # Shared constants
│   ├── exif_extractor.py       # EXIF and XMP metadata extraction
│   ├── importer.py             # Database import functionality
│   ├── io.py                   # Image reading (NumPy arrays)
│   ├── media.py                # SQLAlchemy models
│   ├── media_query.py          # Query helpers
│   ├── scanner.py              # File system scanning
│   └── utils.py                # Common utilities
├── notebooks/                  # Jupyter notebooks
│   ├── live_development.ipynb  # Live dev with auto-reload
│   ├── image_explorer.ipynb    # Image analysis
│   ├── sandbox.ipynb           # Experimental notebook
│   └── yolo_*.ipynb            # YOLO object detection
├── scripts/                    # Command-line tools
│   ├── scan_media.py           # Scan and import media
│   ├── setup_database.py       # Initialize database
│   ├── validate_metadata.py    # Validate DB vs files
│   └── explore_metadata.py     # Metadata exploration
└── tests/                      # Test suite
    ├── test_utils.py           # Utils tests (21 tests)
    ├── test_io.py              # I/O tests (15 tests)
    ├── test_scanner.py         # Scanner tests (12 tests)
    ├── test_exif_extractor.py  # EXIF tests (16 tests)
    └── fixtures/               # Test images
```

## Live Development

The [live_development.ipynb](notebooks/live_development.ipynb) notebook provides an interactive environment with auto-reload:

```python
# Auto-reload is enabled - edit source files and re-run cells!
%load_ext autoreload
%autoreload 2

from home_media_ai import Media, read_image_as_array
from home_media_ai.config import get_config

# Query database
results = session.query(Media).filter(
    Media.rating == 5,
    Media.camera_make.like('%Canon%')
).all()

# Load and display image
img_array = results[0].read_as_array()
plt.imshow(img_array)
```

### Features

- **Auto-reload**: Edit source files and see changes immediately
- **Database queries**: Pre-configured session management
- **Image display**: Built-in matplotlib visualization
- **Path resolution**: Automatic path mapping using config
- **Metadata overlay**: Display EXIF data with images

## Tools and Scripts

### Media Scanning

```bash
# Scan and import media files
python scripts/scan_media.py /path/to/photos

# With EXIF extraction
python scripts/scan_media.py /path/to/photos --extract-exif
```

### Database Setup

```bash
# Initialize database schema
python scripts/setup_database.py

# With sample data
python scripts/setup_database.py --sample-data
```

### Metadata Validation

```bash
# Validate 10 random files
python scripts/validate_metadata.py

# Validate 50 files with verbose output
python scripts/validate_metadata.py --samples 50 --verbose

# Only check rated images
python scripts/validate_metadata.py --samples 20 --rating-only
```

### Metadata Exploration

```bash
# Explore metadata distribution
python scripts/explore_metadata.py

# Generate detailed report
python scripts/explore_metadata.py --detailed
```

## Package API

### Image I/O

```python
from home_media_ai import read_image_as_array, read_image_metadata

# Read image as NumPy array (preserves data type)
img = read_image_as_array('photo.CR2')  # Returns uint16 for RAW
jpg = read_image_as_array('photo.jpg')  # Returns uint8 for JPEG

# Quick metadata extraction (fast, doesn't load full image)
metadata = read_image_metadata('photo.CR2')
print(f"Dimensions: {metadata['width']}x{metadata['height']}")
```

### Database Queries

```python
from home_media_ai import Media, MediaQuery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Setup
engine = create_engine('mariadb+mariadbconnector://...')
Session = sessionmaker(bind=engine)
session = Session()

# Query 5-star Canon images from 2024
results = session.query(Media).filter(
    Media.rating == 5,
    Media.camera_make.like('%Canon%'),
    Media.created >= datetime(2024, 1, 1),
    Media.created < datetime(2025, 1, 1)
).all()

# Load image using convenience method
img_array = results[0].read_as_array()
```

### Utility Functions

```python
from home_media_ai.utils import (
    infer_media_type_from_extension,
    calculate_file_hash,
    split_file_path,
    validate_file_extension
)

# Media type inference
media_type = infer_media_type_from_extension('.CR2')  # Returns 'raw_image'

# File hashing
hash_value = calculate_file_hash('photo.jpg')  # SHA-256 hex string

# Path splitting
storage_root, directory, filename = split_file_path(
    '/volume1/photo/RAW/2024/October/IMG_001.CR2',
    storage_root='/volume1/photo/RAW'
)
# Returns: ('/volume1/photo/RAW', '2024/October', 'IMG_001.CR2')
```

## Testing

Run the test suite:

```bash
# All tests (64 tests total)
pytest tests/ -v

# Specific test file
pytest tests/test_utils.py -v
pytest tests/test_io.py -v
pytest tests/test_scanner.py -v

# With coverage
pytest tests/ --cov=home_media_ai --cov-report=html
```

### Test Coverage

- **test_utils.py**: 21 tests - Utility functions
- **test_io.py**: 15 tests - Image reading with real fixtures
- **test_scanner.py**: 12 tests - File scanning with fixtures
- **test_exif_extractor.py**: 16 tests - EXIF/XMP extraction

All tests use real image files from `tests/fixtures/` including:
- JPEG images
- DNG RAW files
- XMP sidecar files

## Common Issues

### Issue: "Could not find file at resolved path"

**Solution:** Check your config path resolution:

```python
from home_media_ai.config import get_path_resolver

resolver = get_path_resolver()
# Test with actual database values
path = resolver.resolve_path("tiger/photo/RAW", "2024/October", "test.jpg")
print(f"Resolved to: {path}")
print(f"Exists: {path.exists()}")
```

If the path is wrong:
1. Verify `default_storage_root` in `config.yaml`
2. Check that the network share is accessible
3. Try strategy="config_only" to ignore database storage_root

### Issue: UNC Path Not Accessible

**Solution:** Map to drive letter:

```powershell
# Windows
net use Z: \\tiger\photo\RAW

# Update config
default_storage_root: "Z:\\"
```

### Issue: "No database URI configured"

**Solution:** Set in config.yaml:

```yaml
database:
  uri: "mariadb+mariadbconnector://user:pass@host:3306/home_media_ai"
```

Or use environment variable:

```powershell
$env:HOME_MEDIA_AI_URI = "mariadb+mariadbconnector://user:pass@host:3306/home_media_ai"
```

## Machine Learning Integration

The package is designed to support ML workflows:

### Feature Extraction

```python
# Extract features from rated images
for media in session.query(Media).filter(Media.rating >= 4):
    img = media.read_as_array()
    # Extract features (histogram, edges, color, etc.)
    features = extract_features(img)
    # Store for training
```

### Potential ML Applications

1. **Quality Prediction** - Predict ratings from image features
2. **Clustering** - Group similar images automatically
3. **Anomaly Detection** - Find unusual/interesting images
4. **Auto-Tagging** - Predict keywords from visual features

See [image_explorer.ipynb](notebooks/image_explorer.ipynb) for examples.

## Additional Resources

- **Media Query Examples**: See [media_query_examples.md](media_query_examples.md)
- **Configuration Examples**: Check `config.*.yaml` files
- **Live Development**: Open [notebooks/live_development.ipynb](notebooks/live_development.ipynb)

## Questions?

Check the configuration examples in this directory:
- `config.example.yaml` - Comprehensive example for all platforms
- `config.dev.yaml` - Development config example
- `config.docker.yaml` - Docker container setup
- `config.synology.yaml` - Synology NAS setup

For common issues, see the troubleshooting section above or check existing issues in the repository.
