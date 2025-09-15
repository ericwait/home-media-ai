"""
Main media analysis engine for Home Media AI.

This module provides the MediaAnalyzer class which serves as the main
entry point for analyzing media files. It coordinates quality evaluation,
content identification, and database storage.

Classes:
    MediaAnalyzer: Main media analysis orchestrator
    AnalysisResult: Container for complete analysis results
    
Example:
    >>> from home_media_ai import MediaAnalyzer
    >>> analyzer = MediaAnalyzer('/path/to/media/collection')
    >>> analyzer.create_database()
    >>> results = analyzer.analyze_directory()
    >>> print(f"Analyzed {len(results)} files")
"""

import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from ..config import get_config
from ..utils import find_media_files, setup_logging, format_file_size
from ..quality import QualityEvaluator
from ..content import ContentIdentifier
from .database import MediaDatabase

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Container for complete media analysis results.
    
    Attributes:
        file_path: Path to the analyzed file
        file_id: Database ID of the file
        quality_metrics: Quality assessment results
        content_results: Content identification results
        processing_time: Time taken for analysis in seconds
        success: Whether analysis completed successfully
        error_message: Error message if analysis failed
        
    Example:
        >>> result = AnalysisResult(
        ...     file_path='/path/to/image.jpg',
        ...     file_id=123,
        ...     quality_metrics=quality_metrics,
        ...     content_results=content_results,
        ...     processing_time=2.5,
        ...     success=True
        ... )
    """
    file_path: str
    file_id: Optional[int] = None
    quality_metrics: Optional[Any] = None
    content_results: Optional[Any] = None
    processing_time: float = 0.0
    success: bool = False
    error_message: Optional[str] = None


class MediaAnalyzer:
    """Main media analysis engine for Home Media AI.
    
    This class orchestrates the complete analysis pipeline including
    quality evaluation, content identification, and database storage.
    It can analyze individual files or entire directory trees.
    
    Attributes:
        media_directory: Root directory containing media files
        database: Database interface for storing results
        quality_evaluator: Quality assessment engine
        content_identifier: Content identification engine
        config: Configuration settings
        
    Example:
        >>> analyzer = MediaAnalyzer('/path/to/photos')
        >>> analyzer.create_database()
        >>> 
        >>> # Analyze a single file
        >>> result = analyzer.analyze_file('/path/to/photo.jpg')
        >>> print(f"Quality: {result.quality_metrics.overall_score}")
        >>> 
        >>> # Analyze entire directory
        >>> results = analyzer.analyze_directory(progress=True)
        >>> print(f"Processed {len(results)} files")
    """
    
    def __init__(
        self, 
        media_directory: Optional[Union[str, Path]] = None,
        database_path: Optional[str] = None,
        config=None
    ):
        """Initialize the media analyzer.
        
        Args:
            media_directory: Root directory containing media files
            database_path: Path to database file (uses config default if None)
            config: Configuration object (uses global config if None)
            
        Example:
            >>> analyzer = MediaAnalyzer('/home/user/photos', 'my_media.db')
        """
        self.config = config or get_config()
        
        # Set up logging
        setup_logging(
            level=self.config.processing.log_level,
            include_timestamp=True
        )
        
        # Initialize components
        self.media_directory = Path(media_directory) if media_directory else None
        self.database = MediaDatabase(database_path, self.config)
        self.quality_evaluator = QualityEvaluator(self.config)
        self.content_identifier = ContentIdentifier(self.config)
        
        logger.info(f"Media analyzer initialized")
        if self.media_directory:
            logger.info(f"Media directory: {self.media_directory}")
        logger.info(f"Database: {database_path or self.config.database.path}")
    
    def create_database(self) -> None:
        """Create database tables if they don't exist.
        
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> analyzer.create_database()
        """
        self.database.create_tables()
        logger.info("Database tables created/verified")
    
    def analyze_file(self, file_path: Union[str, Path]) -> AnalysisResult:
        """Analyze a single media file.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            AnalysisResult containing all analysis results
            
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> result = analyzer.analyze_file('/path/to/image.jpg')
            >>> if result.success:
            ...     print(f"Quality score: {result.quality_metrics.overall_score}")
            ...     print(f"Found {result.content_results.face_count} faces")
        """
        file_path = Path(file_path)
        start_time = time.time()
        
        logger.debug(f"Analyzing file: {file_path}")
        
        try:
            # Add file to database
            file_id = self.database.add_media_file(file_path)
            
            # Perform quality evaluation
            if file_path.suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpg', '.mpeg', '.m2v', '.mts', '.mxf'}:
                quality_metrics = self.quality_evaluator.evaluate_video(file_path)
            else:
                quality_metrics = self.quality_evaluator.evaluate_image(file_path)
            
            # Perform content identification
            if file_path.suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpg', '.mpeg', '.m2v', '.mts', '.mxf'}:
                content_results = self.content_identifier.analyze_video(file_path)
            else:
                content_results = self.content_identifier.analyze_image(file_path)
            
            # Store results in database
            self.database.add_quality_metrics(file_id, quality_metrics)
            self.database.add_content_analysis(file_id, content_results)
            self.database.update_analysis_timestamp(file_id)
            
            processing_time = time.time() - start_time
            
            result = AnalysisResult(
                file_path=str(file_path),
                file_id=file_id,
                quality_metrics=quality_metrics,
                content_results=content_results,
                processing_time=processing_time,
                success=True
            )
            
            logger.debug(f"Analysis complete: {file_path} ({processing_time:.2f}s)")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            result = AnalysisResult(
                file_path=str(file_path),
                processing_time=processing_time,
                success=False,
                error_message=error_msg
            )
            
            logger.error(f"Analysis failed for {file_path}: {error_msg}")
            return result
    
    def analyze_directory(
        self, 
        directory: Optional[Union[str, Path]] = None,
        recursive: bool = True,
        include_images: bool = True,
        include_videos: bool = True,
        progress: bool = True,
        max_workers: Optional[int] = None
    ) -> List[AnalysisResult]:
        """Analyze all media files in a directory.
        
        Args:
            directory: Directory to analyze (uses instance directory if None)
            recursive: Whether to search subdirectories
            include_images: Whether to include image files
            include_videos: Whether to include video files
            progress: Whether to show progress bar
            max_workers: Maximum number of worker threads (uses config default if None)
            
        Returns:
            List of AnalysisResult objects for all processed files
            
        Example:
            >>> analyzer = MediaAnalyzer('/path/to/photos')
            >>> results = analyzer.analyze_directory(progress=True)
            >>> 
            >>> # Get statistics
            >>> successful = [r for r in results if r.success]
            >>> failed = [r for r in results if not r.success]
            >>> print(f"Successful: {len(successful)}, Failed: {len(failed)}")
        """
        if directory is None:
            if self.media_directory is None:
                raise ValueError("No directory specified and no default directory set")
            directory = self.media_directory
        else:
            directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        logger.info(f"Starting directory analysis: {directory}")
        
        # Find all media files
        media_files = find_media_files(
            directory,
            recursive=recursive,
            include_images=include_images,
            include_videos=include_videos
        )
        
        if not media_files:
            logger.warning(f"No media files found in {directory}")
            return []
        
        logger.info(f"Found {len(media_files)} media files to analyze")
        
        # Calculate total size for progress tracking
        total_size = sum(f.stat().st_size for f in media_files if f.exists())
        logger.info(f"Total size to process: {format_file_size(total_size)}")
        
        # Set up parallel processing
        max_workers = max_workers or self.config.processing.max_workers
        
        results = []
        
        if max_workers == 1:
            # Single-threaded processing
            if progress:
                media_files = tqdm(
                    media_files, 
                    desc="Analyzing files",
                    unit="files",
                    disable=not self.config.processing.progress_bar
                )
            
            for file_path in media_files:
                result = self.analyze_file(file_path)
                results.append(result)
        else:
            # Multi-threaded processing
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_file = {
                    executor.submit(self.analyze_file, file_path): file_path
                    for file_path in media_files
                }
                
                # Collect results with progress bar
                if progress:
                    futures = tqdm(
                        as_completed(future_to_file),
                        total=len(media_files),
                        desc="Analyzing files",
                        unit="files",
                        disable=not self.config.processing.progress_bar
                    )
                else:
                    futures = as_completed(future_to_file)
                
                for future in futures:
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        file_path = future_to_file[future]
                        logger.error(f"Unexpected error processing {file_path}: {e}")
                        results.append(AnalysisResult(
                            file_path=str(file_path),
                            success=False,
                            error_message=str(e)
                        ))
        
        # Log summary statistics
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        total_time = sum(r.processing_time for r in results)
        
        logger.info(f"Directory analysis complete:")
        logger.info(f"  Total files: {len(results)}")
        logger.info(f"  Successful: {len(successful)}")
        logger.info(f"  Failed: {len(failed)}")
        logger.info(f"  Total processing time: {total_time:.2f} seconds")
        
        if successful:
            avg_time = total_time / len(successful)
            logger.info(f"  Average time per file: {avg_time:.2f} seconds")
        
        return results
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all analyzed files.
        
        Returns:
            Dictionary containing analysis summary statistics
            
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> summary = analyzer.get_analysis_summary()
            >>> print(f"Total files: {summary['total_files']}")
            >>> print(f"Average quality: {summary['avg_quality']:.1f}")
        """
        db_stats = self.database.get_statistics()
        
        # Add additional analysis-specific statistics
        summary = {
            'database_stats': db_stats,
            'total_files': db_stats.get('total_files', 0),
            'total_images': db_stats.get('total_images', 0),
            'total_videos': db_stats.get('total_videos', 0),
            'total_size_gb': db_stats.get('total_size_gb', 0),
            'avg_quality': db_stats.get('avg_quality_score', 0),
            'files_with_faces': db_stats.get('files_with_faces', 0),
            'files_with_text': db_stats.get('files_with_text', 0),
        }
        
        return summary
    
    def search_files(
        self,
        quality_min: Optional[float] = None,
        quality_max: Optional[float] = None,
        has_faces: Optional[bool] = None,
        min_face_count: Optional[int] = None,
        object_classes: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        has_text: Optional[bool] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for files based on analysis results.
        
        Args:
            quality_min: Minimum quality score
            quality_max: Maximum quality score
            has_faces: Whether file should contain faces
            min_face_count: Minimum number of faces
            object_classes: List of object classes to search for
            tags: List of tags to search for
            has_text: Whether file should contain text
            limit: Maximum number of results
            
        Returns:
            List of matching files with their analysis data
            
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> 
            >>> # Find high-quality family photos
            >>> family_photos = analyzer.search_files(
            ...     quality_min=80,
            ...     has_faces=True,
            ...     min_face_count=2
            ... )
            >>> 
            >>> # Find outdoor scenes
            >>> outdoor_photos = analyzer.search_files(
            ...     tags=['outdoor', 'nature']
            ... )
        """
        # Combine quality and content searches
        results = []
        
        if quality_min is not None or quality_max is not None:
            quality_results = self.database.search_by_quality(
                min_score=quality_min,
                max_score=quality_max,
                limit=limit
            )
            
            if not any([has_faces, min_face_count, object_classes, tags, has_text]):
                # Only quality criteria specified
                return quality_results
            
            # Get file IDs for content search
            file_ids = [r['id'] for r in quality_results]
            
            # Filter by content criteria
            content_results = self.database.search_by_content(
                has_faces=has_faces,
                min_face_count=min_face_count,
                object_classes=object_classes,
                tags=tags,
                has_text=has_text,
                limit=limit
            )
            
            # Find intersection
            content_file_ids = [r['id'] for r in content_results]
            matching_ids = set(file_ids) & set(content_file_ids)
            
            results = [r for r in quality_results if r['id'] in matching_ids]
            
        else:
            # Only content criteria specified
            results = self.database.search_by_content(
                has_faces=has_faces,
                min_face_count=min_face_count,
                object_classes=object_classes,
                tags=tags,
                has_text=has_text,
                limit=limit
            )
        
        return results
    
    def find_duplicates(self) -> List[List[Dict[str, Any]]]:
        """Find potential duplicate files.
        
        Returns:
            List of duplicate groups, each containing files with same hash
            
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> duplicates = analyzer.find_duplicates()
            >>> for group in duplicates:
            ...     print(f"Duplicate group with {len(group)} files:")
            ...     for file in group:
            ...         print(f"  {file['file_path']}")
        """
        return self.database.find_duplicates()
    
    def backup_database(self, backup_path: Union[str, Path]) -> None:
        """Create a backup of the analysis database.
        
        Args:
            backup_path: Path where backup should be saved
            
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> analyzer.backup_database('/backup/media_analysis.db')
        """
        self.database.backup_database(backup_path)
    
    def export_results(
        self, 
        output_path: Union[str, Path], 
        format: str = 'json',
        include_raw_data: bool = False
    ) -> None:
        """Export analysis results to a file.
        
        Args:
            output_path: Path to save exported data
            format: Export format ('json', 'csv')
            include_raw_data: Whether to include raw analysis data
            
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> analyzer.export_results('analysis_results.json')
        """
        import json
        import csv
        
        output_path = Path(output_path)
        
        # Get all files with analysis data
        all_files = self.database.search_by_content(limit=None)
        
        if format.lower() == 'json':
            with open(output_path, 'w') as f:
                json.dump(all_files, f, indent=2, default=str)
        
        elif format.lower() == 'csv':
            if all_files:
                with open(output_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=all_files[0].keys())
                    writer.writeheader()
                    for file_data in all_files:
                        # Convert complex fields to strings for CSV
                        row = {}
                        for key, value in file_data.items():
                            if isinstance(value, (list, dict)):
                                row[key] = json.dumps(value)
                            else:
                                row[key] = value
                        writer.writerow(row)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        logger.info(f"Analysis results exported to: {output_path}")
    
    def close(self) -> None:
        """Close database connections and clean up resources.
        
        Example:
            >>> analyzer = MediaAnalyzer()
            >>> # ... use analyzer ...
            >>> analyzer.close()
        """
        self.database.close()
        logger.info("Media analyzer closed")