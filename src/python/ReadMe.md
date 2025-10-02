# Image Analysis Tools - Setup Guide

## Overview

I've created two new tools for your [[Home Media AI]] project:

1. **`validate_metadata.py`** - Validates database metadata against actual files
2. **`image_explorer.ipynb`** - Interactive notebook for image selection and processing

## Installation

Both tools are now in your repository structure.
Place them in the appropriate locations:

```sh
src/python/scripts/validate_metadata.py
src/python/notebooks/image_explorer.ipynb  (create notebooks directory)
```

## Validation Script Updates

### Key Improvement: Floating-Point Tolerance

The validation script now uses **relative tolerance** instead of absolute tolerance for numeric comparisons.

This fixes the precision issues you saw where values like:

- Database: `43.46601170`
- File: `43.4660117`

These are now correctly recognized as identical.

### Technical Details

For GPS coordinates, the relative tolerance of `1e-5` means:

- Latitude/Longitude: ~1 meter accuracy
- Altitude: 0.01mm effectively (meaningless precision difference)

This is similar to how MATLAB's `isequal` with tolerance works, or C++'s `std::abs(a - b) / std::max(a, b) < epsilon`.

### Usage

```bash
# Basic validation (10 random files)
python src/python/scripts/validate_metadata.py

# Validate 50 files with details
python src/python/scripts/validate_metadata.py --samples 50 --verbose

# Only check rated images (your ML training data)
python src/python/scripts/validate_metadata.py --samples 20 --rating-only
```

### What It Checks

- Rating (0-5 stars)
- GPS coordinates (latitude, longitude, altitude)
- Camera metadata (make, model, lens)
- Image dimensions (width, height)

## Image Explorer Notebook

### Purpose

Interactive environment for:

- Querying images by criteria
- Visual analysis (histograms, color distribution, edge detection)
- Batch processing
- Comparing RAW vs JPEG exports

### Getting Started

1. Launch JupyterLab:

   ```bash
   mamba activate home-media-ai
   jupyter lab
   ```

2. Open `image_explorer.ipynb`
3. Set your database connection in the second cell (uses `HOME_MEDIA_AI_URI` environment variable)
4. Run through the cells to explore your images

### Key Functions

**Query Functions:**

```python
# Get 5-star images
images = query_images(rating=5, limit=10)

# Get images from specific camera with GPS
images = query_images(camera_make='Canon', has_gps=True, limit=5)

# Get images from specific year
images = query_images(year=2024, limit=20)
```

**Analysis Functions:**

```python
# Histogram and statistics
analyze_image_histogram(img)

# Edge detection (Canny)
analyze_edges(img, low_threshold=50, high_threshold=150)

# Color distribution in LAB space
analyze_color_distribution(img)
```

### Machine Learning Opportunities

The notebook is set up as a foundation for ML work.
Here are some directions you could explore:

1. **Quality Prediction** - Train a model to predict your ratings based on image features
   - Use histogram statistics, color distribution, sharpness metrics
   - Your existing ratings are ground truth
   - This is supervised learning with your existing labeled data
2. **Clustering/Similarity** - Unsupervised grouping of similar images
   - Extract feature vectors (color histograms, edge density, texture)
   - Use k-means or DBSCAN to find natural groupings
   - Could help identify duplicate/similar shots
3. **Automatic Tagging** - If you add keyword extraction from XMP
   - Could train keyword prediction based on visual features
   - Start simple with location-based predictions using GPS
4. **Anomaly Detection** - Find unusual/interesting images
   - No ground truth needed
   - Use isolation forest or autoencoders on image features
   - Could help surface "hidden gems" in large collections

### MATLAB Analogy

If this were MATLAB, you'd be using:

- `imread()` → `load_image()`
- `imhist()` → `cv2.calcHist()`
- `edge()` → `cv2.Canny()`
- Database queries → would need Database Toolbox

The notebook approach is similar to MATLAB's Live Scripts - mix code, visualization, and markdown.

### C++/CUDA Analogy

The image processing here uses OpenCV, which you can think of as the Python equivalent of the C++ OpenCV library.

If you needed GPU acceleration:

- OpenCV has CUDA support (`cv2.cuda.*` modules)
- Could offload edge detection, filtering to GPU
- Similar patterns to CUDA kernels you'd write in C++

For your collection size (8,441 files), CPU processing is probably fine.
GPU acceleration becomes valuable when processing 100K+ images or doing real-time video analysis.

## Next Steps

### Short Term

1. Run validation script with larger sample size to verify data integrity
2. Open the notebook and explore your rated images
3. Try the different analysis functions on your photos

### Medium Term (ML Preparation)

1. Use the batch analysis examples to extract features from rated images
2. Build a CSV of features + ratings for model training
3. Try simple linear regression: brightness/contrast → rating prediction

### Long Term (Deep Learning)

1. The notebook can integrate with PyTorch/TensorFlow
2. Could fine-tune a pre-trained CNN (ResNet, EfficientNet) on your ratings
3. Transfer learning requires less data than training from scratch

## Questions to Consider

- **What makes a 5-star image in your collection?** Understanding this helps with feature selection
- **Do you have enough variety in ratings?** The distribution chart in the notebook will show this
- **GPS vs non-GPS images** - Different processing strategies might be needed

## File Structure

```sh
src/python/
├── ReadMe.md
├── home_media_ai
│   ├── constants.py
│   ├── exif_extractor.py
│   ├── importer.py
│   ├── models.py
│   ├── scanner.py
│   └── __init__.py
├── notebooks
│   └── image_explorer.ipynb
├── scripts
│   ├── explore_metadata.py
│   ├── import_flora_wfo_data.py
│   ├── scan_media.py
│   ├── setup_database.py
│   ├── validate_metadata.py
│   └── __init__.py
└── tests
    ├── test_exif_extractor.py
    ├── test_importer.py
    ├── test_scanner.py
    ├── __init__.py
    ├── fixtures
    │   ├── 2024-10-11_12-19-49.jpg
    │   ├── 2024-10-11_12-19-49.jpg.xmp
    │   ├── 2024-10-11_12-19-50.dng
    │   ├── 2024-10-11_12-19-50.dng.xmp
    │   ├── 2024-10-11_12-19-51.dng
    │   ├── 2024-10-11_12-19-51.dng.xmp
    │   ├── 2024-10-11_12-19-51.jpg
    │   ├── 2024-10-11_12-19-51.jpg.xmp
    └── integration
```

## Tips

- Start with small sample sizes when experimenting
- The notebook auto-saves; use checkpoints for major experiments
- Export results to CSV for further analysis in other tools
- Use `--verbose` flag in validation script to see file paths when debugging

Feel free to ask if you want to dive deeper into any of these areas!
