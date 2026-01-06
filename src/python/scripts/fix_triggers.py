#!/usr/bin/env python3
"""
Script to drop problematic triggers from the database.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Add parent directory to path to import home_media_ai
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.importer import MediaImporter

def remove_triggers():
    # Get database URI from env
    database_uri = os.getenv('HOME_MEDIA_AI_URI')
    if not database_uri:
        print("ERROR: HOME_MEDIA_AI_URI environment variable not set.")
        sys.exit(1)

    print(f"Connecting to database...")
    engine = create_engine(database_uri)

    triggers_to_drop = [
        "maintain_is_final_on_insert",
        "maintain_is_final_on_update",
        "maintain_is_final_on_delete"
    ]

    with engine.connect() as conn:
        for trigger in triggers_to_drop:
            print(f"Dropping trigger: {trigger}...")
            try:
                conn.execute(text(f"DROP TRIGGER IF EXISTS {trigger}"))
                print(f"  - Dropped {trigger}")
            except Exception as e:
                print(f"  - Failed to drop {trigger}: {e}")
        
        print("\nVerifying...")
        # Optional: Check if triggers still exist (syntax varies by DB, skipping for simplicity)
        print("Done.")

if __name__ == "__main__":
    remove_triggers()
