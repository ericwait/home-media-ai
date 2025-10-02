#!/usr/bin/env python3
"""
Database Setup and Migration Script

Executes SQL scripts in order to create the normalized schema
and optionally migrate existing data.
"""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Resolve paths
SCRIPT_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = SCRIPT_DIR.parent / "sql"

# SQL scripts in execution order
SQL_SCRIPTS = [
    "01_create_taxonomies.sql",
    "02_create_media.sql",
    "03_create_linking.sql",
    "06_add_exif_columns.sql",
]

MIGRATION_SCRIPT = "04_migrate_existing_data.sql"


def get_engine():
    """Get database engine from environment variable."""
    db_uri = os.getenv("HOME_MEDIA_AI_URI")
    if not db_uri:
        raise ValueError(
            "HOME_MEDIA_AI_URI environment variable not set.\n"
            "Example: export HOME_MEDIA_AI_URI='mariadb+mariadbconnector://user:pass@host:port/dbname'"
        )
    return create_engine(db_uri)


def execute_sql_file(engine, sql_file):
    """
    Execute a SQL file statement by statement.
    
    Splits on semicolons and executes each statement separately
    to handle multi-statement files properly.
    """
    file_path = SQL_DIR / sql_file
    if not file_path.exists():
        raise FileNotFoundError(f"SQL script not found: {file_path}")
    
    print(f"\n{'='*60}")
    print(f"Executing: {sql_file}")
    print('='*60)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Remove comments first, then split on semicolons
    lines = []
    in_block_comment = False
    
    for line in sql_content.split('\n'):
        # Handle block comments
        if '/*' in line:
            in_block_comment = True
        if '*/' in line:
            in_block_comment = False
            continue
        if in_block_comment:
            continue
            
        # Remove inline comments
        if '--' in line:
            line = line[:line.index('--')]
        
        # Keep non-empty lines
        if line.strip():
            lines.append(line)
    
    cleaned_content = '\n'.join(lines)
    
    # Now split on semicolons and filter
    statements = []
    for stmt in cleaned_content.split(';'):
        cleaned = stmt.strip()
        
        # Only add if it's actually SQL (starts with common keywords)
        if cleaned and any(cleaned.upper().startswith(kw) for kw in 
                          ['CREATE', 'ALTER', 'INSERT', 'UPDATE', 'DELETE', 
                           'DROP', 'SELECT', 'WITH', 'SET']):
            statements.append(cleaned)
    
    with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                result = conn.execute(text(stmt))
                # If it's a SELECT, print results
                if stmt.strip().upper().startswith('SELECT') or stmt.strip().upper().startswith('WITH'):
                    rows = result.fetchall()
                    if rows:
                        print(f"\nStatement {i} results:")
                        for row in rows:
                            print(f"  {dict(row)}")
                else:
                    print(f"✓ Statement {i} executed successfully")
            except Exception as e:
                print(f"✗ Statement {i} failed: {e}")
                print(f"  Statement preview: {stmt[:200]}...")
                raise
    
    print(f"✓ {sql_file} completed successfully\n")


def check_existing_tables(engine):
    """Check if old schema tables exist."""
    check_sql = """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME IN ('wfo_versions', 'plant_taxonomy', 'plant_images')
    """
    with engine.begin() as conn:
        result = conn.execute(text(check_sql))
        return [row[0] for row in result]


def nuclear_option(engine):
    """
    Drop ALL tables in the database.
    
    WARNING: This is destructive and cannot be undone!
    """
    print("\n" + "="*60)
    print("⚠️  NUCLEAR OPTION - DROP ALL TABLES")
    print("="*60)
    print("\n⚠️  WARNING: This will DELETE ALL TABLES and DATA!")
    print("This action CANNOT be undone.\n")
    
    response = input("Type 'DELETE EVERYTHING' to confirm: ")
    if response != 'DELETE EVERYTHING':
        print("Aborted. No changes made.")
        return False
    
    print("\n🔥 Dropping all tables...")
    
    # Get all tables
    get_tables_sql = """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
        ORDER BY TABLE_NAME
    """
    
    with engine.begin() as conn:
        result = conn.execute(text(get_tables_sql))
        tables = [row[0] for row in result]
        
        if not tables:
            print("No tables found. Database is already empty.")
            return True
        
        print(f"Found {len(tables)} tables to drop:")
        for table in tables:
            print(f"  - {table}")
        
        # Disable foreign key checks temporarily
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        # Drop each table
        for table in tables:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                print(f"✓ Dropped {table}")
            except Exception as e:
                print(f"✗ Failed to drop {table}: {e}")
        
        # Re-enable foreign key checks
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    
    print("\n✓ All tables dropped successfully")
    return True


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Home Media AI Database Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_database.py              # Normal setup
  python setup_database.py --nuclear    # Drop all tables and start fresh
        """
    )
    parser.add_argument(
        '--nuclear',
        action='store_true',
        help='Drop ALL tables and start fresh (requires confirmation)'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("Home Media AI - Database Setup")
    print("="*60)

    # Get engine
    try:
        engine = get_engine()
        print(f"✓ Connected to database: {engine.url.database}")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)

    # Handle nuclear option
    if args.nuclear:
        if not nuclear_option(engine):
            sys.exit(0)
        print("\nProceeding with fresh setup...\n")

    # Check for existing tables
    existing_tables = check_existing_tables(engine)
    if existing_tables:
        print(f"\n⚠  Found existing tables: {', '.join(existing_tables)}")
        print("These will be migrated after creating the new schema.")

    # Execute core schema scripts
    try:
        for script in SQL_SCRIPTS:
            execute_sql_file(engine, script)
        print("✓ Core schema created successfully")
    except Exception as e:
        print(f"\n✗ Schema creation failed: {e}")
        sys.exit(1)

    # Optionally run migration
    if existing_tables:
        response = input(f"\nRun migration script to import existing data? (y/n): ")
        if response.lower() == 'y':
            try:
                execute_sql_file(engine, MIGRATION_SCRIPT)
                print("✓ Migration completed successfully")
            except Exception as e:
                print(f"\n✗ Migration failed: {e}")
                print("You may need to manually review and fix data inconsistencies.")
                sys.exit(1)

    print("\n" + "="*60)
    print("Database setup complete!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Run: python src/python/import_flora_wfo_data.py")
    print("  2. Check: src/sql/05_useful_queries.sql for exploration")
    print("="*60)


if __name__ == "__main__":
    main()