# home-media-ai

AI-powered home media management and classification system for working with images and video to classify and judge the content within.

## Project Approach

This project is being built **incrementally and deliberately** - taking a slow, thoughtful approach to ensure stability and meaningful solutions. Each component is developed in bite-sized pieces that can be understood, tested, and refined before moving forward.

## Current Status

### ✅ Foundation

- Python 3.11 development environment with Jupyter notebooks ([environment.yaml](environment.yaml))
- Package structure: `home_media` in `src/python/`
- Simple YAML-based configuration system with environment-specific values
- Jupyter notebook environment for exploration and testing

### ✅ Exploration & Analysis

- [Sandbox notebook](src/python/notebooks/sandbox.ipynb) for testing and experimentation
- File discovery and metadata extraction from photo directories
- Image grouping algorithms to identify related files (RAW+JPEG pairs, XMP sidecars, etc.)
- Pandas DataFrames for analyzing file collections

### 🏗️ Next Steps

- Database schema design for media metadata storage
- Build reusable Python modules from notebook experiments

## Project Structure

```
home-media-ai_scratch/
├── environment.yaml              # Conda environment definition
├── src/
│   └── python/
│       ├── config.yaml           # Environment-specific config (not in git)
│       ├── config_template.yaml  # Config template (in git)
│       ├── notebooks/            # Jupyter notebooks for exploration
│       │   └── sandbox.ipynb     # Sandbox for testing and experiments
│       └── home_media/           # Main Python package
│           ├── config/           # Configuration system
│           ├── core/             # Core functionality (future)
│           ├── media/            # Media handling (future)
│           ├── ai/               # AI models (future)
│           └── utils/            # Utilities (future)
└── README.md
```

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

### 3. Start working with notebooks

```bash
cd src/python/notebooks
jupyter notebook
# Open sandbox.ipynb to start exploring
```

## Configuration

The project uses a simple YAML-based configuration system:

- **`config_template.yaml`** - Template checked into version control
- **`config.yaml`** - Your environment-specific values (excluded from git)

Current configuration variables:

- `photos_root_original` - Root directory where original photos are stored

## Current Capabilities

The [sandbox notebook](src/python/notebooks/sandbox.ipynb) currently demonstrates:

- **Directory scanning**: List all subdirectories in the photos root
- **File metadata extraction**: Gather filename, extension, dates, and size information
- **Image grouping**: Intelligently group related files (e.g., RAW+JPEG pairs, XMP sidecars)
    - Handles complex naming patterns like `basename_001.jpg`, `basename.jpg.xmp`
    - One row per image with list of all related file suffixes
- **Pandas DataFrames**: Analyze and explore file collections efficiently

## Development Philosophy

- **Incremental**: Build one small piece at a time
- **Deliberate**: Understand each component before moving forward
- **Stable**: Test and refine before expanding
- **Meaningful**: Focus on solving real problems, not over-engineering

## License

MIT
