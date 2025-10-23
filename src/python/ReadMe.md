# Home Media AI - Python Package

A comprehensive media management and analysis system for organizing and analyzing photo collections with metadata extraction, database management, and machine learning capabilities.

## Table of Contents

- [Installation](#installation)
- [Database Setup (First Time Only)](#database-setup-first-time-only)
- [Configuration](#configuration)
- [Core Usage](#core-usage)
- [Package Structure](#package-structure)
- [Tools and Scripts](#tools-and-scripts)
- [Testing](#testing)
- [Common Issues](#common-issues)

## Installation

Create the virtual environment from the root-level `environment.yml`:

```bash
cd /path/to/home-media-ai

# Using mamba (faster, recommended)
mamba env create -f environment.yml

# Or using conda
conda env create -f environment.yml

# Activate the environment
conda activate home-media-ai-stable
```

## Database Setup (First Time Only)

Before using the package, initialize the database schema:

1. **Create a new database** (e.g., `home_media_ai`)
   ```bash
   mysql -u root -p -e "CREATE DATABASE home_media_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_520_ci;"
   ```

2. **Run the SQL scripts in order:**
   ```bash
   mysql -u your_user -p home_media_ai < src/sql/01_create_taxonomies.sql
   mysql -u your_user -p home_media_ai < src/sql/02_create_media.sql
   mysql -u your_user -p home_media_ai < src/sql/06_add_exif_columns.sql
   # Additional scripts as needed
   ```

3. **Verify the tables were created:**
   ```bash
   mysql -u your_user -p home_media_ai -e "SHOW TABLES;"
   ```

The core tables created:
- `media_types` - File format categories (JPEG, RAW, PNG, etc.)
- `media` - Individual media files with metadata and EXIF data
- `taxonomy_nodes` - Taxonomic classification data

## Configuration

### Quick Setup

1. **Copy the appropriate config template:**
   ```bash
   cd src/python
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

   scanning:
     storage_root: "/volume1/photo/RAW"  # What gets stored in DB
     batch_size: 100
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

## Core Usage

### 1. Querying Media Files (Recommended)

Use [MediaQuery](home_media_ai/media_query.py:39) with automatic session management:

```python
from home_media_ai import MediaQuery

# Context manager (recommended) - auto-closes session
with MediaQuery() as query:
    results = query.canon().raw().rating_min(4).year(2024).all()
    for photo in results:
        print(f"{photo.filename}: {photo.rating} stars")

# Or manual session management
query = MediaQuery()
results = query.dng().all()
query.close()  # Important: close when done

# Example queries
with MediaQuery() as query:
    # Simple filter
    raw_files = query.raw().all()

# Each independent query gets its own instance
with MediaQuery() as query:
    dngs = query.dng().all()

with MediaQuery() as query:
    rated = query.rating(5).all()

# Chained filters
with MediaQuery() as query:
    results = query.canon().raw().rating_min(4).year(2024).all()

# Return as DataFrame
with MediaQuery() as query:
    df = query.rating_min(3).has_gps().to_dataframe()

# Get file paths only
with MediaQuery() as query:
    paths = query.jpeg().year(2024).to_paths()

# Random sampling
with MediaQuery() as query:
    samples = query.rating(4).random(10)

# Statistics
with MediaQuery() as query:
    stats = query.canon().raw().stats()
    # Returns: count, total_size_mb, avg_rating, etc.
```

### 2. Advanced: Direct Session Management

For more control over transactions and multiple operations:

```python
from home_media_ai import session_scope, get_session, Media

# Context manager with auto-commit/rollback
with session_scope() as session:
    results = session.query(Media).filter(Media.rating == 5).all()
    # Session auto-commits here

# Or manual session management
session = get_session()
try:
    results = session.query(Media).all()
finally:
    session.close()

# Use with MediaQuery for custom session
with session_scope() as session:
    query = MediaQuery(session)
    results = query.rating(5).all()
```

#### Common Filter Methods

**File Types**: `raw()`, `dng()`, `jpeg()`, `extension(ext)`, `originals_only()`, `derivatives_only()`

**Ratings**: `rating(n)`, `rating_min(n)`, `rating_max(n)`, `rating_between(min, max)`, `has_rating()`, `no_rating()`

**Camera**: `camera_make(make)`, `camera_model(model)`, `canon()`, `nikon()`, `sony()`

**Location**: `has_gps()`, `no_gps()`, `gps_bbox(min_lat, max_lat, min_lon, max_lon)`

**Date/Time**: `year(y)`, `month(m)`, `year_month(y, m)`, `date_range(start, end)`, `after(date)`, `before(date)`

**Size**: `min_resolution(mp)`, `max_file_size(mb)`, `min_file_size(mb)`

**Sorting**: `sort_by_date()`, `sort_by_rating()`, `sort_by_file_size()`, `sort_random()`

**Results**: `all()`, `first()`, `one()`, `count()`, `limit(n)`, `random(n)`, `to_dataframe()`, `to_paths()`

### 3. Reading Media Files

```python
from home_media_ai import MediaQuery, read_image_as_array

# Query and read a file
with MediaQuery() as query:
    media = query.dng().first()

    # Method 1: Use Media.read_as_array() convenience method
    img_array = media.read_as_array()

    # Method 2: Get path and read manually
    file_path = media.get_full_path()
    img_array = read_image_as_array(file_path)

    # Image is returned as NumPy array with native dtype
    print(img_array.shape, img_array.dtype)
    # Example: (3024, 4032, 3) uint16 for RAW
    # Example: (3024, 4032, 3) uint8 for JPEG
```

#### Reading Multiple Files

```python
# Get multiple files and read them
with MediaQuery() as query:
    images = query.canon().rating_min(4).limit(5).all()

    for media in images:
        img = media.read_as_array()
        print(f"{media.filename}: {img.shape}, {img.dtype}")
```

### 4. Importing New Media

Use [MediaScanner](home_media_ai/scanner.py:33) to find files and [MediaImporter](home_media_ai/importer.py:13) to add them to the database:

```python
from home_media_ai import MediaScanner, MediaImporter, ExifExtractor

# Initialize EXIF extractor
exif_extractor = ExifExtractor()

# Scan a directory
scanner = MediaScanner(
    root_path="/path/to/photos",
    exif_extractor=exif_extractor
)

# Import files to database
importer = MediaImporter(
    database_uri=config.database.uri,
    use_config=True  # Uses config for storage_root
)

# Scan and import
files = scanner.scan_files(progress_callback=print)
stats = importer.bulk_import_files(list(files), progress_callback=print)

print(f"Imported: {stats['imported']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")

# Clean up
importer.close()
```

#### Importing RAW+JPEG Pairs

```python
# For cameras that create RAW+JPEG pairs, group by timestamp
grouped = scanner.group_by_timestamp(scanner.scan_files())
pairs = scanner.identify_pairs(grouped)

# Import with derivative relationships
stats = importer.import_file_pairs(pairs, progress_callback=print)
```

### Complete Example Workflow

```python
from home_media_ai import MediaQuery

# Simple and clean - session management handled automatically
with MediaQuery() as query:
    # Query files
    photos = query.canon().raw().rating_min(4).year(2024).limit(10).all()

    # Process files
    for photo in photos:
        img = photo.read_as_array()
        # Do something with img...
        print(f"{photo.filename}: {img.shape}")
    # Session auto-closes here
```

## Package Structure

```
src/python/
├── config.yaml                 # Your config file (copy from example)
├── config.example.yaml         # Example config (all platforms)
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

## Live Development

The [live_development.ipynb](notebooks/live_development.ipynb) notebook provides an interactive environment with auto-reload:

```python
# Auto-reload is enabled - edit source files and re-run cells!
%load_ext autoreload
%autoreload 2

from home_media_ai import MediaQuery, read_image_as_array

# Query database (no session setup needed!)
with MediaQuery() as query:
    results = query.rating(5).canon().all()

    # Load and display image
    img_array = results[0].read_as_array()
    plt.imshow(img_array / 65535.0)  # Normalize for display
```

### Features

- **Auto-reload**: Edit source files and see changes immediately
- **Database queries**: Pre-configured session management
- **Image display**: Built-in matplotlib visualization
- **Path resolution**: Automatic path mapping using config
- **Metadata overlay**: Display EXIF data with images

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

### Issue: Database connection fails

**Solution:** Verify database is running and credentials are correct:

```bash
# Test connection
mysql -u your_user -p -h host -P 3306 home_media_ai -e "SELECT COUNT(*) FROM media;"
```

## Machine Learning Integration

The package is designed to support ML workflows:

### Feature Extraction

```python
from home_media_ai import MediaQuery

# Extract features from rated images
with MediaQuery() as query:
    rated_media = query.rating_min(4).all()

    for media in rated_media:
        img = media.read_as_array()
        # Extract features (histogram, edges, color, etc.)
        features = extract_features(img)
        # Store for training
```

### Potential ML Applications

1. **Quality Prediction** - Predict ratings from image features
2. **Clustering** - Group similar images automatically
3. **Anomaly Detection** - Find unusual/interesting images
4. **Auto-Tagging** - Predict keywords from visual content
5. **Object Detection** - YOLO-based detection (see yolo_*.ipynb notebooks)

See [image_explorer.ipynb](notebooks/image_explorer.ipynb) for examples.

## Additional Resources

- **Example Notebooks**: Check [notebooks/](notebooks/) directory
- **Configuration Examples**: `config.*.yaml` files for different platforms
- **SQL Schema**: [src/sql/](../sql/) directory

## Questions?

Check the configuration examples in this directory:
- `config.example.yaml` - Comprehensive example for all platforms
- `config.dev.yaml` - Development config example
- `config.docker.yaml` - Docker container setup
- `config.synology.yaml` - Synology NAS setup

For common issues, see the troubleshooting section above.
