from home_media_ai.database import get_session
from sqlalchemy import text

def debug_paths():
    with get_session() as session:
        print("Querying first 10 media items with thumbnail_path...")
        result = session.execute(text("""
            SELECT id, storage_root, directory, filename, thumbnail_path
            FROM media
            WHERE thumbnail_path IS NOT NULL
            LIMIT 10
        """))
        
        for row in result:
            print(f"ID: {row[0]}")
            print(f"  Storage Root: {row[1]}")
            print(f"  Directory:    {row[2]}")
            print(f"  Filename:     {row[3]}")
            print(f"  Thumb Path:   {row[4]}")
            print("-" * 40)

if __name__ == "__main__":
    try:
        debug_paths()
    except Exception as e:
        print(f"Error: {e}")
