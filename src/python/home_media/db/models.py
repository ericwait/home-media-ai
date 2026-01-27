"""
SQLAlchemy models for the Home Media database.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

# Import Enums from the core library
from home_media.models.enums import FileFormat, FileRole

class Base(DeclarativeBase):
    pass

class ImageModel(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Core Identity
    base_name: Mapped[str] = mapped_column(String, index=True)
    subdirectory: Mapped[str] = mapped_column(String)
    
    # Metadata
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
    
    # Camera/Lens Info
    camera_make: Mapped[Optional[str]] = mapped_column(String)
    camera_model: Mapped[Optional[str]] = mapped_column(String)
    lens: Mapped[Optional[str]] = mapped_column(String)
    
    # Location
    gps_latitude: Mapped[Optional[float]] = mapped_column(Float)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float)
    
    # User Metadata
    title: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    rating: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    files: Mapped[List["ImageFileModel"]] = relationship(back_populates="image", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('base_name', 'subdirectory', name='uq_image_identity'),
    )

class ImageFileModel(Base):
    __tablename__ = "image_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), index=True)
    
    # File details
    file_path: Mapped[str] = mapped_column(String, unique=True)
    filename: Mapped[str] = mapped_column(String)
    extension: Mapped[str] = mapped_column(String)
    
    # Enums stored as strings (or native Enum types if preferred, string is safer for now)
    role: Mapped[FileRole] = mapped_column(Enum(FileRole))
    format: Mapped[FileFormat] = mapped_column(Enum(FileFormat))
    
    # Stats
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    file_hash: Mapped[Optional[str]] = mapped_column(String, index=True)
    
    # Relationships
    image: Mapped["ImageModel"] = relationship(back_populates="files")
