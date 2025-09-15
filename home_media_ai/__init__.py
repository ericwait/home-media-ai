"""
Home Media AI - AI-powered home media management and analysis toolkit.

This package provides tools for:
1. Evaluating the quality of images and videos
2. Identifying contents using computer vision and AI
3. Creating searchable databases for quick content retrieval

The package is designed to handle large collections (700k+ images, terabytes of video)
with efficient processing and comprehensive documentation to help users learn.

Modules:
    quality: Image and video quality assessment tools
    content: Content identification and analysis tools  
    database: Database management and search capabilities
    utils: Common utilities and helper functions
    config: Configuration management
    cli: Command-line interface

Example:
    >>> from home_media_ai import MediaAnalyzer
    >>> analyzer = MediaAnalyzer('/path/to/media')
    >>> results = analyzer.analyze_directory()
"""

__version__ = "0.1.0"
__author__ = "Eric Wait"
__email__ = "ericwait@example.com"

# Import main classes for easy access
from .core.analyzer import MediaAnalyzer
from .core.database import MediaDatabase
from .quality.evaluator import QualityEvaluator
from .content.identifier import ContentIdentifier

__all__ = [
    "MediaAnalyzer",
    "MediaDatabase", 
    "QualityEvaluator",
    "ContentIdentifier",
]