#!/usr/bin/env python3
"""
Script to fix 'directory' and 'storage_root' columns for media files.
It parses dates from filenames (yyyy-mm-dd) and attempts to normalize
the storage_root by moving the date component into the directory column.
"""

import os
import sys
import re
import logging
from pathlib import Path
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import home_media_ai
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.media import Media

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_directory_paths(dry_run=False):
    # Get database URI from env
    database_uri = os.getenv('HOME_MEDIA_AI_URI')
    if not database_uri:
        logger.error("HOME_MEDIA_AI_URI environment variable not set.")
        sys.exit(1)

    logger.info("Connecting to database...")
    engine = create_engine(database_uri)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Regex to match YYYY-MM-DD at start of filename
    date_pattern = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')

    try:
        # Query media with empty or NULL directory
        # Also could check for storage_root containing the date pattern if needed,
        # but starting with empty directory is safer.
        query = session.query(Media).filter(
            or_(Media.directory.is_(None), Media.directory == '')
        )
        
        media_items = query.all()
        logger.info(f"Found {len(media_items)} media items with missing directory.")

        updates_count = 0
        
        for media in media_items:
            match = date_pattern.match(media.filename)
            if not match:
                continue

            year, month, day = match.groups()
            
            # Construct path components
            # We want directory to be "YYYY/MM/DD"
            target_directory = f"{year}/{month}/{day}"
            
            # The storage_root might use backslashes (Windows) or forward slashes
            current_root = media.storage_root
            if not current_root:
                continue
                
            # Create variations of the date path to check against storage_root end
            # e.g. "2025/12/01", "2025\12\01"
            date_suffix_fwd = f"{year}/{month}/{day}"
            date_suffix_back = f"{year}\\{month}\\{day}"
            
            new_root = None
            
            # Check if storage_root ends with the date path
            if current_root.endswith(date_suffix_back):
                # Strip suffix (plus preceding slash if present)
                new_root = current_root[:-len(date_suffix_back)]
            elif current_root.endswith(date_suffix_fwd):
                new_root = current_root[:-len(date_suffix_fwd)]
            
            if new_root:
                # Clean up trailing slashes on new_root
                new_root = new_root.rstrip('/\\')
                
                # If new_root becomes empty, it implies the original root was JUST the date path.
                # In that case, we probably shouldn't clear it entirely unless we want relative paths.
                # But usually there's a drive letter or share name.
                
                if not new_root and ':' not in current_root and not current_root.startswith('\\'):
                     # If it was a relative path, maybe okay. 
                     # But let's be careful. If it's empty, we might lose the mount point.
                     pass

                if dry_run:
                    logger.info(f"[DRY RUN] Would update: {media.filename}")
                    logger.info(f"  Old Root: {current_root}")
                    logger.info(f"  New Root: {new_root}")
                    logger.info(f"  New Dir:  {target_directory}")
                else:
                    media.storage_root = new_root
                    media.directory = target_directory
                    updates_count += 1

        if not dry_run:
            session.commit()
            logger.info(f"Successfully updated {updates_count} media records.")
        else:
            logger.info(f"Dry run complete. Found {updates_count} candidates for update.")

    except Exception as e:
        session.rollback()
        logger.error(f"Error updating records: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fix directory paths based on filename dates")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without saving")
    args = parser.parse_args()
    
    fix_directory_paths(dry_run=args.dry_run)
