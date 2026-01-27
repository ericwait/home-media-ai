"""
Configuration management for home-media.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Default locations to search for config.yaml
CONFIG_SEARCH_PATHS = [
    Path("config.yaml"),
    Path("src/python/config.yaml"),
    Path.home() / ".home_media" / "config.yaml",
]


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Specific path to config file. If None, searches default locations.

    Returns:
        Dictionary containing configuration.

    Raises:
        FileNotFoundError: If no config file is found.
    """
    path_to_load = None

    if config_path:
        if config_path.exists():
            path_to_load = config_path
        else:
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        for path in CONFIG_SEARCH_PATHS:
            if path.exists():
                path_to_load = path
                break

    if not path_to_load:
        raise FileNotFoundError(
            "No config file found. Please create config.yaml or provide a path."
        )

    logger.info("Loading config from %s", path_to_load)
    
    with open(path_to_load, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


def get_photos_root(config: Dict[str, Any]) -> Path:
    """
    Get the photos root directory from config.

    Args:
        config: Configuration dictionary

    Returns:
        Path to photos root directory
    """
    root_str = config.get("photos_root_original")
    if not root_str:
        # Fallback/Error if not defined. 
        # For now, let's raise because the system depends on it.
        raise ValueError("Config missing 'photos_root_original' setting.")
    
    return Path(root_str)


def get_db_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get the database configuration from config.

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary containing database settings
    """
    db_config = config.get("database")
    if not db_config:
        raise ValueError("Config missing 'database' section.")
    return db_config


def get_redis_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get the redis configuration from config.

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary containing redis settings
    """
    redis_config = config.get("redis")
    if not redis_config:
        # Return default defaults if missing, or raise? 
        # Better to return defaults or a minimal dict so callers can handle it
        return {
            "host": "localhost",
            "port": 6379,
            "password": None,
            "db": 0
        }
    return redis_config
