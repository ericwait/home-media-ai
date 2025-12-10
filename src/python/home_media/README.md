# HomeMedia Python Package

AI-powered home media management and classification system.

## Installation

```bash
# From the project root, activate your conda environment
conda activate home-media-ai

# The package is available in development mode
cd src/python
pip install -e .
```

## Quick Start

```python
from home_media import scan_directory, Image, ImageFile, FileFormat, FileRole
from pathlib import Path

# Scan a directory for images
images_df, files_df = scan_directory(Path("/photos/2025/01/01"))

# View summary
print(f"Found {len(images_df)} images with {len(files_df)} files")
print(images_df[['base_name', 'file_count', 'has_raw', 'has_jpeg']].head())
```

## Core Concepts

### Image vs ImageFile

- **Image**: A moment in time - a single capture event
- **ImageFile**: A file representing part of an Image (RAW, JPEG, XMP sidecar, etc.)

An Image may have multiple ImageFiles (RAW + JPEG + XMP, etc.).

### File Roles

Files are classified by their role:

- `FileRole.ORIGINAL` - Primary capture (RAW, DNG)
- `FileRole.COVER` - Preview/thumbnail JPEG
- `FileRole.SIDECAR` - Metadata files (XMP, THM)
- `FileRole.EXPORT` - Processed outputs
- `FileRole.DERIVATIVE` - Crops, edits, versions
- `FileRole.UNKNOWN` - Role not yet determined

### File Formats

Supported formats via `FileFormat` enum:

- **RAW formats**: CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2
- **Standard images**: JPEG, PNG, TIFF, HEIC, WEBP
- **Metadata**: XMP, THM
- **Video** (future): MP4, MOV, AVI

## API Reference

### Models

#### `Image`

Represents a moment in time (a single capture event).

**Key Attributes:**

- `base_name: str` - Common identifier (e.g., "IMG_1234")
- `subdirectory: str` - Relative path from photos_root (e.g., "2025/01/01")
- `files: List[ImageFile]` - All files belonging to this Image
- `captured_at: Optional[datetime]` - When the photo was taken (lazy-loaded from EXIF)
- `camera_make, camera_model, lens` - Camera metadata (lazy-loaded)
- `gps_latitude, gps_longitude` - GPS coordinates (lazy-loaded)

**Key Properties:**

```python
image.file_count          # Number of files
image.suffixes            # List of file suffixes
image.total_size_bytes    # Total size of all files
image.has_raw             # True if Image has a RAW file
image.has_jpeg            # True if Image has a JPEG file
image.has_sidecar         # True if Image has sidecar files
image.original_file       # Get the primary capture file
```

**Methods:**

```python
# Convert to dict for pandas DataFrame
image.to_dict()

# Generate canonical names based on capture time
image.get_canonical_name()              # "2025-01-01_14-30-45"
image.get_canonical_subdirectory()      # "2025/01/01"
```

#### `ImageFile`

Represents a single file that is part of an Image.

**Key Attributes:**

- `filename: str` - Full filename
- `suffix: str` - Part after base_name (e.g., ".RAW-02.ORIGINAL.dng")
- `extension: str` - File extension (e.g., ".dng")
- `file_path: Path` - Absolute path to file
- `file_size_bytes: int` - File size
- `file_created_at, file_modified_at: datetime` - File timestamps
- `format: FileFormat` - Detected file format
- `role: FileRole` - Inferred role
- `file_hash: Optional[str]` - Hash for deduplication (lazy-loaded)
- `width, height: Optional[int]` - Dimensions (lazy-loaded)

**Methods:**

```python
# Create from a file path
ImageFile.from_path(file_path, base_name)

# Convert to dict for pandas DataFrame
image_file.to_dict()
```

#### `FileFormat`

Enum for known file formats with utility methods.

```python
# Detect format from extension
fmt = FileFormat.from_extension(".jpg")     # FileFormat.JPEG
fmt = FileFormat.from_extension("CR2")      # FileFormat.CR2

# Check format properties
fmt.is_raw          # True for RAW formats
fmt.is_image        # True for viewable image formats
fmt.is_sidecar      # True for metadata files
fmt.is_video        # True for video formats
```

#### `FileRole`

Enum for file roles in representing an Image.

```python
FileRole.ORIGINAL
FileRole.COVER
FileRole.SIDECAR
FileRole.EXPORT
FileRole.DERIVATIVE
FileRole.UNKNOWN
```

### Scanner Functions

#### `scan_directory()`

Scan a directory for image files and return DataFrames.

```python
def scan_directory(
    directory: Path,
    photos_root: Optional[Path] = None,
    recursive: bool = False,
    include_sidecars: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Args:
        directory: Directory to scan
        photos_root: Root for calculating relative subdirectories (defaults to directory)
        recursive: If True, scan subdirectories recursively
        include_sidecars: If True, include sidecar files (XMP, etc.)

    Returns:
        Tuple of (images_df, files_df):
        - images_df: One row per Image
        - files_df: One row per file, linked by base_name
    """
```

**Example:**

