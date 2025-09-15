"""
Database management for Home Media AI.

This module provides database operations for storing and retrieving
media metadata, quality metrics, and content analysis results.

Classes:
    MediaDatabase: Main database interface
    MediaFile: Database model for media files
    QualityMetrics: Database model for quality metrics
    ContentAnalysis: Database model for content analysis results
    
Example:
    >>> from home_media_ai.core import MediaDatabase
    >>> db = MediaDatabase('my_media.db')
    >>> db.create_tables()
    >>> db.add_media_file('/path/to/image.jpg', quality_metrics, content_results)
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime
from dataclasses import asdict

from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from ..config import get_config
from ..quality.metrics import ImageQualityMetrics, VideoQualityMetrics
from ..content.detection import DetectionResult
from ..utils import get_file_info

logger = logging.getLogger(__name__)

Base = declarative_base()


class MediaFile(Base):
    """Database model for media files.
    
    This table stores basic information about each media file including
    file system metadata and references to quality and content analysis.
    
    Attributes:
        id: Primary key
        file_path: Absolute path to the media file
        filename: Base filename
        file_extension: File extension (e.g., '.jpg', '.mp4')
        file_size_bytes: File size in bytes
        file_hash: MD5 hash for duplicate detection
        mime_type: MIME type of the file
        is_image: Whether file is an image
        is_video: Whether file is a video
        created_date: File creation date
        modified_date: File modification date
        added_date: Date when file was added to database
        last_analyzed: Date when file was last analyzed
        analysis_version: Version of analysis algorithms used
    """
    __tablename__ = 'media_files'
    
    id = Column(Integer, primary_key=True)
    file_path = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False, index=True)
    file_extension = Column(String, nullable=False, index=True)
    file_size_bytes = Column(Integer)
    file_hash = Column(String, index=True)
    mime_type = Column(String)
    is_image = Column(Boolean, default=False, index=True)
    is_video = Column(Boolean, default=False, index=True)
    created_date = Column(DateTime)
    modified_date = Column(DateTime)
    added_date = Column(DateTime, default=datetime.utcnow)
    last_analyzed = Column(DateTime)
    analysis_version = Column(String)


class QualityMetrics(Base):
    """Database model for quality assessment metrics.
    
    This table stores quality assessment results for both images and videos.
    
    Attributes:
        id: Primary key
        media_file_id: Foreign key to media_files table
        overall_score: Overall quality score (0-100)
        blur_score: Blur quality score
        brightness_score: Brightness quality score
        contrast_score: Contrast quality score
        noise_score: Noise quality score
        sharpness_score: Sharpness quality score
        saturation_score: Saturation quality score
        exposure_score: Exposure quality score
        face_quality_score: Face quality score (if applicable)
        # Video-specific metrics
        avg_frame_quality: Average frame quality for videos
        motion_blur_score: Motion blur score for videos
        stability_score: Video stability score
        compression_score: Compression quality score
        frame_consistency_score: Frame consistency score
        duration_seconds: Video duration
        frame_rate: Video frame rate
        resolution_width: Video/image width
        resolution_height: Video/image height
        raw_metrics: JSON field for storing complete metrics object
    """
    __tablename__ = 'quality_metrics'
    
    id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, nullable=False, index=True)
    overall_score = Column(Float, index=True)
    
    # Image quality metrics
    blur_score = Column(Float)
    brightness_score = Column(Float)
    contrast_score = Column(Float)
    noise_score = Column(Float)
    sharpness_score = Column(Float)
    saturation_score = Column(Float)
    exposure_score = Column(Float)
    face_quality_score = Column(Float)
    
    # Video quality metrics
    avg_frame_quality = Column(Float)
    motion_blur_score = Column(Float)
    stability_score = Column(Float)
    compression_score = Column(Float)
    frame_consistency_score = Column(Float)
    duration_seconds = Column(Float)
    frame_rate = Column(Float)
    
    # Common metrics
    resolution_width = Column(Integer)
    resolution_height = Column(Integer)
    
    # Store complete metrics as JSON
    raw_metrics = Column(JSON)


class ContentAnalysis(Base):
    """Database model for content analysis results.
    
    This table stores content identification results including faces,
    objects, scenes, and other detected content.
    
    Attributes:
        id: Primary key
        media_file_id: Foreign key to media_files table
        face_count: Number of detected faces
        object_count: Number of detected objects
        has_text: Whether text was detected
        scene_labels: JSON array of scene classification results
        object_classes: JSON array of detected object classes
        dominant_colors: JSON array of dominant colors
        tags: JSON array of generated tags
        processing_time: Time taken for analysis
        raw_results: JSON field for storing complete detection results
    """
    __tablename__ = 'content_analysis'
    
    id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, nullable=False, index=True)
    face_count = Column(Integer, default=0, index=True)
    object_count = Column(Integer, default=0, index=True)
    has_text = Column(Boolean, default=False, index=True)
    scene_labels = Column(JSON)
    object_classes = Column(JSON)
    dominant_colors = Column(JSON)
    tags = Column(JSON)
    processing_time = Column(Float)
    
    # Store complete detection results as JSON
    raw_results = Column(JSON)


class MediaDatabase:
    """Main database interface for Home Media AI.
    
    This class provides a high-level interface for storing and retrieving
    media metadata, quality metrics, and content analysis results.
    
    Attributes:
        engine: SQLAlchemy database engine
        session_maker: SQLAlchemy session maker
        config: Configuration object
        
    Example:
        >>> db = MediaDatabase('my_media.db')
        >>> db.create_tables()
        >>> 
        >>> # Add a media file with analysis results
        >>> file_id = db.add_media_file('/path/to/image.jpg')
        >>> db.add_quality_metrics(file_id, quality_metrics)
        >>> db.add_content_analysis(file_id, content_results)
        >>> 
        >>> # Search for files
        >>> high_quality_files = db.search_by_quality(min_score=80)
        >>> files_with_faces = db.search_by_content(has_faces=True)
    """
    
    def __init__(self, database_path: Optional[str] = None, config=None):
        """Initialize the database connection.
        
        Args:
            database_path: Path to SQLite database file (uses config default if None)
            config: Configuration object (uses global config if None)
        """
        self.config = config or get_config()
        
        if database_path is None:
            database_path = self.config.database.path
        
        # Create database directory if needed
        db_path = Path(database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create database engine
        database_url = f"sqlite:///{db_path}"
        self.engine = create_engine(
            database_url,
            echo=self.config.database.echo,
            pool_size=self.config.database.pool_size,
            connect_args={'timeout': self.config.database.timeout}
        )
        
        # Create session maker
        self.session_maker = sessionmaker(bind=self.engine)
        
        logger.info(f"Database initialized: {database_path}")
    
    def create_tables(self) -> None:
        """Create all database tables.
        
        This method is safe to call multiple times as it only creates
        tables that don't already exist.
        
        Example:
            >>> db = MediaDatabase()
            >>> db.create_tables()
        """
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def add_media_file(
        self, 
        file_path: Union[str, Path],
        analysis_version: str = "1.0"
    ) -> int:
        """Add a media file to the database.
        
        Args:
            file_path: Path to the media file
            analysis_version: Version identifier for analysis algorithms
            
        Returns:
            Database ID of the added file
            
        Raises:
            FileNotFoundError: If file doesn't exist
            SQLAlchemyError: If database operation fails
            
        Example:
            >>> db = MediaDatabase()
            >>> file_id = db.add_media_file('/path/to/image.jpg')
        """
        file_path = Path(file_path).absolute()
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Get file information
        file_info = get_file_info(file_path)
        
        with self.session_maker() as session:
            try:
                # Check if file already exists
                existing_file = session.query(MediaFile).filter_by(
                    file_path=str(file_path)
                ).first()
                
                if existing_file:
                    logger.debug(f"File already in database: {file_path}")
                    return existing_file.id
                
                # Create new media file record
                media_file = MediaFile(
                    file_path=str(file_path),
                    filename=file_info['filename'],
                    file_extension=file_info['extension'],
                    file_size_bytes=file_info['size_bytes'],
                    file_hash=file_info['md5_hash'],
                    mime_type=file_info['mime_type'],
                    is_image=file_info['is_image'],
                    is_video=file_info['is_video'],
                    created_date=file_info['created'],
                    modified_date=file_info['modified'],
                    analysis_version=analysis_version
                )
                
                session.add(media_file)
                session.commit()
                
                logger.debug(f"Added media file to database: {file_path}")
                return media_file.id
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error adding media file to database: {e}")
                raise
    
    def add_quality_metrics(
        self, 
        media_file_id: int, 
        metrics: Union[ImageQualityMetrics, VideoQualityMetrics]
    ) -> None:
        """Add quality metrics for a media file.
        
        Args:
            media_file_id: Database ID of the media file
            metrics: Quality metrics object
            
        Raises:
            SQLAlchemyError: If database operation fails
            
        Example:
            >>> db = MediaDatabase()
            >>> file_id = db.add_media_file('/path/to/image.jpg')
            >>> metrics = evaluator.evaluate_image('/path/to/image.jpg')
            >>> db.add_quality_metrics(file_id, metrics)
        """
        with self.session_maker() as session:
            try:
                # Remove existing metrics if any
                session.query(QualityMetrics).filter_by(
                    media_file_id=media_file_id
                ).delete()
                
                # Create quality metrics record
                quality_record = QualityMetrics(
                    media_file_id=media_file_id,
                    overall_score=metrics.overall_score,
                    raw_metrics=metrics.to_dict()
                )
                
                # Set common fields
                if hasattr(metrics, 'blur_score'):
                    quality_record.blur_score = metrics.blur_score
                if hasattr(metrics, 'brightness_score'):
                    quality_record.brightness_score = metrics.brightness_score
                if hasattr(metrics, 'contrast_score'):
                    quality_record.contrast_score = metrics.contrast_score
                if hasattr(metrics, 'noise_score'):
                    quality_record.noise_score = metrics.noise_score
                if hasattr(metrics, 'sharpness_score'):
                    quality_record.sharpness_score = metrics.sharpness_score
                if hasattr(metrics, 'saturation_score'):
                    quality_record.saturation_score = metrics.saturation_score
                if hasattr(metrics, 'exposure_score'):
                    quality_record.exposure_score = metrics.exposure_score
                if hasattr(metrics, 'face_quality_score'):
                    quality_record.face_quality_score = metrics.face_quality_score
                
                # Set video-specific fields
                if isinstance(metrics, VideoQualityMetrics):
                    quality_record.avg_frame_quality = metrics.avg_frame_quality
                    quality_record.motion_blur_score = metrics.motion_blur_score
                    quality_record.stability_score = metrics.stability_score
                    quality_record.compression_score = metrics.compression_score
                    quality_record.frame_consistency_score = metrics.frame_consistency_score
                    quality_record.duration_seconds = metrics.duration_seconds
                    quality_record.frame_rate = metrics.frame_rate
                    quality_record.resolution_width = metrics.resolution_width
                    quality_record.resolution_height = metrics.resolution_height
                
                session.add(quality_record)
                session.commit()
                
                logger.debug(f"Added quality metrics for media file ID: {media_file_id}")
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error adding quality metrics: {e}")
                raise
    
    def add_content_analysis(self, media_file_id: int, results: DetectionResult) -> None:
        """Add content analysis results for a media file.
        
        Args:
            media_file_id: Database ID of the media file
            results: Content detection results
            
        Raises:
            SQLAlchemyError: If database operation fails
            
        Example:
            >>> db = MediaDatabase()
            >>> file_id = db.add_media_file('/path/to/image.jpg')
            >>> results = identifier.analyze_image('/path/to/image.jpg')
            >>> db.add_content_analysis(file_id, results)
        """
        with self.session_maker() as session:
            try:
                # Remove existing analysis if any
                session.query(ContentAnalysis).filter_by(
                    media_file_id=media_file_id
                ).delete()
                
                # Create content analysis record
                content_record = ContentAnalysis(
                    media_file_id=media_file_id,
                    face_count=results.face_count,
                    object_count=results.object_count,
                    has_text=results.has_text,
                    scene_labels=results.scene_labels,
                    object_classes=results.get_object_classes(),
                    dominant_colors=results.dominant_colors,
                    tags=results.tags,
                    processing_time=results.processing_time,
                    raw_results=results.to_dict()
                )
                
                session.add(content_record)
                session.commit()
                
                logger.debug(f"Added content analysis for media file ID: {media_file_id}")
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error adding content analysis: {e}")
                raise
    
    def update_analysis_timestamp(self, media_file_id: int) -> None:
        """Update the last analyzed timestamp for a media file.
        
        Args:
            media_file_id: Database ID of the media file
            
        Example:
            >>> db = MediaDatabase()
            >>> db.update_analysis_timestamp(file_id)
        """
        with self.session_maker() as session:
            try:
                session.query(MediaFile).filter_by(id=media_file_id).update({
                    'last_analyzed': datetime.utcnow()
                })
                session.commit()
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error updating analysis timestamp: {e}")
                raise
    
    def search_by_quality(
        self, 
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for media files by quality score.
        
        Args:
            min_score: Minimum quality score (0-100)
            max_score: Maximum quality score (0-100)
            limit: Maximum number of results to return
            
        Returns:
            List of dictionaries containing file information and quality scores
            
        Example:
            >>> db = MediaDatabase()
            >>> high_quality = db.search_by_quality(min_score=80)
            >>> for file_info in high_quality:
            ...     print(f"{file_info['filename']}: {file_info['overall_score']}")
        """
        with self.session_maker() as session:
            try:
                query = session.query(MediaFile, QualityMetrics).join(
                    QualityMetrics, MediaFile.id == QualityMetrics.media_file_id
                )
                
                if min_score is not None:
                    query = query.filter(QualityMetrics.overall_score >= min_score)
                
                if max_score is not None:
                    query = query.filter(QualityMetrics.overall_score <= max_score)
                
                query = query.order_by(QualityMetrics.overall_score.desc())
                
                if limit:
                    query = query.limit(limit)
                
                results = []
                for media_file, quality_metrics in query.all():
                    result = {
                        'id': media_file.id,
                        'file_path': media_file.file_path,
                        'filename': media_file.filename,
                        'file_size_bytes': media_file.file_size_bytes,
                        'is_image': media_file.is_image,
                        'is_video': media_file.is_video,
                        'overall_score': quality_metrics.overall_score,
                        'created_date': media_file.created_date,
                        'last_analyzed': media_file.last_analyzed,
                    }
                    results.append(result)
                
                return results
                
            except SQLAlchemyError as e:
                logger.error(f"Error searching by quality: {e}")
                return []
    
    def search_by_content(
        self,
        has_faces: Optional[bool] = None,
        min_face_count: Optional[int] = None,
        has_objects: Optional[bool] = None,
        object_classes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        has_text: Optional[bool] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for media files by content criteria.
        
        Args:
            has_faces: Whether file should contain faces
            min_face_count: Minimum number of faces
            has_objects: Whether file should contain objects
            object_classes: List of object classes to search for
            tags: List of tags to search for
            has_text: Whether file should contain text
            limit: Maximum number of results to return
            
        Returns:
            List of dictionaries containing file information and content data
            
        Example:
            >>> db = MediaDatabase()
            >>> family_photos = db.search_by_content(
            ...     has_faces=True, 
            ...     min_face_count=2,
            ...     tags=['outdoor']
            ... )
        """
        with self.session_maker() as session:
            try:
                query = session.query(MediaFile, ContentAnalysis).join(
                    ContentAnalysis, MediaFile.id == ContentAnalysis.media_file_id
                )
                
                if has_faces is not None:
                    if has_faces:
                        query = query.filter(ContentAnalysis.face_count > 0)
                    else:
                        query = query.filter(ContentAnalysis.face_count == 0)
                
                if min_face_count is not None:
                    query = query.filter(ContentAnalysis.face_count >= min_face_count)
                
                if has_objects is not None:
                    if has_objects:
                        query = query.filter(ContentAnalysis.object_count > 0)
                    else:
                        query = query.filter(ContentAnalysis.object_count == 0)
                
                if has_text is not None:
                    query = query.filter(ContentAnalysis.has_text == has_text)
                
                # TODO: Add JSON-based filtering for object_classes and tags
                # This would require database-specific JSON query syntax
                
                query = query.order_by(MediaFile.created_date.desc())
                
                if limit:
                    query = query.limit(limit)
                
                results = []
                for media_file, content_analysis in query.all():
                    # Filter by object classes and tags if specified
                    if object_classes:
                        file_object_classes = content_analysis.object_classes or []
                        if not any(cls in file_object_classes for cls in object_classes):
                            continue
                    
                    if tags:
                        file_tags = content_analysis.tags or []
                        if not any(tag in file_tags for tag in tags):
                            continue
                    
                    result = {
                        'id': media_file.id,
                        'file_path': media_file.file_path,
                        'filename': media_file.filename,
                        'file_size_bytes': media_file.file_size_bytes,
                        'is_image': media_file.is_image,
                        'is_video': media_file.is_video,
                        'face_count': content_analysis.face_count,
                        'object_count': content_analysis.object_count,
                        'has_text': content_analysis.has_text,
                        'object_classes': content_analysis.object_classes,
                        'tags': content_analysis.tags,
                        'scene_labels': content_analysis.scene_labels,
                        'created_date': media_file.created_date,
                        'last_analyzed': media_file.last_analyzed,
                    }
                    results.append(result)
                
                return results
                
            except SQLAlchemyError as e:
                logger.error(f"Error searching by content: {e}")
                return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics and summary information.
        
        Returns:
            Dictionary containing database statistics
            
        Example:
            >>> db = MediaDatabase()
            >>> stats = db.get_statistics()
            >>> print(f"Total files: {stats['total_files']}")
            >>> print(f"Average quality: {stats['avg_quality_score']:.1f}")
        """
        with self.session_maker() as session:
            try:
                # Basic file counts
                total_files = session.query(MediaFile).count()
                total_images = session.query(MediaFile).filter_by(is_image=True).count()
                total_videos = session.query(MediaFile).filter_by(is_video=True).count()
                
                # Quality statistics
                quality_stats = session.query(
                    QualityMetrics.overall_score
                ).filter(QualityMetrics.overall_score.isnot(None)).all()
                
                if quality_stats:
                    scores = [score[0] for score in quality_stats]
                    avg_quality = sum(scores) / len(scores)
                    min_quality = min(scores)
                    max_quality = max(scores)
                else:
                    avg_quality = min_quality = max_quality = 0.0
                
                # Content statistics
                total_faces = session.query(
                    ContentAnalysis.face_count
                ).filter(ContentAnalysis.face_count > 0).count()
                
                files_with_text = session.query(ContentAnalysis).filter_by(has_text=True).count()
                
                # Storage statistics
                total_size = session.query(MediaFile.file_size_bytes).all()
                total_size_bytes = sum(size[0] or 0 for size in total_size)
                
                return {
                    'total_files': total_files,
                    'total_images': total_images,
                    'total_videos': total_videos,
                    'total_size_bytes': total_size_bytes,
                    'total_size_gb': total_size_bytes / (1024**3),
                    'avg_quality_score': avg_quality,
                    'min_quality_score': min_quality,
                    'max_quality_score': max_quality,
                    'files_with_faces': total_faces,
                    'files_with_text': files_with_text,
                }
                
            except SQLAlchemyError as e:
                logger.error(f"Error getting database statistics: {e}")
                return {}
    
    def find_duplicates(self) -> List[List[Dict[str, Any]]]:
        """Find potential duplicate files based on hash.
        
        Returns:
            List of groups, where each group contains files with the same hash
            
        Example:
            >>> db = MediaDatabase()
            >>> duplicates = db.find_duplicates()
            >>> for group in duplicates:
            ...     print(f"Duplicate group with {len(group)} files:")
            ...     for file_info in group:
            ...         print(f"  {file_info['file_path']}")
        """
        with self.session_maker() as session:
            try:
                # Find files with the same hash
                duplicate_hashes = session.query(MediaFile.file_hash).group_by(
                    MediaFile.file_hash
                ).having(
                    session.query(MediaFile.id).filter(
                        MediaFile.file_hash == MediaFile.file_hash
                    ).count() > 1
                ).all()
                
                duplicate_groups = []
                for (file_hash,) in duplicate_hashes:
                    if file_hash:  # Skip null hashes
                        files = session.query(MediaFile).filter_by(file_hash=file_hash).all()
                        group = []
                        for file in files:
                            group.append({
                                'id': file.id,
                                'file_path': file.file_path,
                                'filename': file.filename,
                                'file_size_bytes': file.file_size_bytes,
                                'created_date': file.created_date,
                            })
                        duplicate_groups.append(group)
                
                return duplicate_groups
                
            except SQLAlchemyError as e:
                logger.error(f"Error finding duplicates: {e}")
                return []
    
    def backup_database(self, backup_path: Union[str, Path]) -> None:
        """Create a backup of the database.
        
        Args:
            backup_path: Path where backup should be saved
            
        Example:
            >>> db = MediaDatabase()
            >>> db.backup_database('/backup/media_db_backup.db')
        """
        import shutil
        
        try:
            # For SQLite, we can simply copy the database file
            if self.engine.url.drivername == 'sqlite':
                db_file = self.engine.url.database
                shutil.copy2(db_file, backup_path)
                logger.info(f"Database backed up to: {backup_path}")
            else:
                logger.warning("Backup not implemented for non-SQLite databases")
                
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            raise
    
    def close(self) -> None:
        """Close database connections.
        
        Example:
            >>> db = MediaDatabase()
            >>> # ... use database ...
            >>> db.close()
        """
        try:
            self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")