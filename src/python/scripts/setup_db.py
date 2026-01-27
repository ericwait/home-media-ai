"""
Database setup script.
Creates databases and tables based on configuration.

Usage:
    python src/python/scripts/setup_db.py
"""
import asyncio
import logging
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from home_media.config import load_config, get_db_config
from home_media.db.models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_db_identifier(name: str) -> None:
    """
    Validate that a database name is a safe PostgreSQL identifier.
    
    Args:
        name: Database name to validate
        
    Raises:
        ValueError: If the name contains invalid characters
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
        raise ValueError(
            f"Invalid database name '{name}'. Must start with a letter or underscore "
            "and contain only letters, numbers, and underscores."
        )

async def create_database_if_not_exists(user, password, host, port, db_name):
    """Create the database if it doesn't exist using asyncpg."""
    import asyncpg
    
    # Validate database name to prevent SQL injection
    validate_db_identifier(db_name)

    # Connect to the default 'postgres' database to perform administrative tasks
    sys_conn = await asyncpg.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database='postgres',
        timeout=30
    )

    try:
        # Check if db exists
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            logger.info(f"Creating database: {db_name}")
            await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
        else:
            logger.info(f"Database {db_name} already exists.")

    except Exception as e:
        logger.error(f"Error creating database {db_name}: {e}")
        raise
    finally:
        await sys_conn.close()

async def init_schema(user, password, host, port, db_name):
    """Initialize schema and extensions for a specific database."""
    # URL-encode credentials to handle special characters
    encoded_user = quote_plus(user)
    encoded_password = quote_plus(password)
    url = f"postgresql+asyncpg://{encoded_user}:{encoded_password}@{host}:{port}/{db_name}"

    logger.info(f"Initializing schema for {db_name}...")
    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
        # Enable Extensions
        logger.info("Enabling extensions (vector, ltree)...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS ltree;"))

        # Create Tables
        logger.info("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    logger.info(f"Schema initialization for {db_name} complete.")

async def main():
    try:
        config = load_config()
        db_config = get_db_config(config)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        logger.error("Please ensure config.yaml exists and has a 'database' section.")
        return

    user = db_config['user']
    password = db_config['password']
    host = db_config['host']
    port = db_config['port']

    prod_db = db_config.get('name_prod', 'home_media_prod')
    dev_db = db_config.get('name_dev', 'home_media_dev')

    databases = [prod_db, dev_db]

    for db_name in databases:
        logger.info(f"--- Setting up {db_name} ---")
        try:
            await create_database_if_not_exists(user, password, host, port, db_name)
            await init_schema(user, password, host, port, db_name)
        except Exception as e:
            logger.error(f"Failed to setup {db_name}: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
