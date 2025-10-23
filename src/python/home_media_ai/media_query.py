"""
Media Query Helper

Provides a fluent interface for querying media from the database.
Supports chaining filters and returning results as Media objects or DataFrames.

Usage:
    # Auto-create session (recommended for simple queries)
    with MediaQuery() as query:
        results = query.dng().all()

    # Or manual session management
    query = MediaQuery()
    results = query.rating(5).all()
    query.close()

    # Or provide your own session
    query = MediaQuery(session)
    results = query.canon().raw().rating_min(4).year(2024).all()

    # Return as DataFrame
    df = query.rating_min(3).has_gps().to_dataframe()

    # Random sampling
    results = query.rating(4).random(10)
"""

import pandas as pd
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import or_, func, extract

from .media import Media
from .constants import RAW_EXTENSIONS


class MediaQuery:
    """Fluent interface for querying media from database.

    This class provides chainable methods for building complex queries
    in a readable way. Similar to LINQ in C# or method chaining in MATLAB.

    Can be used with an explicit session or auto-create one:
        # Auto-create (context manager)
        with MediaQuery() as query:
            results = query.rating(5).all()

        # Auto-create (manual)
        query = MediaQuery()
        results = query.rating(5).all()
        query.close()

        # Explicit session
        query = MediaQuery(session)
        results = query.rating(5).all()

    Attributes:
        session: SQLAlchemy session
        _query: Current SQLAlchemy query object
        _owns_session: Whether this instance created and owns the session
    """

    def __init__(self, session: Optional[Session] = None):
        """Initialize query helper.

        Args:
            session: Optional SQLAlchemy session. If None, creates a new session.
        """
        if session is None:
            # Auto-create session using database module
            from .database import get_session
            self.session = get_session()
            self._owns_session = True
        else:
            self.session = session
            self._owns_session = False

        self._query = self.session.query(Media)

    def __enter__(self) -> 'MediaQuery':
        """Enter context manager.

        Returns:
            Self for use in with statement
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager, closing session if we own it.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        self.close()
        return False  # Don't suppress exceptions

    def close(self):
        """Close the session if we own it.

        Only closes the session if it was auto-created by this instance.
        If an external session was provided, it's the caller's responsibility to close it.
        """
        if self._owns_session and self.session:
            self.session.close()
            self._owns_session = False

    def reset(self) -> 'MediaQuery':
        """Reset query to start fresh.

        Returns:
            Self for chaining
        """
        self._query = self.session.query(Media)
        return self

    # ==========================================
    # File Type Filters
    # ==========================================

    def originals_only(self) -> 'MediaQuery':
        """Filter to only original files (not derivatives).

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.is_original.is_(True))
        return self

    def derivatives_only(self) -> 'MediaQuery':
        """Filter to only derivative files.

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.is_original.is_(False))
        return self

    def raw(self) -> 'MediaQuery':
        """Filter to RAW image files (DNG, CR2, NEF, ARW).

        Returns:
            Self for chaining
        """
        raw_exts = list(RAW_EXTENSIONS)
        self._query = self._query.filter(Media.file_ext.in_(raw_exts))
        return self

    def dng(self) -> 'MediaQuery':
        """Filter to DNG files only.

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.file_ext == '.dng')
        return self

    def jpeg(self) -> 'MediaQuery':
        """Filter to JPEG files.

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.file_ext.in_(['.jpg', '.jpeg']))
        return self

    def extension(self, ext: str) -> 'MediaQuery':
        """Filter by file extension.

        Args:
            ext: File extension (with or without leading dot)

        Returns:
            Self for chaining
        """
        if not ext.startswith('.'):
            ext = f'.{ext}'
        self._query = self._query.filter(Media.file_ext == ext.lower())
        return self

    # ==========================================
    # Rating Filters
    # ==========================================

    def rating(self, stars: int) -> 'MediaQuery':
        """Filter by exact rating.

        Args:
            stars: Rating value (0-5)

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.rating == stars)
        return self

    def rating_min(self, stars: int) -> 'MediaQuery':
        """Filter by minimum rating.

        Args:
            stars: Minimum rating (0-5)

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.rating >= stars)
        return self

    def rating_max(self, stars: int) -> 'MediaQuery':
        """Filter by maximum rating.

        Args:
            stars: Maximum rating (0-5)

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.rating <= stars)
        return self

    def rating_between(self, min_stars: int, max_stars: int) -> 'MediaQuery':
        """Filter by rating range.

        Args:
            min_stars: Minimum rating
            max_stars: Maximum rating

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(
            Media.rating >= min_stars,
            Media.rating <= max_stars
        )
        return self

    def has_rating(self) -> 'MediaQuery':
        """Filter to only files with ratings.

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.rating.isnot(None))
        return self

    def no_rating(self) -> 'MediaQuery':
        """Filter to only files without ratings.

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.rating.is_(None))
        return self

    # ==========================================
    # Camera Filters
    # ==========================================

    def camera_make(self, make: str) -> 'MediaQuery':
        """Filter by camera manufacturer (case-insensitive, partial match).

        Args:
            make: Camera make (e.g., 'Canon', 'Nikon', 'Sony')

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.camera_make.ilike(f'%{make}%'))
        return self

    def camera_model(self, model: str) -> 'MediaQuery':
        """Filter by camera model (case-insensitive, partial match).

        Args:
            model: Camera model

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.camera_model.ilike(f'%{model}%'))
        return self

    def canon(self) -> 'MediaQuery':
        """Convenience filter for Canon cameras.

        Returns:
            Self for chaining
        """
        return self.camera_make('Canon')

    def nikon(self) -> 'MediaQuery':
        """Convenience filter for Nikon cameras.

        Returns:
            Self for chaining
        """
        return self.camera_make('Nikon')

    def sony(self) -> 'MediaQuery':
        """Convenience filter for Sony cameras.

        Returns:
            Self for chaining
        """
        return self.camera_make('Sony')

    # ==========================================
    # GPS / Location Filters
    # ==========================================

    def has_gps(self) -> 'MediaQuery':
        """Filter to only files with GPS coordinates.

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(
            Media.gps_latitude.isnot(None),
            Media.gps_longitude.isnot(None)
        )
        return self

    def no_gps(self) -> 'MediaQuery':
        """Filter to only files without GPS coordinates.

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(
            or_(
                Media.gps_latitude.is_(None),
                Media.gps_longitude.is_(None)
            )
        )
        return self

    def gps_bbox(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> 'MediaQuery':
        """Filter by GPS bounding box.

        Args:
            min_lat: Minimum latitude
            max_lat: Maximum latitude
            min_lon: Minimum longitude
            max_lon: Maximum longitude

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(
            Media.gps_latitude.between(min_lat, max_lat),
            Media.gps_longitude.between(min_lon, max_lon)
        )
        return self

    # ==========================================
    # Date/Time Filters
    # ==========================================

    def year(self, year: int) -> 'MediaQuery':
        """Filter by year.

        Args:
            year: Year (e.g., 2024)

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(extract('year', Media.created) == year)
        return self

    def month(self, month: int) -> 'MediaQuery':
        """Filter by month (1-12).

        Args:
            month: Month number (1-12)

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(extract('month', Media.created) == month)
        return self

    def year_month(self, year: int, month: int) -> 'MediaQuery':
        """Filter by year and month.

        Args:
            year: Year
            month: Month (1-12)

        Returns:
            Self for chaining
        """
        return self.year(year).month(month)

    def date_range(self, start: datetime, end: datetime) -> 'MediaQuery':
        """Filter by date range.

        Args:
            start: Start datetime (inclusive)
            end: End datetime (inclusive)

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(
            Media.created >= start,
            Media.created <= end
        )
        return self

    def after(self, date: datetime) -> 'MediaQuery':
        """Filter to files created after date.

        Args:
            date: Cutoff date

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.created >= date)
        return self

    def before(self, date: datetime) -> 'MediaQuery':
        """Filter to files created before date.

        Args:
            date: Cutoff date

        Returns:
            Self for chaining
        """
        self._query = self._query.filter(Media.created <= date)
        return self

    # ==========================================
    # Size Filters
    # ==========================================

    def min_resolution(self, megapixels: float) -> 'MediaQuery':
        """Filter by minimum resolution.

        Args:
            megapixels: Minimum megapixels (e.g., 12.0 for 12MP)

        Returns:
            Self for chaining
        """
        min_pixels = int(megapixels * 1_000_000)
        self._query = self._query.filter(
            (Media.width * Media.height) >= min_pixels
        )
        return self

    def max_file_size(self, size_mb: float) -> 'MediaQuery':
        """Filter by maximum file size.

        Args:
            size_mb: Maximum size in megabytes

        Returns:
            Self for chaining
        """
        max_bytes = int(size_mb * 1024 * 1024)
        self._query = self._query.filter(Media.file_size <= max_bytes)
        return self

    def min_file_size(self, size_mb: float) -> 'MediaQuery':
        """Filter by minimum file size.

        Args:
            size_mb: Minimum size in megabytes

        Returns:
            Self for chaining
        """
        min_bytes = int(size_mb * 1024 * 1024)
        self._query = self._query.filter(Media.file_size >= min_bytes)
        return self

    # ==========================================
    # Sorting
    # ==========================================

    def sort_by_date(self, ascending: bool = False) -> 'MediaQuery':
        """Sort by creation date.

        Args:
            ascending: If True, oldest first. If False, newest first.

        Returns:
            Self for chaining
        """
        if ascending:
            self._query = self._query.order_by(Media.created.asc())
        else:
            self._query = self._query.order_by(Media.created.desc())
        return self

    def sort_by_rating(self, ascending: bool = False) -> 'MediaQuery':
        """Sort by rating.

        Args:
            ascending: If True, lowest first. If False, highest first.

        Returns:
            Self for chaining
        """
        if ascending:
            self._query = self._query.order_by(Media.rating.asc())
        else:
            self._query = self._query.order_by(Media.rating.desc())
        return self

    def sort_by_file_size(self, ascending: bool = True) -> 'MediaQuery':
        """Sort by file size.

        Args:
            ascending: If True, smallest first. If False, largest first.

        Returns:
            Self for chaining
        """
        if ascending:
            self._query = self._query.order_by(Media.file_size.asc())
        else:
            self._query = self._query.order_by(Media.file_size.desc())
        return self

    def sort_random(self) -> 'MediaQuery':
        """Sort randomly.

        Returns:
            Self for chaining
        """
        self._query = self._query.order_by(func.random())
        return self

    # ==========================================
    # Result Retrieval
    # ==========================================

    def all(self) -> List[Media]:
        """Execute query and return all results.

        Returns:
            List of Media objects
        """
        return self._query.all()

    def first(self) -> Optional[Media]:
        """Execute query and return first result.

        Returns:
            First Media object or None
        """
        return self._query.first()

    def one(self) -> Media:
        """Execute query and return exactly one result.

        Raises:
            sqlalchemy.orm.exc.NoResultFound: If no results
            sqlalchemy.orm.exc.MultipleResultsFound: If multiple results

        Returns:
            Single Media object
        """
        return self._query.one()

    def count(self) -> int:
        """Get count of matching records without retrieving them.

        Returns:
            Number of matching records
        """
        return self._query.count()

    def limit(self, n: int) -> 'MediaQuery':
        """Limit number of results.

        Args:
            n: Maximum number of results

        Returns:
            Self for chaining
        """
        self._query = self._query.limit(n)
        return self

    def random(self, n: int = 1) -> List[Media]:
        """Get random sample of results.

        Args:
            n: Number of random results

        Returns:
            List of Media objects
        """
        return self.sort_random().limit(n).all()

    def to_dataframe(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """Execute query and return results as pandas DataFrame.

        Args:
            columns: List of column names to include. If None, includes common columns.

        Returns:
            DataFrame with query results
        """
        results = self.all()

        if not results:
            return pd.DataFrame()

        if columns is None:
            # Default columns for DataFrame
            columns = [
                'id', 'storage_root', 'directory', 'filename', 'file_ext', 'file_size',
                'rating', 'camera_make', 'camera_model',
                'gps_latitude', 'gps_longitude', 'gps_altitude',
                'width', 'height', 'created', 'is_original'
            ]

        data = []
        for media in results:
            row = {
                col: (
                    media.get_full_path()
                    if col == 'file_path'
                    else getattr(media, col, None)
                )
                for col in columns
            }
            data.append(row)

        return pd.DataFrame(data)

    def to_paths(self) -> List[str]:
        """Execute query and return just file paths.

        Returns:
            List of file paths as strings
        """
        results = self.all()
        return [media.get_full_path() for media in results]

    # ==========================================
    # Statistics / Aggregation
    # ==========================================

    def stats(self) -> dict:
        """Get statistics about the query results.

        Returns:
            Dictionary with count, rating stats, file size stats, etc.
        """
        results = self.all()

        if not results:
            return {
                'count': 0,
                'total_size_mb': 0,
                'avg_rating': None,
                'avg_file_size_mb': 0
            }

        ratings = [m.rating for m in results if m.rating is not None]
        file_sizes = [m.file_size for m in results]

        return {
            'count': len(results),
            'total_size_mb': sum(file_sizes) / (1024 * 1024),
            'avg_file_size_mb': sum(file_sizes) / len(file_sizes) / (1024 * 1024),
            'min_file_size_mb': min(file_sizes) / (1024 * 1024),
            'max_file_size_mb': max(file_sizes) / (1024 * 1024),
            'avg_rating': sum(ratings) / len(ratings) if ratings else None,
            'rated_count': len(ratings),
            'unrated_count': len(results) - len(ratings),
            'with_gps': sum(m.gps_latitude is not None and m.gps_longitude is not None for m in results),
            'without_gps': sum(m.gps_latitude is None or m.gps_longitude is None for m in results),
        }
