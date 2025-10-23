from .media import Media, MediaType, Base
from .scanner import MediaScanner, FileInfo
from .importer import MediaImporter
from .exif_extractor import ExifExtractor
from .media_query import MediaQuery
from .io import read_image_as_array, read_image_metadata
from .database import get_engine, get_session, session_scope, reset_engine

from .utils import (
    infer_media_type_from_extension,
    get_all_supported_extensions,
    calculate_file_hash,
    split_file_path,
    validate_file_extension,
    normalize_extension
)

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
