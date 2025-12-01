"""
Configuration management for Home Media AI.

Loads configuration from YAML files and environment variables.
Provides path resolution for cross-platform storage root mapping.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class PathResolutionConfig:
    """Configuration for path resolution strategy."""
    strategy: str = "config_only"  # config_only, mapped, database
    validate_exists: bool = False
    normalize_separators: bool = True


@dataclass
class ScanningConfig:
    """Configuration for file scanning/importing."""
    storage_root: Optional[str] = None
    batch_size: int = 100


@dataclass
class WebConfig:
    """Configuration for web service."""
    port: int = 5100
    host: str = "0.0.0.0"
    media_root: Optional[str] = None


@dataclass
class DatabaseConfig:
    """Configuration for database connection."""
    uri: Optional[str] = None


@dataclass
class LoggingConfig:
    """Configuration for logging."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class Config:
    """Main configuration class."""
    storage_roots: Dict[str, str] = field(default_factory=dict)
    default_storage_root: Optional[str] = None
    path_resolution: PathResolutionConfig = field(default_factory=PathResolutionConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    scanning: ScanningConfig = field(default_factory=ScanningConfig)
    web: WebConfig = field(default_factory=WebConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create Config from dictionary."""
        return cls(
            storage_roots=data.get('storage_roots', {}),
            default_storage_root=data.get('default_storage_root'),
            path_resolution=PathResolutionConfig(**data.get('path_resolution', {})),
            database=DatabaseConfig(**data.get('database', {})),
            scanning=ScanningConfig(**data.get('scanning', {})),
            web=WebConfig(**data.get('web', {})),
            logging=LoggingConfig(**data.get('logging', {}))
        )

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'Config':
        """Load configuration from file.

        Args:
            config_path: Path to config file. If None, searches for config.yaml
                        in current directory and project root.

        Returns:
            Config instance
        """
        if config_path:
            config_file = Path(config_path)
        else:
            # Search for config.yaml in standard locations
            search_paths = [
                Path.cwd() / "config.yaml",
                Path(__file__).parent.parent / "config.yaml",
                Path.home() / ".config" / "home-media-ai" / "config.yaml",
            ]
            config_file = next((path for path in search_paths if path.exists()), None)

        if config_file and config_file.exists() and HAS_YAML:
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f) or {}
                config = cls.from_dict(data)
                # Apply environment variable overrides
                config._apply_env_overrides()
                return config
        else:
            # No config file found or yaml not available, use defaults with env overrides
            config = cls()
            config._apply_env_overrides()
            return config

    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        # Database URI
        if env_uri := os.getenv('HOME_MEDIA_AI_URI'):
            self.database.uri = env_uri

        # Web service media root
        if env_media_root := os.getenv('PHOTO_ROOT'):
            self.web.media_root = env_media_root

        # Scanning storage root
        if env_scan_root := os.getenv('STORAGE_ROOT'):
            self.scanning.storage_root = env_scan_root


class PathResolver:
    """Resolves database paths to local filesystem paths.

    Handles storage root mapping for cross-platform compatibility.
    """

    def __init__(self, config: Optional[Config] = None):
        """Initialize path resolver.

        Args:
            config: Configuration instance. If None, loads default config.
        """
        self.config = config or Config.load()

    def resolve_path(self, storage_root: Optional[str], directory: Optional[str], filename: str) -> Path:
        """Resolve a path from database components to local filesystem path.

        Args:
            storage_root: Database storage root (e.g., tiger/photo/RAW or /volume1/photos)
                         Ignored when strategy is 'config_only'
            directory: Relative directory from storage root (e.g., 2024/January)
            filename: Filename (e.g., IMG_001.CR2)

        Returns:
            Resolved Path object

        Raises:
            ValueError: If strategy requires config but no default_storage_root is set
        """
        strategy = self.config.path_resolution.strategy

        if strategy == "config_only":
            # Ignore database storage_root entirely, use config default_storage_root
            if not self.config.default_storage_root:
                raise ValueError(
                    "strategy='config_only' requires default_storage_root to be set in config"
                )
            local_root = self.config.default_storage_root

        elif strategy == "mapped":
            # Try to map database storage_root using config, fall back to default
            local_root = self._get_local_storage_root(storage_root)
            if not local_root:
                raise FileNotFoundError(
                    f"No mapping found for storage_root: {storage_root}. "
                    f"Add mapping to config or use strategy='config_only'"
                )

        elif strategy == "database":
            # Use database storage_root directly (no config mapping)
            local_root = storage_root
            if not local_root:
                raise ValueError("Database storage_root is None and strategy='database'")

        else:
            raise ValueError(f"Unknown path resolution strategy: {strategy}")

        # Build the full path
        if directory:
            local_path = Path(local_root) / directory / filename
        else:
            local_path = Path(local_root) / filename

        # Normalize path separators if configured
        if self.config.path_resolution.normalize_separators:
            local_path = Path(str(local_path).replace('\\', os.sep).replace('/', os.sep))

        return local_path

    def _get_local_storage_root(self, db_storage_root: Optional[str]) -> Optional[str]:
        """Get local storage root for a database storage root.

        Args:
            db_storage_root: Storage root value from database

        Returns:
            Local storage root path, or None if no mapping exists
        """
        if not db_storage_root:
            return self.config.default_storage_root

        # Check for exact match
        if db_storage_root in self.config.storage_roots:
            return self.config.storage_roots[db_storage_root]

        # Check for partial matches (longest match wins)
        # This handles cases like /volume1/photos/raw -> /mnt/media
        matches = []
        matches.extend(
            (len(db_root), db_root, local_root)
            for db_root, local_root in self.config.storage_roots.items()
            if db_storage_root.startswith(db_root)
        )
        if matches:
            # Return longest matching prefix
            matches.sort(reverse=True)
            _, db_root, local_root = matches[0]
            # Append the remaining path
            remainder = db_storage_root[len(db_root):].lstrip('/')
            return str(Path(local_root) / remainder) if remainder else local_root
        # No mapping found
        return self.config.default_storage_root

    def _try_database_path(self, storage_root: Optional[str], directory: Optional[str], filename: str) -> Optional[Path]:
        """Try to build path using database values directly.

        Args:
            storage_root: Database storage root
            directory: Database directory
            filename: Database filename

        Returns:
            Path if it can be constructed, None otherwise
        """
        if not storage_root:
            return None

        if directory:
            return Path(storage_root) / directory / filename
        else:
            return Path(storage_root) / filename

    def get_storage_root_for_import(self) -> str:
        """Get the storage root to use when importing new files.

        Returns:
            Storage root path to store in database
        """
        if self.config.scanning.storage_root:
            return self.config.scanning.storage_root
        elif self.config.default_storage_root:
            return self.config.default_storage_root
        else:
            raise ValueError(
                "No storage_root configured for importing. "
                "Set scanning.storage_root or default_storage_root in config.yaml"
            )


# Global configuration instance
_global_config: Optional[Config] = None
_global_resolver: Optional[PathResolver] = None


def get_config() -> Config:
    """Get global configuration instance.

    Returns:
        Config instance
    """
    global _global_config
    if _global_config is None:
        _global_config = Config.load()
    return _global_config


def get_path_resolver() -> PathResolver:
    """Get global path resolver instance.

    Returns:
        PathResolver instance
    """
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = PathResolver(get_config())
    return _global_resolver


def set_config(config: Config):
    """Set global configuration instance.

    Args:
        config: Config instance to use globally
    """
    global _global_config, _global_resolver
    _global_config = config
    _global_resolver = PathResolver(config)
