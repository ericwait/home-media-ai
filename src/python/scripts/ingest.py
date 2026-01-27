"""
Ingestion script for HomeMedia AI.

Scans the photos directory and populates the PostgreSQL database.
Recommended to run this on the Server (Mac) for performance.

Usage:
    python src/python/scripts/ingest.py [--dry-run] [--full-scan]
"""
import asyncio
import logging
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Add src/python to path to allow imports
sys.path.append(str(Path(__file__).parents[2]))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from home_media.config import load_config, get_photos_root, get_db_config
from home_media.scanner.directory import _collect_files
from home_media.scanner.grouper import group_files_to_images
from home_media.models.image import Image as DomainImage
from home_media.db.models import ImageModel, ImageFileModel, FileFormat, FileRole

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ingest")

BATCH_SIZE = 100

async def ingest_batch(session: AsyncSession, images: List[DomainImage]):
    """
    Ingest a batch of images and their files into the database.
    Uses ON CONFLICT DO UPDATE to handle existing records.
    """
    if not images:
        return

    # 1. Prepare Image Records
    image_records = []
    for img in images:
        rec = {
            "base_name": img.base_name,
            "subdirectory": img.subdirectory,
            "captured_at": img.captured_at,
            "created_at": img.created_at,
            "updated_at": img.updated_at,
            "camera_make": img.camera_make,
            "camera_model": img.camera_model,
            "lens": img.lens,
            "gps_latitude": img.gps_latitude,
            "gps_longitude": img.gps_longitude,
            "title": img.title,
            "description": img.description,
            "rating": img.rating,
        }
        image_records.append(rec)

    # 2. Insert/Upsert Images and get IDs
    # We use (base_name, subdirectory) as unique key
    stmt = pg_insert(ImageModel).values(image_records)
    
    # Define update columns (everything except PK and identity)
    update_dict = {
        col.name: col for col in stmt.excluded 
        if col.name not in ('id', 'base_name', 'subdirectory', 'created_at')
    }
    
    stmt = stmt.on_conflict_do_update(
        constraint='uq_image_identity',
        set_=update_dict
    ).returning(ImageModel.id, ImageModel.base_name, ImageModel.subdirectory)

    result = await session.execute(stmt)
    
    # Map (base_name, subdirectory) -> database_id
    id_map = {}
    for row in result:
        # row is (id, base_name, subdirectory)
        key = (row.base_name, row.subdirectory)
        id_map[key] = row.id

    # 3. Prepare File Records
    file_records = []
    for img in images:
        img_id = id_map.get((img.base_name, img.subdirectory))
        if not img_id:
            logger.warning(f"Could not find ID for image {img.base_name}")
            continue
            
        for f in img.files:
            file_rec = {
                "image_id": img_id,
                "file_path": str(f.file_path),
                "filename": f.filename,
                "extension": f.extension,
                "role": f.role,
                "format": f.format,
                "file_size_bytes": f.file_size_bytes,
                "width": f.width,
                "height": f.height,
                "file_hash": f.file_hash,
            }
            file_records.append(file_rec)

    if not file_records:
        return

    # 4. Insert/Upsert Files
    # We use file_path as unique key (implied by unique index or requirement)
    # Actually ImageFileModel has file_path: Mapped[str] = mapped_column(String, unique=True)
    
    file_stmt = pg_insert(ImageFileModel).values(file_records)
    
    file_update_dict = {
        col.name: col for col in file_stmt.excluded 
        if col.name not in ('id', 'file_path', 'image_id')
    }
    
    file_stmt = file_stmt.on_conflict_do_update(
        index_elements=['file_path'], # Use the unique column name
        set_=file_update_dict
    )

    await session.execute(file_stmt)


async def main():
    parser = argparse.ArgumentParser(description="Ingest photos into database")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, do not write to DB")
    parser.add_argument("--extract-exif", action="store_true", help="Extract EXIF metadata (slower)")
    parser.add_argument("--extract-dims", action="store_true", help="Extract dimensions (slower)")
    parser.add_argument("--calc-hash", action="store_true", help="Calculate file hash (very slow)")
    parser.add_argument("--db", default="dev", choices=["dev", "prod"], help="Target database")
    
    args = parser.parse_args()

    try:
        config = load_config()
        photos_root = get_photos_root(config)
        db_config_root = get_db_config(config)
    except Exception as e:
        logger.error(f"Config Error: {e}")
        return

    # 1. Scan Directory
    logger.info(f"Scanning directory: {photos_root}")
    if not photos_root.exists():
        logger.error(f"Photos root does not exist: {photos_root}")
        return

    # Use internal scanner logic to get objects directly
    files = _collect_files(photos_root, recursive=True, include_sidecars=True)
    logger.info(f"Found {len(files)} files. Grouping...")
    
    images = group_files_to_images(files, photos_root)
    logger.info(f"Grouped into {len(images)} images.")

    # Optional Metadata Extraction
    if args.extract_exif:
        logger.info("Extracting EXIF metadata...")
        for img in images:
            img.populate_from_exif()
            
    if args.extract_dims or args.calc_hash:
        logger.info("Extracting file metadata...")
        for img in images:
            for f in img.files:
                if args.extract_dims: f.populate_dimensions()
                if args.calc_hash: f.populate_hash()

    if args.dry_run:
        logger.info("Dry run complete. Exiting.")
        return

    # 2. Database Connection
    db_name = db_config_root.get(f'name_{args.db}', 'home_media_dev')
    user = db_config_root['user']
    password = db_config_root['password']
    host = db_config_root['host']
    port = db_config_root['port']
    
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    
    logger.info(f"Connecting to database: {db_name}")
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 3. Ingest Loop
    async with async_session() as session:
        async with session.begin():
            total = len(images)
            for i in range(0, total, BATCH_SIZE):
                batch = images[i : i + BATCH_SIZE]
                logger.info(f"Ingesting batch {i//BATCH_SIZE + 1}/{(total // BATCH_SIZE) + 1} ({len(batch)} images)")
                await ingest_batch(session, batch)
        
        logger.info("Commit successful.")

    await engine.dispose()
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
