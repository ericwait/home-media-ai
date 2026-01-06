#!/usr/bin/env python3
"""
Script to refresh the is_final status of all media items in the database.
This replaces the functionality of the triggers that were removed for performance/compatibility.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Add parent directory to path to import home_media_ai
sys.path.insert(0, str(Path(__file__).parent.parent))

def refresh_final_status():
    # Get database URI from env
    database_uri = os.getenv('HOME_MEDIA_AI_URI')
    if not database_uri:
        print("ERROR: HOME_MEDIA_AI_URI environment variable not set.")
        sys.exit(1)

    print(f"Connecting to database...")
    engine = create_engine(database_uri)

    print("Refreshing 'is_final' status (this may take a moment for large databases)...")
    try:
        with engine.begin() as conn:
            conn.execute(text("CALL update_is_final()"))
        print("Success: Final status refreshed.")
    except Exception as e:
        print(f"ERROR: Failed to refresh status: {e}")
        print("\nNote: Ensure the 'update_is_final' procedure exists by running src/sql/07_add_is_final_column.sql")

if __name__ == "__main__":
    refresh_final_status()