```python
from pathlib import Path

# Scan a single directory
images_df, files_df = scan_directory(Path("/photos/2025/01/01"))

# Scan recursively with a custom root
images_df, files_df = scan_directory(
    Path("/photos/2025/01"),
    photos_root=Path("/photos"),
    recursive=True
)

# Analyze results
print(f"Total images: {len(images_df)}")
print(f"Images with RAW: {images_df['has_raw'].sum()}")
print(f"Images with sidecars: {images_df['has_sidecar'].sum()}")
```

#### `list_subdirectories()`

List all subdirectories in a directory.

```python
def list_subdirectories(directory: Path) -> List[Path]:
    """
    Args:
        directory: Directory to scan

    Returns:
        List of subdirectory paths, sorted alphabetically
    """
```

**Example:**

```python
subdirs = list_subdirectories(Path("/photos"))
for subdir in subdirs:
    print(subdir.name)
```

#### `group_files_to_images()`

Group file paths into Images by base name.

```python
def group_files_to_images(
    file_paths: List[Path],
    photos_root: Path
) -> List[Image]:
    """
    Args:
        file_paths: List of file paths to group
        photos_root: Root directory for calculating subdirectories

    Returns:
        List of Image objects with files grouped by base_name
    """
```

**Example:**

```python
from pathlib import Path

files = [
    Path("/photos/IMG_1234.CR2"),
    Path("/photos/IMG_1234.jpg"),
    Path("/photos/IMG_1234.xmp"),
]

images = group_files_to_images(files, Path("/photos"))
print(f"Grouped into {len(images)} image(s)")
print(f"Image has {images[0].file_count} files")
```

#### `extract_base_name()`

Extract the base name from a filename.

```python
def extract_base_name(filename: str) -> str:
    """
    Extract the common base name from a filename.

    Handles patterns like:
    - IMG_1234.CR2 → IMG_1234
    - IMG_1234_001.jpg → IMG_1234
    - PXL_20251210_200246684.RAW-02.ORIGINAL.dng → PXL_20251210_200246684
    - photo.jpg.xmp → photo

    Args:
        filename: The filename to process

    Returns:
        The extracted base name
    """
```

**Example:**

```python
extract_base_name("IMG_1234.CR2")                           # "IMG_1234"
extract_base_name("IMG_1234_001.jpg")                       # "IMG_1234"
extract_base_name("PXL_20251210_200246684.RAW-02.dng")      # "PXL_20251210_200246684"
extract_base_name("photo.jpg.xmp")                          # "photo"
```

## Working with DataFrames

The scanner returns pandas DataFrames for easy analysis.

### Images DataFrame

Columns include:

- `base_name` - Common identifier
- `subdirectory` - Relative path from photos_root
- `file_count` - Number of files in this Image
- `suffixes` - List of file suffixes
- `total_size_bytes` - Total size of all files
- `has_raw`, `has_jpeg`, `has_sidecar` - Boolean flags
- `earliest_file_date`, `latest_file_date` - File timestamps
- `captured_at` - When photo was taken (if available)
- `camera_make`, `camera_model` - Camera info (if available)

### Files DataFrame

Columns include:

- `base_name`, `subdirectory` - Link to parent Image
- `filename`, `suffix`, `extension` - File naming
- `file_path` - Absolute path
- `file_size_bytes` - File size
- `file_created_at`, `file_modified_at` - Timestamps
- `format` - FileFormat value (e.g., "cr2", "jpg")
- `role` - FileRole name (e.g., "ORIGINAL", "SIDECAR")
- `width`, `height` - Image dimensions (if loaded)
- `file_hash` - File hash (if computed)

### Example Analysis

```python
# Find images with RAW but no XMP sidecar
needs_processing = images_df[images_df['has_raw'] & ~images_df['has_sidecar']]

# Calculate total storage by file format
format_sizes = files_df.groupby('format')['file_size_bytes'].sum() / (1024**3)  # GB
print("Storage by format (GB):")
print(format_sizes.sort_values(ascending=False))

# Find largest images
largest = images_df.nlargest(10, 'total_size_bytes')[['base_name', 'total_size_bytes', 'file_count']]
```

## Package Structure

```text
home_media/
├── __init__.py              # Main package exports
├── __version__.py           # Version information
├── models/                  # Data models
│   ├── __init__.py
│   ├── enums.py            # FileFormat, FileRole
│   └── image.py            # Image, ImageFile
├── scanner/                 # Directory scanning
│   ├── __init__.py
│   ├── directory.py        # scan_directory, list_subdirectories
│   ├── grouper.py          # group_files_to_images
│   └── patterns.py         # extract_base_name, pattern matching
├── config/                  # Configuration (future)
├── core/                    # Core functionality (future)
├── media/                   # Media handling (future)
├── ai/                      # AI models (future)
└── utils/                   # Utilities (future)
```

## Future Features

- EXIF metadata extraction and lazy-loading
- Database integration for persistent storage
- AI-powered image classification and tagging
- Duplicate detection using perceptual hashing
- Batch renaming and organization tools
- Web interface for browsing and management

## Contributing

This is a personal project built incrementally. Contributions and suggestions are welcome.

## License

MIT
