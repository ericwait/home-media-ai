#!/usr/bin/env python3
"""Generate thumbnails for existing media files in the database.

Usage:
    python generate_thumbnails.py [--limit N] [--check-integrity] [--workers N] [--sequential] [--commit-interval N]

Options:
    --limit N            Only generate N thumbnails (useful for testing)
    --check-integrity    Check existing thumbnails and regenerate missing ones
    --workers N          Number of parallel workers (default: 4)
    --sequential         Use sequential processing (RECOMMENDED for remote databases on Windows)
    --commit-interval N  Commit database changes every N items in sequential mode (default: 100)

Notes:
    - For remote databases on Windows, use --sequential to avoid port exhaustion
    - Parallel mode works best with local databases or Linux systems
    - Use --workers 2 for remote databases if you need parallel processing
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.config import Config
from home_media_ai.database import get_session
from home_media_ai.thumbnails import (
    generate_missing_thumbnails,
    generate_missing_thumbnails_parallel,
    check_thumbnail_integrity,
    check_thumbnail_integrity_parallel
)


def main():
    parser = argparse.ArgumentParser(description='Generate thumbnails for media files')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of thumbnails to generate')
    parser.add_argument('--check-integrity', action='store_true',
                        help='Check existing thumbnails and regenerate missing ones')
    parser.add_argument('--workers', type=int, default=4,
                        help='Number of parallel workers (default: 4, recommended for remote databases)')
    parser.add_argument('--sequential', action='store_true',
                        help='Use sequential processing instead of parallel')
    parser.add_argument('--commit-interval', type=int, default=100,
                        help='Commit database changes every N items (default: 100)')
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
        if args.check_integrity:
            if args.sequential:
                print("Checking thumbnail integrity (sequential)...")
                valid, missing, regenerated = check_thumbnail_integrity(
                    session,
                    regenerate=True,
                    commit_interval=args.commit_interval
                )
            else:
                print("Checking thumbnail integrity (parallel)...")
                valid, missing, regenerated = check_thumbnail_integrity_parallel(
                    session,
                    database_uri=database_uri,
                    regenerate=True,
                    workers=args.workers
                )
            print(f"Results: {valid} valid, {missing} missing, {regenerated} regenerated")
        elif args.sequential:
            print("Generating missing thumbnails (sequential)...")
            successful, failed = generate_missing_thumbnails(
                session,
                limit=args.limit
            )
            print(f"Results: {successful} generated, {failed} failed")
        else:
            print("Generating missing thumbnails (parallel)...")
            successful, failed = generate_missing_thumbnails_parallel(
                session,
                database_uri=database_uri,
                limit=args.limit,
                workers=args.workers
            )
            print(f"Results: {successful} generated, {failed} failed")


if __name__ == '__main__':
    main()
