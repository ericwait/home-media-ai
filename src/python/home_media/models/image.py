"""
Image and ImageFile models.

An Image represents a moment in time - a single capture event.
Multiple files may represent the same Image (RAW, JPEG, XMP sidecar, etc.).

These models are designed to:
- Work seamlessly with pandas DataFrames
- Support lazy-loading of metadata (EXIF extracted on demand)
- Be serializable for future database storage
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from home_media.models.enums import FileFormat, FileRole


@dataclass
class ImageFile:
    """
    Represents a single file that is part of an Image.

    An Image may have multiple ImageFiles:
    - The original RAW capture
    - A JPEG preview/cover
    - An XMP sidecar with edits
    - Exported versions

    Attributes:
        filename: Full filename including extension
        suffix: The part after base_name (e.g., ".RAW-02.ORIGINAL.dng")
        extension: File extension (e.g., ".dng")
        file_path: Absolute path to the file
        file_size_bytes: Size of the file in bytes
        file_created_at: File system creation time
        file_modified_at: File system modification time
        format: Detected file format (FileFormat enum)
        role: Role this file plays (FileRole enum)
        file_hash: Optional hash for deduplication (lazy-loaded)
        width: Image width in pixels (lazy-loaded from metadata)
        height: Image height in pixels (lazy-loaded from metadata)
    """
    filename: str
    suffix: str
    extension: str
    file_path: Path
    file_size_bytes: int
    file_created_at: datetime
    file_modified_at: datetime
    format: FileFormat = FileFormat.UNKNOWN
    role: FileRole = FileRole.UNKNOWN
    file_hash: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

    @classmethod
    def from_path(cls, file_path: Path, base_name: str) -> "ImageFile":
        """
        Create an ImageFile from a file path.

        Args:
            file_path: Path to the file
            base_name: The base name of the parent Image

        Returns:
            An ImageFile instance with basic metadata populated
        """
        stats = file_path.stat()
        filename = file_path.name
        suffix = filename[len(base_name):]
        extension = file_path.suffix.lower()

        # Detect format from extension
        fmt = FileFormat.from_extension(extension)

        # Infer role from suffix and format
        role = cls._infer_role(suffix, fmt)

        return cls(
            filename=filename,
            suffix=suffix,
            extension=extension,
            file_path=file_path,
            file_size_bytes=stats.st_size,
            file_created_at=datetime.fromtimestamp(stats.st_ctime),
            file_modified_at=datetime.fromtimestamp(stats.st_mtime),
            format=fmt,
            role=role,
        )

    @staticmethod
    def _infer_role(suffix: str, fmt: FileFormat) -> FileRole:
        """Infer the file role from suffix and format."""
        suffix_upper = suffix.upper()

        # Sidecar files
        if fmt.is_sidecar:
            return FileRole.SIDECAR

        # Google Pixel patterns
        if ".COVER." in suffix_upper:
            return FileRole.COVER
        if ".ORIGINAL." in suffix_upper:
            return FileRole.ORIGINAL

        # Numbered derivatives (_001, _002, etc.)
        if any(f"_{i:03d}" in suffix for i in range(1, 100)):
            return FileRole.DERIVATIVE

        # RAW files are typically originals
        if fmt.is_raw:
            return FileRole.ORIGINAL

        # Single JPEG might be original or export
        if fmt == FileFormat.JPEG:
            # If it's just .jpg with no other suffix, likely original
            if suffix.lower() in (".jpg", ".jpeg"):
                return FileRole.ORIGINAL
            else:
                return FileRole.EXPORT

        return FileRole.UNKNOWN

    def populate_hash(self, algorithm: str = "sha256") -> bool:
        """
        Calculate and populate the file hash.

        Args:
            algorithm: Hash algorithm to use (default: "sha256")

        Returns:
            True if hash was calculated successfully, False otherwise

        Example:
            >>> image_file = ImageFile.from_path(Path("/photos/IMG_1234.jpg"), "IMG_1234")
            >>> image_file.populate_hash()
            >>> print(image_file.file_hash)
        """
        try:
            import hashlib

            hash_obj = hashlib.new(algorithm)
            with open(self.file_path, "rb") as f:
                # Read in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)

            self.file_hash = hash_obj.hexdigest()
            return True

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Failed to calculate hash for %s: %s", self.file_path, e)
            return False

    def populate_dimensions(self) -> bool:
        """
        Extract and populate image dimensions (width and height).

        This works for both RAW and standard image formats:
        - RAW files: Uses exifread to extract dimensions from EXIF
        - Standard formats: Uses Pillow to read image dimensions

        Returns:
            True if dimensions were extracted successfully, False otherwise

        Example:
            >>> image_file = ImageFile.from_path(Path("/photos/IMG_1234.CR2"), "IMG_1234")
            >>> image_file.populate_dimensions()
            >>> print(f"{image_file.width}x{image_file.height}")
        """
        if not self.file_path.exists() or not self.file_path.is_file():
            return False

        try:
            # For RAW files, use exifread
            if self.format.is_raw:
                return self._extract_dimensions_exifread()
            # For standard image formats, use Pillow
            elif self.format.is_image:
                return self._extract_dimensions_pillow()
            else:
                # Not an image file
                return False

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Failed to extract dimensions from %s: %s", self.file_path, e)
            return False

    def _extract_dimensions_pillow(self) -> bool:
        """Extract dimensions using Pillow."""
        try:
            from PIL import Image as PILImage

            with PILImage.open(self.file_path) as img:
                self.width = img.width
                self.height = img.height
                return True

        except Exception:
            return False

    def _extract_dimensions_exifread(self) -> bool:
        """Extract dimensions from RAW files using exifread."""
        try:
            import exifread

            with open(self.file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)

                if not tags:
                    return False

                # Try different EXIF tags for dimensions
                width = (
                    tags.get("EXIF ExifImageWidth") or
                    tags.get("Image ImageWidth") or
                    tags.get("Image PixelXDimension")
                )
                height = (
                    tags.get("EXIF ExifImageLength") or
                    tags.get("Image ImageLength") or
                    tags.get("Image PixelYDimension")
                )

                if width and height:
                    self.width = int(str(width))
                    self.height = int(str(height))
                    return True

                return False

        except Exception:
            return False

    def to_dict(self) -> dict:
        """Convert to dictionary for pandas DataFrame."""
        return {
            "filename": self.filename,
            "suffix": self.suffix,
            "extension": self.extension,
            "file_path": str(self.file_path),
            "file_size_bytes": self.file_size_bytes,
            "file_created_at": self.file_created_at,
            "file_modified_at": self.file_modified_at,
            "format": self.format.value,
            "role": self.role.name,
            "file_hash": self.file_hash,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class Image:
    """
    Represents a moment in time - a single capture event.

    An Image is identified by its base_name and subdirectory.
    Multiple files may belong to the same Image (RAW, JPEG, XMP, etc.).

    Attributes:
        base_name: Common identifier (e.g., "2025-01-01_00-28-40" or "PXL_20251210_200246684")
        subdirectory: Relative path from photos_root (e.g., "2025/01/01")
        files: List of ImageFile instances belonging to this Image
        captured_at: When the photo was taken (from EXIF, lazy-loaded)

        Global metadata (lazy-loaded from EXIF):
        - camera_make, camera_model, lens
        - gps_latitude, gps_longitude
        - title, description, rating
    """
    base_name: str
    subdirectory: str
    files: List[ImageFile] = field(default_factory=list)

    # Global metadata - lazy loaded from EXIF
    captured_at: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    title: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[int] = None

    # Housekeeping
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def file_count(self) -> int:
        """Number of files belonging to this Image."""
        return len(self.files)

    @property
    def suffixes(self) -> List[str]:
        """List of all suffixes for this Image's files."""
        return [f.suffix for f in self.files]

    @property
    def total_size_bytes(self) -> int:
        """Total size of all files in bytes."""
        return sum(f.file_size_bytes for f in self.files)

    @property
    def earliest_file_date(self) -> Optional[datetime]:
        """Earliest file creation date across all files."""
        return min(f.file_created_at for f in self.files) if self.files else None

    @property
    def latest_file_date(self) -> Optional[datetime]:
        """Latest file modification date across all files."""
        return max(f.file_modified_at for f in self.files) if self.files else None

    @property
    def original_file(self) -> Optional[ImageFile]:
        """Get the original file (RAW or primary capture)."""
        for f in self.files:
            if f.role == FileRole.ORIGINAL:
                return f
        # Fallback: return first RAW file
        for f in self.files:
            if f.format.is_raw:
                return f
        # Fallback: return first file
        return self.files[0] if self.files else None

    @property
    def has_raw(self) -> bool:
        """Check if this Image has a RAW file."""
        return any(f.format.is_raw for f in self.files)

    @property
    def has_jpeg(self) -> bool:
        """Check if this Image has a JPEG file."""
        return any(f.format == FileFormat.JPEG for f in self.files)

    @property
    def has_sidecar(self) -> bool:
        """Check if this Image has a sidecar file (XMP, etc.)."""
        return any(f.role == FileRole.SIDECAR for f in self.files)

    def add_file(self, image_file: ImageFile) -> None:
        """Add an ImageFile to this Image."""
        self.files.append(image_file)
        self.updated_at = datetime.now()

    def refine_file_roles(self) -> None:
        """
        Refine file roles based on the complete set of files in this Image.

        This method applies context-aware rules that require knowledge of all files:
        - If there's a RAW file, JPEGs are typically EXPORTs (unless marked as COVER)
        - If there's NO RAW file, a standalone JPEG becomes the ORIGINAL
        - Ensures only one file is marked as ORIGINAL

        Called after all files have been added to the Image.
        """
        # Rule 1: If there's a RAW file, it should be the ORIGINAL
        if self.has_raw:
            # Any JPEG that was initially marked as ORIGINAL should be reclassified
            for f in self.files:
                if f.format == FileFormat.JPEG and f.role == FileRole.ORIGINAL:
                    if FileRole.COVER not in [file.role for file in self.files]:
                        # If no file is marked as COVER, this could be a cover
                        f.role = FileRole.COVER if ".COVER." in f.suffix.upper() else FileRole.EXPORT
                    else:
                        f.role = FileRole.EXPORT

        else:
            # Find standalone JPEG files that might have been marked as EXPORT
            jpeg_files = [f for f in self.files if f.format == FileFormat.JPEG]

            # If there's exactly one JPEG and it's not ORIGINAL, promote it
            if len(jpeg_files) == 1 and jpeg_files[0].role != FileRole.ORIGINAL and jpeg_files[0].role not in (FileRole.COVER, FileRole.DERIVATIVE):
                jpeg_files[0].role = FileRole.ORIGINAL

        self.updated_at = datetime.now()

    def populate_from_exif(self, extract_from_file: Optional[Path] = None) -> bool:
        """
        Populate Image metadata from EXIF data.

        Extracts EXIF metadata from the original file (or specified file)
        and populates the Image fields: captured_at, camera_make, camera_model,
        lens, GPS coordinates, title, description, and rating.

        Args:
            extract_from_file: Optional specific file to extract from.
                             If None, uses the original_file property.

        Returns:
            True if EXIF data was successfully extracted and populated,
            False otherwise

        Example:
            >>> image = Image(base_name="IMG_1234", subdirectory="2025/01/01")
            >>> image.add_file(ImageFile.from_path(Path("/photos/IMG_1234.CR2"), "IMG_1234"))
            >>> if image.populate_from_exif():
            ...     print(f"Captured at: {image.captured_at}")
        """
        # Determine which file to extract from
        target_file = extract_from_file
        if target_file is None:
            original = self.original_file
            if original is None:
                return False
            target_file = original.file_path

        # Import here to avoid circular dependency
        from home_media.scanner.exif import extract_exif_metadata

        # Extract EXIF data
        exif_data = extract_exif_metadata(target_file)
        
        if exif_data:
            # Populate Image fields from EXIF
            self.captured_at = exif_data.captured_at
            self.camera_make = exif_data.camera_make
            self.camera_model = exif_data.camera_model
            self.lens = exif_data.lens
            self.gps_latitude = exif_data.gps_latitude
            self.gps_longitude = exif_data.gps_longitude
            self.title = exif_data.title
            self.description = exif_data.description
            self.rating = exif_data.rating
        
        # Fallback: If captured_at is still None (no EXIF or no date in EXIF),
        # use the earliest file creation date.
        if self.captured_at is None:
            self.captured_at = self.earliest_file_date

        self.updated_at = datetime.now()
        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for pandas DataFrame (without nested files)."""
        return {
            "base_name": self.base_name,
            "subdirectory": self.subdirectory,
            "file_count": self.file_count,
            "suffixes": self.suffixes,
            "total_size_bytes": self.total_size_bytes,
            "earliest_file_date": self.earliest_file_date,
            "latest_file_date": self.latest_file_date,
            "has_raw": self.has_raw,
            "has_jpeg": self.has_jpeg,
            "has_sidecar": self.has_sidecar,
            "captured_at": self.captured_at,
            "camera_make": self.camera_make,
            "camera_model": self.camera_model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def get_canonical_name(self, captured_at: Optional[datetime] = None) -> str:
        """
        Generate the canonical name for this Image based on capture time.

        Format: YYYY-mm-dd_HH-MM-SS

        Args:
            captured_at: Override capture time (uses self.captured_at if None)

        Returns:
            Canonical name string, or current base_name if no capture time available
        """
        dt = captured_at or self.captured_at
        return self.base_name if dt is None else dt.strftime("%Y-%m-%d_%H-%M-%S")

    def get_canonical_subdirectory(self, captured_at: Optional[datetime] = None) -> str:
        """
        Generate the canonical subdirectory for this Image based on capture time.

        Format: YYYY/mm/dd

        Args:
            captured_at: Override capture time (uses self.captured_at if None)

        Returns:
            Canonical subdirectory string, or current subdirectory if no capture time
        """
        dt = captured_at or self.captured_at
        return self.subdirectory if dt is None else dt.strftime("%Y/%m/%d")
