# Core imports that should always be available
from .media import Media, MediaType, Base
from .database import get_engine, get_session, session_scope, reset_engine
from .utils import (
    infer_media_type_from_extension,
    get_all_supported_extensions,
    calculate_file_hash,
    split_file_path,
    validate_file_extension,
    normalize_extension
)

# Optional imports - these may not be needed for basic usage (e.g., web viewer)
try:
    from .scanner import MediaScanner, FileInfo
except ImportError:
    MediaScanner = None
    FileInfo = None

try:
    from .importer import MediaImporter
except ImportError:
    MediaImporter = None

try:
    from .exif_extractor import ExifExtractor
except ImportError:
    ExifExtractor = None

try:
    from .media_query import MediaQuery
except ImportError:
    MediaQuery = None

try:
    from .io import read_image_as_array, read_image_metadata
except ImportError:
    read_image_as_array = None
    read_image_metadata = None

__version__ = "1.0.0"
__all__ = [
    "Media", "MediaType", "Base",
    "MediaScanner", "FileInfo",
    "MediaImporter",
    "ExifExtractor",
    "MediaQuery",
    "read_image_as_array",
    "read_image_metadata",
    "get_engine",
    "get_session",
    "session_scope",
    "reset_engine",
    "infer_media_type_from_extension",
    "get_all_supported_extensions",
    "calculate_file_hash",
    "split_file_path",
    "validate_file_extension",
    "normalize_extension"
]
