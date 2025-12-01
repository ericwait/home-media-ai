import contextlib
import hashlib
import secrets
from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Boolean, ForeignKey, BigInteger, Numeric
from sqlalchemy.orm import relationship, Mapped, mapped_column, declarative_base
from sqlalchemy.dialects.mysql import JSON

Base = declarative_base()


class User(Base):
    """Represents a user who can rate photos.

    Attributes:
        id: Unique identifier for the user.
        username: Unique username for login.
        password_hash: Hashed password.
        salt: Unique salt for this user's password.
        display_name: Friendly name to display.
        is_active: Whether the user can log in.
        created_at: When the user was created.
        last_login: When the user last logged in.
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    salt: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    def set_password(self, password: str) -> None:
        """Set a new password for this user."""
        self.salt = secrets.token_hex(16)
        self.password_hash = hashlib.sha256(f"{self.salt}{password}".encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches."""
        test_hash = hashlib.sha256(f"{self.salt}{password}".encode()).hexdigest()
        return test_hash == self.password_hash

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Validate password meets minimum security requirements."""
        import re
        if len(password) < 12:
            return False, "Password must be at least 12 characters"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        return True, ""


class MediaType(Base):
    """Represents a type or category of media within the system.

    This class models the classification of media items, such as image, video, or audio.

    Attributes:
        id: Unique identifier for the media type.
        name: Name of the media type.
        media: Relationship to Media instances associated with this type.
    """
    __tablename__ = 'media_types'

    id  : Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    media: Mapped[list["Media"]] = relationship("Media", back_populates="media_type")


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
        thumbnail_path: Path to cached thumbnail image (relative to storage_root).
        media_type: Relationship to the MediaType class.
        derivatives: Relationship to derivative Media instances.
    """
    __tablename__ = 'media'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # New path component columns
    storage_root: Mapped[str] = mapped_column(String(500), nullable=True)
    directory   : Mapped[str] = mapped_column(String(500), nullable=True)
    filename    : Mapped[str] = mapped_column(String(255), nullable=False)
    # Deprecated column - will be removed after migration
    # file_path     = Column(String(500), nullable=True)
    file_hash    : Mapped[str]      = mapped_column(String(64), nullable=False, unique=True)
    file_size    : Mapped[int]      = mapped_column(BigInteger, nullable=False)
    file_ext     : Mapped[str]      = mapped_column(String(10), nullable=False)
    media_type_id: Mapped[int]      = mapped_column(Integer, ForeignKey('media_types.id'), nullable=False)
    created      : Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_original  : Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)
    origin_id    : Mapped[int]      = mapped_column(Integer, ForeignKey('media.id'), nullable=True)
    exif_data    : Mapped[dict]     = mapped_column(JSON, nullable=True)

    # EXIF metadata columns
    gps_latitude : Mapped[float] = mapped_column(Numeric(10, 8), nullable=True)
    gps_longitude: Mapped[float] = mapped_column(Numeric(11, 8), nullable=True)
    gps_altitude : Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    camera_make  : Mapped[str]   = mapped_column(String(100), nullable=True)
    camera_model : Mapped[str]   = mapped_column(String(100), nullable=True)
    lens_model   : Mapped[str]   = mapped_column(String(100), nullable=True)
    width        : Mapped[int]   = mapped_column(Integer, nullable=True)
    height       : Mapped[int]   = mapped_column(Integer, nullable=True)
    rating       : Mapped[int]   = mapped_column(Integer, nullable=True)
    thumbnail_path: Mapped[str]  = mapped_column(String(500), nullable=True)

    media_type : Mapped["MediaType"]   = relationship("MediaType", back_populates="media")
    derivatives: Mapped[list["Media"]] = relationship("Media", backref="original", remote_side=[id])

    def get_full_path(self, use_local_mapping: bool = True) -> str:
        """Construct full file path from components.

        Args:
            use_local_mapping: If True, uses configuration to map storage_root to local paths.
                              If False, uses database paths directly.

        Returns:
            str: Full path to the file, resolved to local filesystem if mapping exists.
        """
        if use_local_mapping:
            # Use path resolver for cross-platform compatibility
            with contextlib.suppress(ImportError, ValueError, FileNotFoundError):
                from .config import get_path_resolver
                resolver = get_path_resolver()
                path = resolver.resolve_path(self.storage_root, self.directory, self.filename)
                return str(path)
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

    def read_as_array(self, use_local_mapping: bool = True):
        """Read the media file and return it as a NumPy array.

        This is a convenience method that combines get_full_path() with read_image_as_array().

        Args:
            use_local_mapping: If True, uses configuration to map storage_root to local paths.

        Returns:
            numpy.ndarray: Image data with native data type preserved.

        Example:
            >>> media = session.query(Media).first()
            >>> img_array = media.read_as_array()
            >>> print(img_array.shape, img_array.dtype)
        """
        from .io import read_image_as_array
        file_path = self.get_full_path(use_local_mapping=use_local_mapping)
        return read_image_as_array(file_path, media_type=self.media_type.name)
