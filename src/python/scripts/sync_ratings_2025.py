#!/usr/bin/env python3
"""
Sync ratings to files for images from 2025 with rating >= 3.

This script queries the database for media items that match the criteria
(year 2025, rating >= 3) and writes the rating back to the file metadata
(EXIF for JPG, XMP sidecar for others).
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from home_media_ai.database import get_session
from home_media_ai.media import Media
from home_media_ai.rating_sync import sync_rating_to_file, read_rating_from_file

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Execute the rating sync process."""
    parser = argparse.ArgumentParser(description="Sync ratings to files for 2025 media.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing to files")
    parser.add_argument("--limit", type=int, help="Limit number of items to process")
    args = parser.parse_args()

    session = get_session()
    
    try:
        # Define criteria
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2026, 1, 1)
        min_rating = 3
        
        logger.info(f"Querying for media from 2025 with rating >= {min_rating}...")
        
        # Query database
        media_items = session.query(Media).filter(
            Media.created >= start_date,
            Media.created < end_date,
            Media.rating >= min_rating
        ).all()
        
        count = len(media_items)
        if count == 0:
            logger.info("No matching media items found.")
            return
            
        logger.info(f"Found {count} items. Starting sync...")
        if args.dry_run:
            logger.info("DRY RUN ENABLED: No changes will be made.")
        if args.limit:
            logger.info(f"Limit set to {args.limit} items.")
        
        successful = 0
        failed = 0
        skipped = 0
        processed = 0
        
        for i, media in enumerate(media_items, 1):
            if args.limit and processed >= args.limit:
                logger.info(f"Limit of {args.limit} reached. Stopping.")
                break

            try:
                # Log progress every 10 items
                if i % 10 == 0:
                    logger.info(f"Processing {i}/{count}...")
                
                file_path = media.get_full_path(use_local_mapping=True)
                
                if args.dry_run:
                    current_file_rating = read_rating_from_file(file_path)
                    if current_file_rating == media.rating:
                        logger.info(f"[DRY RUN] Would SKIP (already {media.rating}): {file_path}")
                        skipped += 1
                    else:
                        logger.info(f"[DRY RUN] Would UPDATE (from {current_file_rating} to {media.rating}): {file_path}")
                        successful += 1
                else:
                    # In non-dry run, sync_rating_to_file handles the "already correct" logic
                    # and returns True, but we can check if it was skipped by comparing
                    # before and after or just trusting its log.
                    # For accuracy in the count, we'll check here too:
                    current_file_rating = read_rating_from_file(file_path)
                    if current_file_rating == media.rating:
                        logger.info(f"Already {media.rating} in file: {Path(file_path).name}. Skipping.")
                        skipped += 1
                    else:
                        result = sync_rating_to_file(
                            media=media,
                            rating=media.rating,
                            session=session,
                            use_local_mapping=True,
                            file_path=Path(file_path)
                        )
                        
                        if result:
                            successful += 1
                        else:
                            failed += 1
                
                processed += 1
                    
            except Exception as e:
                logger.error(f"Error processing media ID {media.id}: {e}")
                failed += 1
                
        logger.info("=" * 40)
        logger.info(f"Sync complete.")
        logger.info(f"Total processed: {processed}")
        if args.dry_run:
             logger.info(f"Would update: {successful}")
             logger.info(f"Would skip:   {skipped}")
        else:
            logger.info(f"Updated: {successful}")
            logger.info(f"Skipped: {skipped}")
            logger.info(f"Failed:  {failed}")
        logger.info("=" * 40)
        
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}")
    finally:
        session.close()
if __name__ == "__main__":
    main()
