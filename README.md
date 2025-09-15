# Home Media AI

🏠📸 **AI-powered home media management and analysis toolkit**

Transform your massive media collection into an organized, searchable library! Home Media AI helps you analyze, evaluate, and discover content in your personal photos and videos using computer vision and machine learning.

## 🎯 Perfect for families with:
- 700k+ photos and videos 📷
- Terabytes of home media storage 💾
- Years of unorganized memories 📅
- Need for quick content discovery 🔍

## ✨ Features

### 📊 **Quality Assessment**
- **Image Quality Evaluation**: Blur detection, brightness, contrast, noise analysis
- **Video Quality Assessment**: Frame quality, motion blur, stability scoring
- **Face Quality Analysis**: Detect and assess face quality in photos
- **Exposure & Color Analysis**: Proper exposure and color saturation metrics

### 🧠 **Content Identification**
- **Face Detection**: Find and count faces in images and videos
- **Object Detection**: Identify objects, people, and scenes
- **Scene Classification**: Outdoor, indoor, nature, events automatic categorization
- **Color Analysis**: Extract dominant colors from media
- **Smart Tagging**: Auto-generate descriptive tags for easy searching

### 🗃️ **Database & Search**
- **Fast SQLite Database**: Store metadata and analysis results efficiently
- **Advanced Search**: Find media by quality, content, faces, objects, tags
- **Duplicate Detection**: Identify duplicate files to save storage space
- **Comprehensive Metadata**: EXIF data, file info, and analysis timestamps

### 🛠️ **Developer-Friendly**
- **Extensive Documentation**: Learn computer vision and AI concepts
- **Modular Design**: Use individual components or the complete toolkit
- **Configuration Management**: Flexible settings for different use cases
- **CLI Interface**: Powerful command-line tools for batch processing

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/ericwait/home-media-ai.git
cd home-media-ai

# Install with pip (development mode)
pip install -e .

# Or install with optional dependencies
pip install -e ".[dev,ml]"
```

### Basic Usage

```bash
# Analyze a directory of photos/videos
home-media-ai analyze /path/to/your/media --recursive --progress

# Search for high-quality family photos
home-media-ai search --min-quality 80 --has-faces --min-faces 2

# Find outdoor scenes
home-media-ai search --tag outdoor --tag nature

# Show collection statistics
home-media-ai stats

# Find duplicate files
home-media-ai duplicates --show-paths
```

### Python API

```python
from home_media_ai import MediaAnalyzer

# Initialize analyzer
analyzer = MediaAnalyzer('/path/to/your/media')
analyzer.create_database()

# Analyze a single file
result = analyzer.analyze_file('/path/to/photo.jpg')
print(f"Quality: {result.quality_metrics.overall_score}/100")
print(f"Faces: {result.content_results.face_count}")

# Analyze entire directory
results = analyzer.analyze_directory(progress=True)

# Search your collection
high_quality_photos = analyzer.search_files(
    quality_min=80,
    has_faces=True,
    tags=['family', 'vacation']
)

# Get collection statistics
stats = analyzer.get_analysis_summary()
print(f"Total files: {stats['total_files']}")
print(f"Average quality: {stats['avg_quality']:.1f}")
```

## 📖 Documentation

### Core Concepts

#### Quality Assessment
The quality evaluator analyzes multiple aspects:
- **Blur Detection**: Uses Laplacian variance to detect blurry images
- **Brightness Analysis**: Evaluates optimal exposure levels
- **Contrast Assessment**: Measures image contrast ratios
- **Noise Detection**: Identifies noisy or grainy images
- **Sharpness Scoring**: Evaluates image sharpness using gradients

#### Content Identification
The content identifier recognizes:
- **Faces**: Using OpenCV Haar cascades with confidence scoring
- **Objects**: Edge-based detection with shape classification
- **Scenes**: Color and texture analysis for scene classification
- **Colors**: K-means clustering for dominant color extraction

#### Database Schema
The system stores:
- **Media Files**: File metadata, paths, and basic information
- **Quality Metrics**: All quality assessment scores and raw data
- **Content Analysis**: Face counts, objects, tags, and detection results

### Configuration

Create a configuration file to customize behavior:

```json
{
  "database": {
    "path": "my_media.db",
    "pool_size": 10
  },
  "quality": {
    "blur_threshold": 100.0,
    "brightness_min": 20,
    "brightness_max": 235
  },
  "content": {
    "enable_face_detection": true,
    "max_faces_per_image": 20,
    "face_confidence_threshold": 0.6
  },
  "processing": {
    "max_workers": 8,
    "batch_size": 100,
    "log_level": "INFO"
  }
}
```

Use with: `home-media-ai --config config.json analyze /path/to/media`

### Environment Variables

Configure using environment variables:

```bash
export HMEDIA_DATABASE__PATH="/custom/database.db"
export HMEDIA_PROCESSING__MAX_WORKERS=8
export HMEDIA_QUALITY__BLUR_THRESHOLD=150.0
```

## 🔧 Advanced Usage

### Quality-Based Organization

```bash
# Find your best photos
home-media-ai search --min-quality 90 --limit 50

