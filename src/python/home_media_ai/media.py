from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, BigInteger, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import JSON

Base = declarative_base()


class MediaType(Base):
    """Represents a type or category of media within the system.

    This class models the classification of media items, such as image, video, or audio.

    Attributes:
        id: Unique identifier for the media type.
        name: Name of the media type.
        media: Relationship to Media instances associated with this type.
    """
    __tablename__ = 'media_types'

    id   = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)

    media = relationship("Media", back_populates="media_type")


class Media(Base):
    """Represents a media file stored in the system, including its metadata and relationships.

    This class models individual media items, their types, and derivative relationships.

    Attributes:
        id: Unique identifier for the media.
        storage_root: Mount point where file was found (e.g., /volume1/photos).
        directory: Path from storage_root to file (e.g., 2024/January).
        filename: Just the filename portion (e.g., IMG_001.CR2).
        file_path: DEPRECATED - Legacy column, will be removed after migration.
        file_hash: SHA-256 hash of the file.
        file_size: Size of the file in bytes.
        file_ext: File extension.
        media_type_id: Foreign key to the media type.
        created: Datetime when the media was created.
        is_original: Indicates if the media is an original file.
        origin_id: Foreign key to the original media if this is a derivative.
        exif_data: Additional metadata stored as JSON.
        gps_latitude: GPS latitude in decimal degrees.
        gps_longitude: GPS longitude in decimal degrees.
        gps_altitude: GPS altitude in meters.
        camera_make: Camera manufacturer.
        camera_model: Camera model.
        lens_model: Lens model if available.
        width: Image width in pixels.
        height: Image height in pixels.
        rating: Quality rating 0-5 stars.
        media_type: Relationship to the MediaType class.
        derivatives: Relationship to derivative Media instances.
    """
    __tablename__ = 'media'

    id            = Column(Integer, primary_key=True)
    # New path component columns
    storage_root  = Column(String(500), nullable=True)
    directory     = Column(String(500), nullable=True)
    filename      = Column(String(255), nullable=False)
    # Deprecated column - will be removed after migration
    file_path     = Column(String(500), nullable=True)
    file_hash     = Column(String(64), nullable=False, unique=True)
    file_size     = Column(BigInteger, nullable=False)
    file_ext      = Column(String(10), nullable=False)
    media_type_id = Column(Integer, ForeignKey('media_types.id'), nullable=False)
    created       = Column(DateTime, nullable=False)
    is_original   = Column(Boolean, nullable=False, default=True)
    origin_id     = Column(Integer, ForeignKey('media.id'), nullable=True)
    exif_data     = Column(JSON, nullable=True)

    # EXIF metadata columns
    gps_latitude  = Column(Numeric(10, 8), nullable=True)
    gps_longitude = Column(Numeric(11, 8), nullable=True)
    gps_altitude  = Column(Numeric(8, 2), nullable=True)
    camera_make   = Column(String(100), nullable=True)
    camera_model  = Column(String(100), nullable=True)
    lens_model    = Column(String(100), nullable=True)
    width         = Column(Integer, nullable=True)
    height        = Column(Integer, nullable=True)
    rating        = Column(Integer, nullable=True)

    media_type  = relationship("MediaType", back_populates="media")
    derivatives = relationship("Media", backref="original", remote_side=[id])

    def get_full_path(self, use_local_mapping: bool = True):
        """Construct full file path from components.

        Args:
            use_local_mapping: If True, uses configuration to map storage_root to local paths.
                              If False, uses database paths directly.

        Returns:
            str: Full path to the file, resolved to local filesystem if mapping exists.
        """
        if use_local_mapping:
            # Use path resolver for cross-platform compatibility
            try:
                from .config import get_path_resolver
                resolver = get_path_resolver()
                path = resolver.resolve_path(self.storage_root, self.directory, self.filename)
                return str(path)
            except ImportError:
                # Config module not available, fall back to simple path construction
                pass

        # Fallback: construct path from database values directly
        from pathlib import Path
        if self.storage_root and self.directory:
            return str(Path(self.storage_root) / self.directory / self.filename)
        elif self.storage_root:
            return str(Path(self.storage_root) / self.filename)
        elif self.directory:
            return str(Path(self.directory) / self.filename)
        else:
            return self.filename
