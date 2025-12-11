# home-media

AI-powered home media management and classification system for working with images and video to classify and judge the content within.

## Project Approach

This project is being built **incrementally and deliberately** - taking a slow, thoughtful approach to ensure stability and meaningful solutions. Each component is developed in bite-sized pieces that can be understood, tested, and refined before moving forward.

## Core Concepts

### Image vs ImageFile

- **Image**: A moment in time - a single capture event
- **ImageFile**: A file representing part of an Image (RAW, JPEG, XMP sidecar, etc.)

An Image may have multiple ImageFiles:

- Original RAW capture (`.CR2`, `.NEF`, `.DNG`, etc.)
- JPEG preview or export
- XMP sidecar with metadata and edits
- Derivative versions (crops, edits)

### File Roles

Files are classified by their role in representing an Image:

- **ORIGINAL**: Primary capture (RAW, DNG)
- **COVER**: Preview/thumbnail JPEG
- **SIDECAR**: Metadata files (XMP, THM)
- **EXPORT**: Processed outputs
- **DERIVATIVE**: Crops, edits, versions

### File Grouping

The system intelligently groups related files by their base name:

- `IMG_1234.CR2` and `IMG_1234.jpg` → same Image
- `PXL_20251210_200246684.RAW-02.ORIGINAL.dng` and `PXL_20251210_200246684.RAW-01.COVER.jpg` → same Image
- `photo_001.jpg`, `photo_002.jpg` → different Images

## Current Status

### Implemented

- **Data Models** ([`home_media.models`](src/python/home_media/models/))
    - `Image` and `ImageFile` dataclasses with pandas integration
    - `FileFormat` and `FileRole` enumerations
    - Lazy-loading support for EXIF metadata

- **Scanner Module** ([`home_media.scanner`](src/python/home_media/scanner/))
    - Directory scanning with optional recursion
    - File grouping by base name patterns
    - DataFrame output for easy analysis
    - Functions: `scan_directory`, `list_subdirectories`, `group_files_to_images`, `extract_base_name`

- **Development Environment**
    - Python 3.11 with Jupyter notebooks
    - YAML-based configuration system
    - Sandbox notebook for experimentation

### Next Steps

- Database schema design for media metadata storage
- EXIF metadata extraction
- AI/ML integration for classification

## Getting Started

### 1. Set up the environment

```bash
# Create and activate conda environment
conda env create -f environment.yaml
conda activate home-media-ai
```

### 2. Configure for your environment

```bash
# Copy the template and edit with your values
cd src/python
cp config_template.yaml config.yaml
# Edit config.yaml with your local paths
```

### 3. Start using the package

**In a Jupyter notebook:**

```python
from home_media import scan_directory, Image, ImageFile
from pathlib import Path

# Scan a directory
images_df, files_df = scan_directory(Path("/photos/2025/01/01"))
print(f"Found {len(images_df)} images with {len(files_df)} files")

# Analyze the results
print(images_df[['base_name', 'file_count', 'has_raw', 'has_jpeg']].head())
```

**In a Python script:**

```python
from home_media import list_subdirectories, scan_directory
from pathlib import Path

# List subdirectories
photos_root = Path("/photos")
subdirs = list_subdirectories(photos_root)

# Scan each subdirectory
for subdir in subdirs:
    images_df, files_df = scan_directory(subdir, photos_root)
    print(f"{subdir.name}: {len(images_df)} images")
```

See the [Python module README](src/python/home_media/README.md) for detailed API documentation.

## Project Structure

```text
home-media-ai_scratch/
├── environment.yaml              # Conda environment definition
├── src/
│   └── python/
│       ├── config.yaml           # Environment-specific config (not in git)
│       ├── config_template.yaml  # Config template (in git)
│       ├── notebooks/            # Jupyter notebooks for exploration
│       │   └── sandbox.ipynb     # Sandbox for testing and experiments
│       └── home_media/           # Main Python package
│           ├── models/           # Data models (Image, ImageFile, enums)
│           ├── scanner/          # Directory scanning and file grouping
│           ├── config/           # Configuration system
│           ├── core/             # Core functionality (future)
│           ├── media/            # Media handling (future)
│           ├── ai/               # AI models (future)
│           └── utils/            # Utilities (future)
└── README.md
```

## Development Philosophy

- **Incremental**: Build one small piece at a time
- **Deliberate**: Understand each component before moving forward
- **Stable**: Test and refine before expanding
- **Meaningful**: Focus on solving real problems, not over-engineering

## License

MIT