# Identify low-quality images for cleanup
home-media-ai search --max-quality 30 --output low_quality.json

# Export quality report
home-media-ai export quality_analysis.csv --format csv
```

### Content Discovery

```bash
# Find all family gatherings
home-media-ai search --min-faces 5 --tag group --tag family

# Locate specific objects
home-media-ai search --object-class person --object-class dog

# Find text-containing images (screenshots, documents)
home-media-ai search --has-text
```

### Database Management

```bash
# Create regular backups
home-media-ai backup "/backup/$(date +%Y%m%d)_media.db"

# Export for external analysis
home-media-ai export analysis_results.json --include-raw

# View comprehensive statistics
home-media-ai stats
```

## 🏗️ Architecture

```
home_media_ai/
├── core/           # Main orchestration classes
│   ├── analyzer.py    # MediaAnalyzer - main entry point
│   └── database.py    # Database models and operations
├── quality/        # Quality assessment modules
│   ├── evaluator.py   # QualityEvaluator - main engine
│   └── metrics.py     # Quality metric data structures
├── content/        # Content identification modules
│   ├── identifier.py  # ContentIdentifier - detection engine
│   └── detection.py   # Detection result data structures
├── utils/          # Utility functions
│   ├── file_utils.py  # File operations and metadata
│   └── logging.py     # Logging configuration
├── config/         # Configuration management
│   └── settings.py    # Configuration classes and loading
└── cli.py         # Command-line interface
```

## 🎓 Learning Resources

This project serves as an educational resource for:

### Computer Vision Concepts
- **Image Quality Assessment**: Learn blur detection, noise analysis, and exposure evaluation
- **Object Detection**: Understand edge detection, contour analysis, and shape recognition
- **Face Detection**: Explore cascade classifiers and confidence scoring
- **Color Analysis**: Practice K-means clustering and color space conversions

### Software Engineering Best Practices
- **Modular Design**: See how to structure large Python projects
- **Configuration Management**: Learn flexible settings and environment variable handling
- **Database Design**: Understand SQLAlchemy ORM and schema design
- **CLI Development**: Study Click framework usage and user experience design
- **Documentation**: Examples of comprehensive project documentation

### Data Management
- **Metadata Extraction**: EXIF data reading and file system operations
- **Batch Processing**: Parallel processing and progress tracking
- **Search Algorithms**: Database indexing and query optimization
- **Duplicate Detection**: Content-based file comparison techniques

## 📋 Requirements

### Core Dependencies
- **Python 3.8+**
- **OpenCV**: Computer vision operations
- **Pillow**: Image processing
- **SQLAlchemy**: Database ORM
- **NumPy/Pandas**: Data manipulation
- **Click**: CLI framework

### Optional Dependencies
- **scikit-learn**: Advanced clustering and ML features
- **scikit-image**: Additional image processing
- **face-recognition**: Enhanced face detection (ML package)
- **pytesseract**: OCR text extraction

### System Requirements
- **Storage**: Database grows with collection size (~1-5MB per 1000 files)
- **Memory**: 2-4GB RAM recommended for large batch processing
- **CPU**: Multi-core processors benefit from parallel processing

## 🤝 Contributing

We welcome contributions! This project is designed to be educational, so contributions that improve learning value are especially appreciated.

### Areas for Contribution
- **Additional Quality Metrics**: Implement new image/video quality assessments
- **Enhanced Object Detection**: Integrate modern ML models (YOLO, SSD)
- **Face Recognition**: Add face encoding and recognition capabilities
- **Performance Optimization**: Improve processing speed and memory usage
- **Documentation**: Add tutorials, examples, and educational content

### Development Setup

```bash
# Clone repository
git clone https://github.com/ericwait/home-media-ai.git
cd home-media-ai

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting
black home_media_ai/
isort home_media_ai/

# Type checking
mypy home_media_ai/
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenCV**: Comprehensive computer vision library
- **scikit-image**: Image processing algorithms
- **SQLAlchemy**: Powerful Python ORM
- **Click**: Elegant command-line interfaces

---

**Ready to transform your media collection?** Start with `home-media-ai analyze /path/to/your/photos` and discover what's hidden in your memories! 🚀
