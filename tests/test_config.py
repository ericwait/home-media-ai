"""
Test configuration management.
"""

import pytest
import os
import tempfile
import json
from pathlib import Path

from home_media_ai.config import Config, get_config, set_config, load_config_file


class TestConfig:
    """Test configuration classes and functions."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        
        # Test default database settings
        assert config.database.path == "home_media.db"
        assert config.database.echo is False
        assert config.database.pool_size == 5
        
        # Test default quality settings
        assert config.quality.blur_threshold == 100.0
        assert config.quality.brightness_min == 20
        assert config.quality.brightness_max == 235
        
        # Test default content settings
        assert config.content.enable_face_detection is True
        assert config.content.face_confidence_threshold == 0.6
        
        # Test default processing settings
        assert config.processing.max_workers == 4
        assert config.processing.batch_size == 100
    
    def test_config_to_dict(self):
        """Test converting config to dictionary."""
        config = Config()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert 'database' in config_dict
        assert 'quality' in config_dict
        assert 'content' in config_dict
        assert 'processing' in config_dict
        
        assert config_dict['database']['path'] == "home_media.db"
        assert config_dict['quality']['blur_threshold'] == 100.0
    
    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        config_data = {
            'database': {'path': '/custom/path.db', 'pool_size': 10},
            'quality': {'blur_threshold': 150.0},
            'content': {'enable_face_detection': False},
            'processing': {'max_workers': 8}
        }
        
        config = Config.from_dict(config_data)
        
        assert config.database.path == '/custom/path.db'
        assert config.database.pool_size == 10
        assert config.quality.blur_threshold == 150.0
        assert config.content.enable_face_detection is False
        assert config.processing.max_workers == 8
        
        # Check that defaults are preserved for unspecified values
        assert config.database.echo is False  # Default value
        assert config.quality.brightness_min == 20  # Default value
    
    def test_config_file_operations(self):
        """Test saving and loading config files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
        
        try:
            # Create and save config
            original_config = Config()
            original_config.database.path = '/test/path.db'
            original_config.quality.blur_threshold = 200.0
            original_config.save_to_file(config_path)
            
            # Load config
            loaded_config = Config.load_from_file(config_path)
            
            assert loaded_config.database.path == '/test/path.db'
            assert loaded_config.quality.blur_threshold == 200.0
            assert loaded_config.database.echo is False  # Default preserved
            
        finally:
            os.unlink(config_path)
    
    def test_environment_variable_override(self):
        """Test environment variable configuration override."""
        # Set environment variables
        os.environ['HMEDIA_DATABASE__PATH'] = '/env/test.db'
        os.environ['HMEDIA_QUALITY__BLUR_THRESHOLD'] = '250.0'
        os.environ['HMEDIA_CONTENT__ENABLE_FACE_DETECTION'] = 'false'
        os.environ['HMEDIA_PROCESSING__MAX_WORKERS'] = '16'
        
        try:
            config = Config()
            config.update_from_env()
            
            assert config.database.path == '/env/test.db'
            assert config.quality.blur_threshold == 250.0
            assert config.content.enable_face_detection is False
            assert config.processing.max_workers == 16
            
        finally:
            # Clean up environment variables
            for key in ['HMEDIA_DATABASE__PATH', 'HMEDIA_QUALITY__BLUR_THRESHOLD',
                       'HMEDIA_CONTENT__ENABLE_FACE_DETECTION', 'HMEDIA_PROCESSING__MAX_WORKERS']:
                if key in os.environ:
                    del os.environ[key]
    
    def test_global_config(self):
        """Test global configuration management."""
        # Create custom config
        custom_config = Config()
        custom_config.database.path = '/global/test.db'
        
        # Set as global
        set_config(custom_config)
        
        # Get global config
        retrieved_config = get_config()
        assert retrieved_config.database.path == '/global/test.db'
        
        # Test that it's the same instance
        assert retrieved_config is custom_config
    
    def test_load_config_file_function(self):
        """Test the load_config_file convenience function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_data = {
                'database': {'path': '/loaded/test.db'},
                'quality': {'blur_threshold': 300.0}
            }
            json.dump(config_data, f)
            config_path = f.name
        
        try:
            # Load config file and set as global
            loaded_config = load_config_file(config_path)
            
            assert loaded_config.database.path == '/loaded/test.db'
            assert loaded_config.quality.blur_threshold == 300.0
            
            # Verify it was set as global
            global_config = get_config()
            assert global_config.database.path == '/loaded/test.db'
            
        finally:
            os.unlink(config_path)