"""
Configuration settings for Home Media AI.

This module provides centralized configuration management for the entire toolkit.
It supports multiple configuration sources (files, environment variables, defaults)
and validation of settings.

Classes:
    Config: Main configuration class with validation and defaults
    
Functions:
    get_config: Get current configuration instance
    set_config: Update configuration settings
    load_config_file: Load configuration from file
    
Example:
    >>> from home_media_ai.config import get_config
    >>> config = get_config()
    >>> config.database.path = '/path/to/my/database.db'
    >>> config.quality.blur_threshold = 100.0
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field, asdict


@dataclass
class DatabaseConfig:
    """Database configuration settings.
    
    Attributes:
        path: Path to SQLite database file
        echo: Whether to echo SQL statements (for debugging)
        pool_size: Connection pool size for concurrent operations
        timeout: Database connection timeout in seconds
        backup_interval: Automatic backup interval in hours (0 to disable)
    """
    path: str = "home_media.db"
    echo: bool = False
    pool_size: int = 5
    timeout: int = 30
    backup_interval: int = 24


@dataclass 
class QualityConfig:
    """Quality assessment configuration.
    
    Attributes:
        blur_threshold: Threshold for blur detection (higher = more blur tolerance)
        brightness_min: Minimum acceptable brightness (0-255)
        brightness_max: Maximum acceptable brightness (0-255)
        contrast_min: Minimum acceptable contrast ratio
        noise_threshold: Threshold for noise detection
        enable_face_quality: Whether to assess face quality in images
        video_sample_frames: Number of frames to sample for video quality assessment
    """
    blur_threshold: float = 100.0
    brightness_min: int = 20
    brightness_max: int = 235
    contrast_min: float = 0.1
    noise_threshold: float = 0.5
    enable_face_quality: bool = True
    video_sample_frames: int = 10


@dataclass
class ContentConfig:
    """Content identification configuration.
    
    Attributes:
        enable_face_detection: Whether to detect faces in images
        enable_object_detection: Whether to detect objects in images
        face_confidence_threshold: Minimum confidence for face detection
        object_confidence_threshold: Minimum confidence for object detection
        max_faces_per_image: Maximum number of faces to detect per image
        enable_text_extraction: Whether to extract text from images (OCR)
        enable_scene_classification: Whether to classify scenes/locations
    """
    enable_face_detection: bool = True
    enable_object_detection: bool = True
    face_confidence_threshold: float = 0.6
    object_confidence_threshold: float = 0.5
    max_faces_per_image: int = 20
    enable_text_extraction: bool = False
    enable_scene_classification: bool = True


@dataclass
class ProcessingConfig:
    """Processing and performance configuration.
    
    Attributes:
        max_workers: Maximum number of worker processes for parallel processing
        batch_size: Number of files to process in each batch
        memory_limit_mb: Memory limit per worker process in MB
        cache_size: Size of image cache in number of images
        temp_dir: Temporary directory for processing
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        progress_bar: Whether to show progress bars during processing
    """
    max_workers: int = 4
    batch_size: int = 100
    memory_limit_mb: int = 1024
    cache_size: int = 100
    temp_dir: str = "/tmp/home_media_ai"
    log_level: str = "INFO"
    progress_bar: bool = True


@dataclass
class Config:
    """Main configuration class for Home Media AI.
    
    This class holds all configuration settings for the toolkit, organized
    into logical sections. Settings can be loaded from files, environment
    variables, or set programmatically.
    
    Attributes:
        database: Database-related settings
        quality: Quality assessment settings
        content: Content identification settings
        processing: Processing and performance settings
        
    Example:
        >>> config = Config()
        >>> config.database.path = '/my/database.db'
        >>> config.quality.blur_threshold = 150.0
        >>> config.save_to_file('my_config.json')
    """
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    content: ContentConfig = field(default_factory=ContentConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create Config instance from dictionary.
        
        Args:
            data: Dictionary containing configuration data
            
        Returns:
            Config instance with settings from dictionary
            
        Example:
            >>> data = {'database': {'path': '/custom/path.db'}}
            >>> config = Config.from_dict(data)
        """
        return cls(
            database=DatabaseConfig(**data.get('database', {})),
            quality=QualityConfig(**data.get('quality', {})),
            content=ContentConfig(**data.get('content', {})),
            processing=ProcessingConfig(**data.get('processing', {}))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Config instance to dictionary.
        
        Returns:
            Dictionary representation of configuration
            
        Example:
            >>> config = Config()
            >>> data = config.to_dict()
            >>> print(data['database']['path'])
        """
        return asdict(self)
    
    def save_to_file(self, path: Union[str, Path]) -> None:
        """Save configuration to JSON file.
        
        Args:
            path: Path to save configuration file
            
        Example:
            >>> config = Config()
            >>> config.save_to_file('my_config.json')
        """
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, path: Union[str, Path]) -> 'Config':
        """Load configuration from JSON file.
        
        Args:
            path: Path to configuration file
            
        Returns:
            Config instance loaded from file
            
        Example:
            >>> config = Config.load_from_file('my_config.json')
        """
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def update_from_env(self) -> None:
        """Update configuration from environment variables.
        
        Environment variables should be prefixed with 'HMEDIA_' and use
        double underscores to separate nested keys.
        
        Example:
            >>> os.environ['HMEDIA_DATABASE__PATH'] = '/my/db.db'
            >>> config = Config()
            >>> config.update_from_env()
        """
        prefix = 'HMEDIA_'
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
                
            # Remove prefix and split on double underscores
            config_key = key[len(prefix):].lower()
            parts = config_key.split('__')
            
            if len(parts) == 2:
                section, setting = parts
                if hasattr(self, section):
                    section_obj = getattr(self, section)
                    if hasattr(section_obj, setting):
                        # Convert value to appropriate type
                        current_value = getattr(section_obj, setting)
                        if isinstance(current_value, bool):
                            value = value.lower() in ('true', '1', 'yes', 'on')
                        elif isinstance(current_value, int):
                            value = int(value)
                        elif isinstance(current_value, float):
                            value = float(value)
                        
                        setattr(section_obj, setting, value)


# Global configuration instance
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.
    
    Returns:
        Global Config instance
        
    Example:
        >>> config = get_config()
        >>> print(config.database.path)
    """
    global _global_config
    if _global_config is None:
        _global_config = Config()
        _global_config.update_from_env()
        
        # Try to load from default config file
        default_config_path = Path.home() / '.home_media_ai' / 'config.json'
        if default_config_path.exists():
            try:
                _global_config = Config.load_from_file(default_config_path)
                _global_config.update_from_env()  # Environment overrides file
            except Exception as e:
                logging.warning(f"Failed to load config from {default_config_path}: {e}")
    
    return _global_config


def set_config(config: Config) -> None:
    """Set the global configuration instance.
    
    Args:
        config: Config instance to set as global
        
    Example:
        >>> config = Config()
        >>> config.database.path = '/my/db.db'
        >>> set_config(config)
    """
    global _global_config
    _global_config = config


def load_config_file(path: Union[str, Path]) -> Config:
    """Load configuration from file and set as global.
    
    Args:
        path: Path to configuration file
        
    Returns:
        Loaded Config instance
        
    Example:
        >>> config = load_config_file('my_config.json')
    """
    config = Config.load_from_file(path)
    config.update_from_env()  # Environment overrides file
    set_config(config)
    return config