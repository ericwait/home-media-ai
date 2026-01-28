from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy import select, func
from typing import List, Optional
import logging

from home_media.config import load_config, get_db_config
from home_media.db.models import ImageModel, ImageFileModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("home_media_api")

app = FastAPI(title="Home Media AI API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Setup
config = load_config()
db_config = get_db_config(config)

# Default to dev database for now
db_name = db_config.get('name_dev', 'home_media_dev')
user = db_config['user']
password = db_config['password']
host = db_config['host']
port = db_config['port']

DATABASE_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/")
async def root():
    return {"message": "Home Media AI API is running"}

@app.get("/images")
async def get_images(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a paginated list of images.
    """
    try:
        # Fetch images with their files eagerly loaded
        stmt = (
            select(ImageModel)
            .options(selectinload(ImageModel.files))
            .offset(offset)
            .limit(limit)
            .order_by(ImageModel.captured_at.desc())
        )
        result = await db.execute(stmt)
        images = result.scalars().all()
        
        # Simple count for total
        count_stmt = select(func.count()).select_from(ImageModel)
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar()

        return {
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "images": [
                {
                    "id": img.id,
                    "base_name": img.base_name,
                    "subdirectory": img.subdirectory,
                    "captured_at": img.captured_at,
                    "camera_make": img.camera_make,
                    "camera_model": img.camera_model,
                    "rating": img.rating,
                    "file_count": len(img.files)
                }
                for img in images
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching images: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/images/{image_id}")
async def get_image_details(
    image_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information for a single image, including all its files.
    """
    stmt = select(ImageModel).options(selectinload(ImageModel.files)).where(ImageModel.id == image_id)
    result = await db.execute(stmt)
    image = result.scalar_one_or_none()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    return {
        "id": image.id,
        "base_name": image.base_name,
        "subdirectory": image.subdirectory,
        "captured_at": image.captured_at,
        "camera_make": image.camera_make,
        "camera_model": image.camera_model,
        "lens": image.lens,
        "rating": image.rating,
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "file_path": f.file_path,
                "extension": f.extension,
                "role": f.role.name,
                "format": f.format.value,
                "width": f.width,
                "height": f.height,
                "file_size_bytes": f.file_size_bytes
            }
            for f in image.files
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
