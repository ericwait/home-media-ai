#!/usr/bin/env python3
"""Generate thumbnails for existing media files in the database.

Usage:
    python generate_thumbnails.py [--limit N] [--workers N] [--sequential] [--commit-interval N] [--error-log FILE]

Options:
    --limit N            Only generate N thumbnails (useful for testing)
    --workers N          Number of parallel threads (default: 4)
    --sequential         Use sequential processing instead of parallel
    --commit-interval N  Commit database changes every N items in sequential mode (default: 100)
    --error-log FILE     CSV file to log failed files (default: thumbnail_errors.csv)

Notes:
    - Parallel mode (default) uses 4 threads with batched database commits
    - Each thread has its own database connection
    - For Windows with remote databases, 4 threads should be safe
    - Use --sequential if you encounter connection issues
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from home_media_ai.config import Config
from home_media_ai.database import get_session
from home_media_ai.thumbnails import (
    generate_missing_thumbnails,
    generate_missing_thumbnails_parallel
)

# Configure logging to show progress
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    parser = argparse.ArgumentParser(description='Generate thumbnails for media files')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of thumbnails to generate')
    parser.add_argument('--workers', type=int, default=4,
                        help='Number of parallel threads (default: 4)')
    parser.add_argument('--sequential', action='store_true',
                        help='Use sequential processing instead of parallel')
    parser.add_argument('--commit-interval', type=int, default=100,
                        help='Commit database changes every N items in sequential mode (default: 100)')
    parser.add_argument('--error-log', type=str, default='thumbnail_errors.csv',
                        help='CSV file to log failed files (default: thumbnail_errors.csv)')
    args = parser.parse_args()

    # Load config
    try:
        config = Config.load()
        database_uri = config.database.uri
        if not database_uri:
            print("Error: No database URI configured")
            sys.exit(1)
        print("Loaded configuration")
    except Exception as e:
        print(f"Error: Could not load config: {e}")
        sys.exit(1)

    with get_session() as session:
        if args.sequential:
            print("Generating missing thumbnails (sequential)...")
            successful, failed = generate_missing_thumbnails(
                session,
                limit=args.limit,
                commit_interval=args.commit_interval,
                error_log_file=args.error_log
            )
            print(f"Results: {successful} generated, {failed} failed")
            if failed > 0:
                print(f"Failed files logged to: {args.error_log}")
        else:
            print(f"Generating missing thumbnails (parallel with {args.workers} threads)...")
            successful, failed = generate_missing_thumbnails_parallel(
                session,
                limit=args.limit,
                num_threads=args.workers,
                batch_size=100,
                error_log_file=args.error_log
            )
            print(f"Results: {successful} generated, {failed} failed")
            if failed > 0:
                print(f"Failed files logged to: {args.error_log}")


if __name__ == '__main__':
    main()
