#!/usr/bin/env python3
"""
Script to organize photos into a date-based directory structure.

Usage:
    python organize_photos.py /path/to/source [--execute] [--config /path/to/config.yaml]
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure we can import the package if running from source
src_path = Path(__file__).resolve().parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from home_media.organizer import organize_directory

def setup_logging(verbose: bool = False):
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )
    # Ensure our package logger is at least INFO
    logging.getLogger("home_media").setLevel(logging.INFO)

def main():
    parser = argparse.ArgumentParser(
        description="Organize photos into date-based directories."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Source directory to scan for photos"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually move files (default is dry-run)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    
    source_dir = args.source
    dry_run = not args.execute

    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)

    print(f"Starting organization of '{source_dir}'...")
    if dry_run:
        print("DRY RUN: No files will be moved. Use --execute to proceed.")

    try:
        result = organize_directory(source_dir, args.config, dry_run=dry_run)
        print("\nOrganization Complete:")
        print(result)
        
        if result.errors:
            print("\nErrors encountered:")
            for path, error in result.errors:
                print(f"  {path}: {error}")
                
    except Exception as e:
        print(f"\nCritical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
