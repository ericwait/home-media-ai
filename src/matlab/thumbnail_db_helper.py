#!/usr/bin/env python3
"""
Database helper for MATLAB thumbnail generation.

Handles database queries and updates so MATLAB doesn't need JDBC setup.
"""

import sys
import json
import argparse
from pathlib import Path

# Add Python package to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from home_media_ai.config import Config
from home_media_ai.database import get_session
from home_media_ai.media import Media


def query_media(limit=None):
    """Query media items without thumbnails and output as JSON."""
    config = Config.load()

    with get_session() as session:
        query = session.query(
            Media.id,
            Media.storage_root,
            Media.directory,
            Media.filename,
            Media.file_ext
        ).filter(Media.thumbnail_path.is_(None))

        if limit:
            query = query.limit(limit)

        results = query.all()

        # Convert to list of dicts
        media_items = [
            {
                'id': r.id,
                'storage_root': r.storage_root,
                'directory': r.directory if r.directory else '',
                'filename': r.filename,
                'file_ext': r.file_ext
            }
            for r in results
        ]

        # Output as JSON
        print(json.dumps(media_items))


def update_thumbnails(updates_file):
    """Update thumbnail paths in database from JSON file."""
    # Read updates from file
    with open(updates_file, 'r') as f:
        updates = json.load(f)

    config = Config.load()

    with get_session() as session:
        for update in updates:
            media_id = update['media_id']
            thumbnail_path = update['thumbnail_path']

            # Update the media record
            media = session.query(Media).filter(Media.id == media_id).first()
            if media:
                media.thumbnail_path = thumbnail_path

        # Commit all updates
        session.commit()

    print(f"Updated {len(updates)} records")


def main():
    parser = argparse.ArgumentParser(description='Database helper for MATLAB thumbnail generation')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Query command
    query_parser = subparsers.add_parser('query', help='Query media without thumbnails')
    query_parser.add_argument('--limit', type=int, help='Limit number of results')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update thumbnail paths')
    update_parser.add_argument('updates_file', help='JSON file with updates')

    args = parser.parse_args()

    if args.command == 'query':
        query_media(args.limit)
    elif args.command == 'update':
        update_thumbnails(args.updates_file)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
