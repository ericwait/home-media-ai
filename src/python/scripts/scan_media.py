#!/usr/bin/env python3
"""
Scan and import media files into the home media database.

This script discovers media files, extracts metadata, and imports them
into the database with proper RAW/derivative relationships.

Usage:
    # Dry run - preview what would be imported
    python scan_media.py --root /path/to/photos --dry-run

    # Import with EXIF extraction
    python scan_media.py --root /path/to/photos

    # Import specific year
    python scan_media.py --root /path/to/photos --year 2024
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.scanner import MediaScanner
from home_media_ai.importer import MediaImporter
from home_media_ai.exif_extractor import ExifExtractor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_progress(message: str):
    """Print progress updates to console."""
    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}")


def dry_run_scan(scanner: MediaScanner):
    """Perform a dry run scan without importing to database.

    Args:
        scanner: MediaScanner instance

    Returns:
        Dict with statistics about what would be imported
    """
    print("=" * 70)
    print("DRY RUN MODE - No changes will be made to the database")
    print("=" * 70)
    print()

    # Scan files
    print_progress("Scanning for media files...")
    files = list(scanner.scan_files(progress_callback=print_progress))

    if not files:
        print("No media files found.")
        return {'files': 0, 'pairs': 0, 'originals': 0, 'derivatives': 0}

    print_progress(f"Found {len(files)} media files")
    print()

    # Group by timestamp
    print_progress("Grouping files by timestamp...")
    grouped = scanner.group_by_timestamp(iter(files))
    print_progress(f"Found {len(grouped)} unique timestamps")
    print()

    # Identify pairs
    print_progress("Identifying RAW/derivative pairs...")
    pairs = list(scanner.identify_pairs(grouped))

    # Count statistics
    stats = {
        'files': len(files),
        'pairs': len(pairs),
        'originals': len(pairs),
        'derivatives': sum(1 for _, deriv in pairs if deriv is not None)
    }

    print()
    print("=" * 70)
    print("DRY RUN SUMMARY")
    print("=" * 70)
    print(f"Total files found:        {stats['files']}")
    print(f"File groups (pairs):      {stats['pairs']}")
    print(f"  - Original files:       {stats['originals']}")
    print(f"  - Derivative files:     {stats['derivatives']}")
    print()

    # Show file type breakdown
    type_counts = {}
    for file_info in files:
        type_counts[file_info.media_type] = type_counts.get(file_info.media_type, 0) + 1

    print("File types:")
    for media_type, count in sorted(type_counts.items()):
        print(f"  {media_type:15} {count:5} files")
    print()

    # Show sample pairs
    print("Sample file pairs (first 5):")
    print("-" * 70)
    for i, (original, derivative) in enumerate(pairs[:5], 1):
        print(f"{i}. Original:   {Path(original.path).name}")
        print(f"   Type:       {original.media_type}")
        print(f"   Size:       {original.size / 1_000_000:.1f} MB")
        print(f"   Timestamp:  {original.timestamp}")

        if derivative:
            print(f"   Derivative: {Path(derivative.path).name}")
            print(f"   Type:       {derivative.media_type}")
            print(f"   Size:       {derivative.size / 1_000_000:.1f} MB")
        else:
            print(f"   Derivative: (none)")
        print()

    if len(pairs) > 5:
        print(f"... and {len(pairs) - 5} more pairs")

    # Show sample EXIF data
    if pairs and pairs[0][0].exif_data:
        print()
        print("=" * 70)
        print("SAMPLE EXIF DATA (first file)")
        print("=" * 70)

        original = pairs[0][0]
        exif = original.exif_data

        print(f"File: {Path(original.path).name}")
        print()

        if 'rating' in exif:
            print(f"  rating:        {exif['rating']}")
        if 'gps_latitude' in exif:
            print(f"  gps_latitude:  {exif['gps_latitude']:.6f}")
        if 'gps_longitude' in exif:
            print(f"  gps_longitude: {exif['gps_longitude']:.6f}")
        if 'gps_altitude' in exif:
            print(f"  gps_altitude:  {exif['gps_altitude']:.2f} m")
        if 'camera_make' in exif:
            print(f"  camera_make:   {exif['camera_make']}")
        if 'camera_model' in exif:
            print(f"  camera_model:  {exif['camera_model']}")
        if 'lens_model' in exif:
            print(f"  lens_model:    {exif['lens_model']}")
        if 'width' in exif:
            print(f"  width:         {exif['width']} px")
        if 'height' in exif:
            print(f"  height:        {exif['height']} px")

        print()

    print("=" * 70)
    print("To proceed with import, run without --dry-run flag")
    print("=" * 70)

    return stats


def perform_import(scanner: MediaScanner, database_uri: str):
    """Perform actual import to database.

    Args:
        scanner: MediaScanner instance
        database_uri: Database connection string
    """
    print("=" * 70)
    print("IMPORT MODE - Changes will be written to database")
    print("=" * 70)
    print()

    # Scan files
    print_progress("Scanning for media files...")
    files = list(scanner.scan_files(progress_callback=print_progress))

    if not files:
        print("No media files found.")
        return

    print_progress(f"Found {len(files)} media files")
    print()

    # Group by timestamp
    print_progress("Grouping files by timestamp...")
    grouped = scanner.group_by_timestamp(iter(files))
    print_progress(f"Found {len(grouped)} unique timestamps")
    print()

    # Identify pairs
    print_progress("Identifying RAW/derivative pairs...")
    pairs = list(scanner.identify_pairs(grouped))
    print_progress(f"Identified {len(pairs)} file pairs")
    print()

    # Import to database
    print_progress("Connecting to database...")

    try:
        importer = MediaImporter(database_uri)

        print_progress("Starting import (EXIF extraction: enabled)...")

        stats = importer.import_file_pairs(
            iter(pairs),
            progress_callback=print_progress
        )

        importer.close()

        print()
        print("=" * 70)
        print("IMPORT COMPLETE")
        print("=" * 70)
        print(f"Imported:  {stats['imported']} files")
        print(f"Skipped:   {stats['skipped']} files (already in database)")
        print(f"Errors:    {stats['errors']} files")
        print("=" * 70)

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        print()
        print(f"ERROR: Import failed - {e}")
        sys.exit(1)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Scan and import media files into the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Dry run to preview what would be imported:
    python scan_media.py --root /photos --dry-run

  Import all photos from 2024:
    python scan_media.py --root /photos --year 2024
        """
    )

    parser.add_argument(
        '--root',
        required=True,
        help='Root directory to scan for media files'
    )

    parser.add_argument(
        '--year',
        type=int,
        help='Limit scan to a specific year subdirectory'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be imported without making changes'
    )

    parser.add_argument(
        '--database-uri',
        help='Database URI (defaults to HOME_MEDIA_AI_URI environment variable)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger('home_media_ai').setLevel(logging.DEBUG)

    # Determine scan path
    scan_path = Path(args.root)
    if args.year:
        scan_path = scan_path / str(args.year)

    if not scan_path.exists():
        print(f"ERROR: Path does not exist: {scan_path}")
        sys.exit(1)

    print(f"Scanning directory: {scan_path}")
    print()

    # Initialize scanner with EXIF extractor
    scanner = MediaScanner(
        str(scan_path),
        exif_extractor=ExifExtractor()
    )

    # Perform dry run or actual import
    if args.dry_run:
        dry_run_scan(scanner)
    else:
        # Get database URI
        database_uri = args.database_uri or os.getenv('HOME_MEDIA_AI_URI')
        if not database_uri:
            print("ERROR: No database URI provided.")
            print("Use --database-uri or set HOME_MEDIA_AI_URI environment variable")
            sys.exit(1)

        perform_import(scanner, database_uri)


if __name__ == '__main__':
    main()
