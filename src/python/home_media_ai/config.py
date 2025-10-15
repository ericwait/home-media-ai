"""
Configuration management for Home Media AI.

Loads configuration from YAML files and environment variables.
Provides path resolution for cross-platform storage root mapping.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class PathResolutionConfig:
    """Configuration for path resolution strategy."""
    strategy: str = "mapped"  # mapped, database, local_only
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
                Path(__file__).parent.parent.parent.parent / "config.yaml",
                Path.home() / ".config" / "home-media-ai" / "config.yaml",
            ]
            config_file = None
            for path in search_paths:
                if path.exists():
                    config_file = path
                    break

        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f) or {}
                config = cls.from_dict(data)
                # Apply environment variable overrides
                config._apply_env_overrides()
                return config
        else:
            # No config file found, use defaults with env overrides
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

    def resolve_path(self, storage_root: Optional[str], directory: Optional[str],
                     filename: str) -> Path:
        """Resolve a path from database components to local filesystem path.

        Args:
            storage_root: Database storage root (e.g., /volume1/photos)
            directory: Relative directory from storage root (e.g., 2024/January)
            filename: Filename (e.g., IMG_001.CR2)

        Returns:
            Resolved Path object

        Raises:
            FileNotFoundError: If path resolution strategy is 'local_only' and no mapping exists
        """
        strategy = self.config.path_resolution.strategy

        # Build path using mapped storage root
        local_root = self._get_local_storage_root(storage_root)

        if local_root:
            # Use mapped root
            if directory:
                local_path = Path(local_root) / directory / filename
            else:
                local_path = Path(local_root) / filename
        elif strategy == "local_only":
            raise FileNotFoundError(
                f"No local mapping found for storage_root: {storage_root} "
                f"and strategy is 'local_only'"
            )
        else:
            # Fall back to database path
            if storage_root:
                if directory:
                    local_path = Path(storage_root) / directory / filename
                else:
                    local_path = Path(storage_root) / filename
            else:
                # No storage root at all, just use directory/filename
                if directory:
                    local_path = Path(directory) / filename
                else:
                    local_path = Path(filename)

        # Normalize path separators if configured
        if self.config.path_resolution.normalize_separators:
            local_path = Path(str(local_path).replace('\\', os.sep).replace('/', os.sep))

        # Validate existence if configured
        if self.config.path_resolution.validate_exists and not local_path.exists():
            # Try falling back to database path if we haven't already
            if local_root and strategy == "mapped":
                fallback_path = self._try_database_path(storage_root, directory, filename)
                if fallback_path and fallback_path.exists():
                    return fallback_path

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
        for db_root, local_root in self.config.storage_roots.items():
            if db_storage_root.startswith(db_root):
                matches.append((len(db_root), db_root, local_root))

        if matches:
            # Return longest matching prefix
            matches.sort(reverse=True)
            _, db_root, local_root = matches[0]
            # Append the remaining path
            remainder = db_storage_root[len(db_root):].lstrip('/')
            if remainder:
                return str(Path(local_root) / remainder)
            return local_root

        # No mapping found
        return self.config.default_storage_root

    def _try_database_path(self, storage_root: Optional[str], directory: Optional[str],
                          filename: str) -> Optional[Path]:
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
