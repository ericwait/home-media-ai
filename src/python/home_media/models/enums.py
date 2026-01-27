"""Enumerations for HomeMedia models."""

from enum import Enum, auto


class FileRole(Enum):
    """
    The role a file plays in representing an Image.

    An Image (a moment in time) may have multiple files with different roles:
    - ORIGINAL: The primary capture (RAW, DNG)
    - COVER: Preview/thumbnail JPEG (e.g., Pixel's COVER files)
    - SIDECAR: Metadata files (XMP, THM)
    - EXPORT: Processed outputs (JPEGs exported from editing software)
    - DERIVATIVE: Crops, edits, versions (e.g., _001, _edit)
    - UNKNOWN: Role not yet determined
    """
    ORIGINAL = auto()
    COVER = auto()
    SIDECAR = auto()
    EXPORT = auto()
    DERIVATIVE = auto()
    UNKNOWN = auto()


class FileFormat(Enum):
    """
    Known file formats for image files.

    Grouped by type:
    - RAW formats: Camera-specific raw files
    - Standard formats: Common image formats
    - Metadata formats: Sidecar and metadata files
    - Video formats: For future video support
    """
    # RAW formats
    CR2 = "cr2"      # Canon RAW 2
    CR3 = "cr3"      # Canon RAW 3
    NEF = "nef"      # Nikon RAW
    ARW = "arw"      # Sony RAW
    DNG = "dng"      # Adobe Digital Negative
    RAF = "raf"      # Fujifilm RAW
    ORF = "orf"      # Olympus RAW
    RW2 = "rw2"      # Panasonic RAW

    # Standard image formats
    JPEG = "jpg"
    PNG = "png"
    TIFF = "tiff"
    HEIC = "heic"
    HEIF = "heif"
    WEBP = "webp"

    # Metadata/sidecar formats
    XMP = "xmp"
    THM = "thm"      # Thumbnail file (Ignored for now)

    # Video formats (for future use)
    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"

    # Unknown
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, extension: str) -> "FileFormat":
        """
        Get FileFormat from a file extension.

        Args:
            extension: File extension (with or without leading dot)

        Returns:
            The matching FileFormat, or UNKNOWN if not recognized
        """
        ext = extension.lower().lstrip(".")

        # Handle common variations
        if ext in {"jpg", "jpeg"}:
            return cls.JPEG
        if ext in {"tif", "tiff"}:
            return cls.TIFF

        # Try direct match
        for fmt in cls:
            if fmt.value == ext:
                return fmt

        return cls.UNKNOWN

    @classmethod
    def from_filename(cls, filename: str) -> "FileFormat":
        """
        Get FileFormat from a filename or file path.

        Convenience method that extracts the extension and returns the format.

        Args:
            filename: Filename or full path (e.g., "photo.jpg" or "/path/to/photo.CR2")

        Returns:
            The matching FileFormat, or UNKNOWN if not recognized

        Examples:
            >>> FileFormat.from_filename("photo.jpg")
            FileFormat.JPEG
            >>> FileFormat.from_filename("/photos/2025/01/IMG_1234.CR2")
            FileFormat.CR2
            >>> FileFormat.from_filename("sidecar.xmp")
            FileFormat.XMP
        """
        from pathlib import Path
        ext = Path(filename).suffix
        return cls.from_extension(ext)

    @property
    def is_raw(self) -> bool:
        """Check if this format is a RAW format."""
        return self in (
            FileFormat.CR2, FileFormat.CR3, FileFormat.NEF,
            FileFormat.ARW, FileFormat.DNG, FileFormat.RAF,
            FileFormat.ORF, FileFormat.RW2, FileFormat.TIFF
        )

    @property
    def is_image(self) -> bool:
        """Check if this format is a viewable image format."""
        return self in (
            FileFormat.JPEG, FileFormat.PNG,
            FileFormat.HEIC, FileFormat.HEIF, FileFormat.WEBP
        ) or self.is_raw

    @property
    def is_sidecar(self) -> bool:
        """Check if this format is a sidecar/metadata format."""
        # Include THM as sidecar even if video support is pending
        return self in (FileFormat.XMP, FileFormat.THM)

    @property
    def is_video(self) -> bool:
        """Check if this format is a video format."""
        return self in (FileFormat.MP4, FileFormat.MOV, FileFormat.AVI)
