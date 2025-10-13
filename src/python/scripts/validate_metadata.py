#!/usr/bin/env python3
"""
Metadata Validation Script

Randomly selects files from the database and validates that the stored
metadata matches what is currently in the file and its XMP sidecar.

Usage:
    python validate_metadata.py --samples 10
    python validate_metadata.py --samples 50 --verbose
    python validate_metadata.py --rating-only  # Only check rated files
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import random

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.exif_extractor import ExifExtractor
from home_media_ai.media import Media

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetadataValidator:
    """Validates database metadata against actual file metadata."""

    # Fields to validate (column name -> metadata key)
    VALIDATION_FIELDS = {
        'rating': 'rating',
        'gps_latitude': 'gps_latitude',
        'gps_longitude': 'gps_longitude',
        'gps_altitude': 'gps_altitude',
        'camera_make': 'camera_make',
        'camera_model': 'camera_model',
        'lens_model': 'lens_model',
        'width': 'width',
        'height': 'height'
    }

    def __init__(self, database_uri: str):
        """Initialize validator with database connection.

        Args:
            database_uri: SQLAlchemy database connection string
        """
        self.engine = create_engine(database_uri)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.extractor = ExifExtractor()

    def get_random_samples(self, n: int = 10, rating_only: bool = False) -> List[Media]:
        """Get random media samples from database.

        Args:
            n: Number of samples to retrieve
            rating_only: Only select files with ratings

        Returns:
            List of Media objects
        """
        query = self.session.query(Media).filter(Media.is_original == True)

        if rating_only:
            query = query.filter(Media.rating.isnot(None))

        # Get total count
        total = query.count()
        if total == 0:
            logger.warning("No files found matching criteria")
            return []

        # Get random samples
        samples = query.order_by(text('RAND()')).limit(min(n, total)).all()
        logger.info(f"Selected {len(samples)} random files from {total} total")

        return samples

    def validate_file(self, media: Media) -> Tuple[bool, Dict]:
        """Validate a single file's metadata.

        Args:
            media: Media object from database

        Returns:
            Tuple of (all_valid, differences_dict)
        """
        file_path = media.file_path

        # Check if file exists
        if not Path(file_path).exists():
            return False, {'error': 'File not found'}

        # Extract current metadata
        try:
            current_metadata = self.extractor.extract_metadata(file_path)
        except Exception as e:
            return False, {'error': f'Extraction failed: {e}'}

        # Compare each field
        differences = {}
        all_valid = True

        for db_field, meta_key in self.VALIDATION_FIELDS.items():
            db_value = getattr(media, db_field, None)
            file_value = current_metadata.get(meta_key)

            # Skip if both are None
            if db_value is None and file_value is None:
                continue

            # Compare values with tolerance for floats
            if self._values_differ(db_value, file_value):
                differences[db_field] = {
                    'database': db_value,
                    'file': file_value
                }
                all_valid = False

        return all_valid, differences

    def _values_differ(self, db_val, file_val, tolerance: float = 1e-6) -> bool:
        """Check if two values differ significantly.

        Args:
            db_val: Value from database
            file_val: Value from file
            tolerance: Tolerance for float comparisons

        Returns:
            True if values differ
        """
        # Both None or both same
        if db_val is None and file_val is None:
            return False

        # One is None
        if db_val is None or file_val is None:
            return True

        # Float comparison with tolerance
        if isinstance(db_val, (float, int)) and isinstance(file_val, (float, int)):
            return abs(float(db_val) - float(file_val)) > tolerance

        # String comparison (case-insensitive, stripped)
        if isinstance(db_val, str) and isinstance(file_val, str):
            return db_val.strip().lower() != file_val.strip().lower()

        # Direct comparison
        return db_val != file_val

    def validate_samples(self, samples: List[Media], verbose: bool = False) -> Dict:
        """Validate multiple samples and return statistics.

        Args:
            samples: List of Media objects to validate
            verbose: Print detailed results for each file

        Returns:
            Dict with validation statistics
        """
        stats = {
            'total': len(samples),
            'valid': 0,
            'invalid': 0,
            'errors': 0,
            'differences_by_field': {}
        }

        print("=" * 70)
        print(f"VALIDATING {len(samples)} FILES")
        print("=" * 70)
        print()

        for i, media in enumerate(samples, 1):
            print(f"[{i}/{len(samples)}] {Path(media.file_path).name}")

            is_valid, differences = self.validate_file(media)

            if 'error' in differences:
                stats['errors'] += 1
                print(f"  ✗ ERROR: {differences['error']}")
                if verbose:
                    print(f"  Path: {media.file_path}")
            elif is_valid:
                stats['valid'] += 1
                print(f"  ✓ Valid - all metadata matches")
            else:
                stats['invalid'] += 1
                print(f"  ✗ Invalid - {len(differences)} field(s) differ:")

                for field, diff in differences.items():
                    # Track which fields have issues
                    if field not in stats['differences_by_field']:
                        stats['differences_by_field'][field] = 0
                    stats['differences_by_field'][field] += 1

                    # Print difference
                    print(f"    {field}:")
                    print(f"      Database: {diff['database']}")
                    print(f"      File:     {diff['file']}")

                if verbose:
                    print(f"  Path: {media.file_path}")

            print()

        return stats

    def print_summary(self, stats: Dict):
        """Print validation summary statistics.

        Args:
            stats: Statistics dictionary from validate_samples
        """
        print("=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Total files checked:  {stats['total']}")
        print(f"Valid:                {stats['valid']} ({stats['valid']/stats['total']*100:.1f}%)")
        print(f"Invalid:              {stats['invalid']} ({stats['invalid']/stats['total']*100:.1f}%)")
        print(f"Errors:               {stats['errors']} ({stats['errors']/stats['total']*100:.1f}%)")

        if stats['differences_by_field']:
            print()
            print("Fields with differences:")
            for field, count in sorted(stats['differences_by_field'].items(),
                                       key=lambda x: x[1], reverse=True):
                print(f"  {field:20} {count:3} file(s)")

        print("=" * 70)

    def close(self):
        """Close database connection."""
        self.session.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate database metadata against actual file metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Validate 10 random files:
    python validate_metadata.py

  Validate 50 files with detailed output:
    python validate_metadata.py --samples 50 --verbose

  Only check files with ratings:
    python validate_metadata.py --samples 20 --rating-only
        """
    )

    parser.add_argument(
        '--samples',
        type=int,
        default=10,
        help='Number of random files to validate (default: 10)'
    )

    parser.add_argument(
        '--rating-only',
        action='store_true',
        help='Only validate files that have ratings'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed information for each file'
    )

    parser.add_argument(
        '--database-uri',
        help='Database URI (defaults to HOME_MEDIA_AI_URI environment variable)'
    )

    args = parser.parse_args()

    # Get database URI
    database_uri = args.database_uri or os.getenv('HOME_MEDIA_AI_URI')
    if not database_uri:
        print("ERROR: No database URI provided.")
        print("Use --database-uri or set HOME_MEDIA_AI_URI environment variable")
        sys.exit(1)

    # Run validation
    try:
        validator = MetadataValidator(database_uri)

        # Get samples
        samples = validator.get_random_samples(
            n=args.samples,
            rating_only=args.rating_only
        )

        if not samples:
            print("No files found to validate")
            sys.exit(0)

        # Validate
        stats = validator.validate_samples(samples, verbose=args.verbose)

        # Print summary
        validator.print_summary(stats)

        validator.close()

        # Exit with error code if there were invalid files
        if stats['invalid'] > 0 or stats['errors'] > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
