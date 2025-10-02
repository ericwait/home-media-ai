import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, Optional, Set, Tuple
from dataclasses import dataclass, field

from .constants import MEDIA_TYPE_EXTENSIONS

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False


@dataclass
class FileInfo:
    path: str
    size: int
    extension: str
    timestamp: datetime
    media_type: str
    exif_data: Dict = field(default_factory=dict)  # Added for EXIF metadata


class MediaScanner:
    def __init__(self, root_path: str, exif_extractor=None):
        self.root_path = Path(root_path)
        self.exif_extractor = exif_extractor
        # Use shared extension definitions
        self.media_type_extensions = MEDIA_TYPE_EXTENSIONS

    def _get_media_type(self, extension: str) -> Optional[str]:
        ext_lower = extension.lower()
        for media_type, extensions in self.media_type_extensions.items():
            if ext_lower in extensions:
                return media_type
        return None

    def _get_exif_timestamp_pil(self, file_path: Path) -> Optional[datetime]:
        if not HAS_PIL:
            return None

        try:
            with Image.open(file_path) as img:
                exif = img._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == 'DateTimeOriginal' or tag == 'DateTime':
                            return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
        except Exception:
            pass
        return None

    def _get_exif_timestamp_exifread(self, file_path: Path) -> Optional[datetime]:
        if not HAS_EXIFREAD:
            return None

        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f)

                for tag_name in ['EXIF DateTimeOriginal', 'Image DateTime', 'EXIF DateTime']:
                    if tag_name in tags:
                        timestamp_str = str(tags[tag_name])
                        return datetime.strptime(timestamp_str, '%Y:%m:%d %H:%M:%S')
        except Exception:
            pass
        return None

    def _get_file_timestamp(self, file_path: Path) -> Optional[datetime]:
        # Try EXIF data first
        timestamp = self._get_exif_timestamp_pil(file_path)
        if timestamp:
            return timestamp

        timestamp = self._get_exif_timestamp_exifread(file_path)
        if timestamp:
            return timestamp

        # Fallback to file creation time
        try:
            stat_result = file_path.stat()
            return datetime.fromtimestamp(stat_result.st_ctime)
        except OSError:
            return None

    def scan_files(self, progress_callback=None) -> Iterator[FileInfo]:
        file_count = 0

        for root, dirs, files in os.walk(self.root_path):
            for filename in files:
                file_path = Path(root) / filename

                if not file_path.is_file():
                    continue

                extension = file_path.suffix
                media_type = self._get_media_type(extension)

                if not media_type:
                    continue

                timestamp = self._get_file_timestamp(file_path)
                if not timestamp:
                    continue

                try:
                    file_size = file_path.stat().st_size
                except OSError:
                    continue

                # Extract EXIF metadata if extractor is available
                exif_data = {}
                if self.exif_extractor:
                    try:
                        exif_data = self.exif_extractor.extract_metadata(str(file_path))
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Warning: Failed to extract EXIF from {file_path}: {e}")

                file_count += 1
                if progress_callback and file_count % 100 == 0:
                    progress_callback(f"Scanned {file_count} files...")

                yield FileInfo(
                    path=str(file_path),
                    size=file_size,
                    extension=extension,
                    timestamp=timestamp,
                    media_type=media_type,
                    exif_data=exif_data
                )

    def group_by_timestamp(self, files: Iterator[FileInfo]) -> Dict[datetime, Dict[str, FileInfo]]:
        groups = {}

        for file_info in files:
            if file_info.timestamp not in groups:
                groups[file_info.timestamp] = {}
            groups[file_info.timestamp][file_info.media_type] = file_info

        return groups

    def identify_pairs(self, grouped_files: Dict[datetime, Dict[str, FileInfo]]) -> Iterator[Tuple[FileInfo, Optional[FileInfo]]]:
        for timestamp, files_by_type in grouped_files.items():
            raw_file = files_by_type.get('raw_image')
            jpeg_file = files_by_type.get('jpeg')

            if raw_file and jpeg_file:
                yield (raw_file, jpeg_file)
            elif raw_file:
                yield (raw_file, None)
            else:
                for media_type, file_info in files_by_type.items():
                    yield (file_info, None)
