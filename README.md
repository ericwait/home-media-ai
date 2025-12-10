# home-media-ai

AI-powered home media management and classification system for working with images and video to classify and judge the content within.

## Project Approach

This project is being built **incrementally and deliberately** - taking a slow, thoughtful approach to ensure stability and meaningful solutions. Each component is developed in bite-sized pieces that can be understood, tested, and refined before moving forward.

## Current Status

### ✅ Foundation
- Python 3.11 development environment ([environment.yaml](environment.yaml))
- Package structure: `home_media` in `src/python/`
- Simple configuration system with environment-specific values

### 🏗️ In Progress
- Configuration management (starting with `photos_root_original`)
- Building core functionality piece by piece

## Project Structure

```
home-media-ai_scratch/
├── environment.yaml              # Conda environment definition
├── src/
│   └── python/
│       ├── config.yaml           # Environment-specific config (not in git)
│       ├── config_template.yaml  # Config template (in git)
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

### 3. Install the package (development mode)

```bash
pip install -e .
```

## Configuration

The project uses a simple YAML-based configuration system:

- **`config_template.yaml`** - Template checked into version control
- **`config.yaml`** - Your environment-specific values (excluded from git)

Current configuration variables:
- `photos_root_original` - Root directory where original photos are stored

## Development Philosophy

- **Incremental**: Build one small piece at a time
- **Deliberate**: Understand each component before moving forward
- **Stable**: Test and refine before expanding
- **Meaningful**: Focus on solving real problems, not over-engineering

## License

MIT
