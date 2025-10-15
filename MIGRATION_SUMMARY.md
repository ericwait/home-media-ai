# Database Schema Migration Summary: File Path Components

## Overview

This document summarizes the migration from a single `file_path` column to a component-based file path system using `storage_root`, `directory`, and `filename` columns.

## Migration Purpose

The new schema splits file paths into logical components to:
1. **Improve portability** - Files can be remapped when storage locations change
2. **Enable better querying** - Search by directory structure or filename patterns
3. **Support multiple storage roots** - Different mount points for different systems
4. **Simplify path reconstruction** - Build full paths as needed without string parsing

## Schema Changes

### Old Schema
```sql
file_path TEXT NOT NULL UNIQUE
```

### New Schema
```sql
storage_root VARCHAR(500)     -- Mount point (e.g., /volume1/photos)
directory VARCHAR(500)         -- Path from root (e.g., 2024/January)
filename VARCHAR(255) NOT NULL -- Just filename (e.g., IMG_001.CR2)
file_path TEXT                 -- DEPRECATED - kept temporarily for migration
```

### Example Transformation

**Old:** `/volume1/photos/2024/January/IMG_001.CR2`

**New:**
- `storage_root`: `/volume1/photos`
- `directory`: `2024/January`
- `filename`: `IMG_001.CR2`

## Files Updated

### 1. Database Schema
- **[src/sql/02_create_media.sql](src/sql/02_create_media.sql#L30-L57)** ✅
  - Added `storage_root`, `directory`, `filename` columns
  - Marked `file_path` as deprecated
  - Added indexes on new columns

### 2. Documentation
- **[doc/database_schema.md](doc/database_schema.md#L59-L97)** ✅
  - Updated media table documentation
  - Added path reconstruction examples
  - Documented EXIF metadata columns

- **[doc/database_schema.mmd](doc/database_schema.mmd#L23-L48)** ✅
  - Updated Mermaid diagram with new schema

### 3. Python ORM Model
- **[src/python/home_media_ai/media.py](src/python/home_media_ai/media.py#L27-L104)** ✅
  - Added `storage_root`, `directory`, `filename` columns to Media class
  - Marked `file_path` as deprecated (nullable)
  - Added `get_full_path()` helper method to reconstruct paths

### 4. Data Import/Export
- **[src/python/home_media_ai/importer.py](src/python/home_media_ai/importer.py)** ✅
  - Added `storage_root` parameter to `MediaImporter.__init__()`
  - Added `_split_file_path()` method to parse paths into components
  - Updated `_file_exists_in_db()` to check by hash and filename
  - Updated `import_file()` to populate new columns
  - Updated `bulk_import_files()` to populate new columns
  - Still populates `file_path` for backwards compatibility

### 5. Query Helpers
- **[src/python/home_media_ai/media_query.py](src/python/home_media_ai/media_query.py#L548-L591)** ✅
  - Updated `to_dataframe()` default columns to include new schema
  - Added backwards compatibility for `file_path` column requests
  - Updated `to_paths()` to use `get_full_path()` method

### 6. Scripts
- **[src/python/scripts/validate_metadata.py](src/python/scripts/validate_metadata.py#L93-L113)** ✅
  - Updated `validate_file()` to use `media.get_full_path()`
  - Updated display code to use `media.filename` instead of parsing path

- **[src/python/scripts/media_dashboard.py](src/python/scripts/media_dashboard.py)** ✅
  - Updated SQL queries to SELECT new columns: lines [190-205](src/python/scripts/media_dashboard.py#L190-L205), [228-243](src/python/scripts/media_dashboard.py#L228-L243)
  - Updated `create_image_gallery_html()` to construct paths from components: [line 97](src/python/scripts/media_dashboard.py#L97)
  - Updated docstring to reflect new column names

### 7. SQL Query Examples
- **[src/sql/05_useful_queries.sql](src/sql/05_useful_queries.sql)** ✅
  - Updated all queries to use `CONCAT(storage_root, '/', directory, '/', filename)`
  - Lines updated: [69-78](src/sql/05_useful_queries.sql#L69-L78), [81-88](src/sql/05_useful_queries.sql#L81-L88), [112-122](src/sql/05_useful_queries.sql#L112-L122), [125-134](src/sql/05_useful_queries.sql#L125-L134)

## Migration Strategy

### Phase 1: Schema Update (Current)
- ✅ Add new columns to database schema
- ✅ Update all application code to use new columns
- ✅ Keep `file_path` column populated for backwards compatibility

### Phase 2: Data Migration (Next Steps)
1. Create migration script to populate new columns from existing `file_path` data
2. Run migration on existing database records
3. Verify all records have been migrated correctly

### Phase 3: Cleanup (Future)
1. Remove `file_path` column from schema
2. Remove backwards compatibility code
3. Update any remaining references

## Code Usage Examples

### Creating a MediaImporter with Storage Root
```python
from home_media_ai.importer import MediaImporter

# Specify storage root for proper path splitting
importer = MediaImporter(
    database_uri="mariadb+mariadbconnector://user:pass@host/db",
    storage_root="/volume1/photos"
)

# Import files - paths will be automatically split
for file_info in scanner.scan_files():
    media, created = importer.import_file(file_info)
```

### Reconstructing Full Paths
```python
from home_media_ai.media_query import MediaQuery

query = MediaQuery(session)
results = query.rating(5).all()

for media in results:
    # Use helper method to get full path
    full_path = media.get_full_path()
    print(f"File: {full_path}")
    print(f"  Root: {media.storage_root}")
    print(f"  Dir: {media.directory}")
    print(f"  Name: {media.filename}")
```

### SQL Queries
```sql
-- Reconstruct full path in query
SELECT
    CONCAT(storage_root, '/', directory, '/', filename) AS full_path,
    file_hash,
    rating
FROM media
WHERE storage_root = '/volume1/photos'
  AND directory LIKE '2024/%';
```

## Backwards Compatibility

All code maintains backwards compatibility by:
1. Keeping the `file_path` column (marked as deprecated)
2. Populating both old and new columns during import
3. Supporting `file_path` in DataFrame column requests
4. Providing `get_full_path()` helper method

## Web Application

The web service ([src/web/app.py](src/web/app.py)) was already using the new schema:
- Lines [350-362](src/web/app.py#L350-L362): Queries `storage_root`, `directory`, `filename`
- Line [369](src/web/app.py#L369): Reconstructs path using Path concatenation

No updates needed for the web service.

## Testing Checklist

Before completing migration, verify:
- [ ] Database schema updated successfully
- [ ] All existing code runs without errors
- [ ] New imports populate all three path components
- [ ] Queries return correct file paths
- [ ] Web service displays images correctly
- [ ] Dashboard generates thumbnails successfully
- [ ] Validation script finds files correctly

## Key Changes Summary

| File | Changes | Lines |
|------|---------|-------|
| 02_create_media.sql | Added new columns, indexes | 32-56 |
| database_schema.md | Updated documentation | 59-97 |
| database_schema.mmd | Updated diagram | 23-48 |
| media.py | Added columns, get_full_path() | 27-104 |
| importer.py | Path splitting logic | 16-28, 44-68, 110-153, 219-255 |
| media_query.py | Updated DataFrame/paths | 562-591 |
| validate_metadata.py | Use get_full_path() | 93-113, 191, 199, 219 |
| media_dashboard.py | Updated queries, path building | 77-98, 190-243 |
| 05_useful_queries.sql | Updated all queries | 69-134 |

## Notes

1. **NULL handling:** The new columns are nullable to support gradual migration
2. **Uniqueness:** The `file_hash` column remains the primary uniqueness constraint
3. **Performance:** Added indexes on `storage_root` and `filename` for efficient querying
4. **Path separator:** Uses `/` for consistency across platforms (Path handles conversion)

## Configuration System (NEW)

A flexible configuration system has been added to enable cross-platform path mapping:

### Key Features
- **Storage Root Mapping** - Map database `storage_root` values to local mount points
- **Multiple Strategies** - Mapped, database, or local-only path resolution
- **Environment Variables** - Override config with `HOME_MEDIA_AI_URI`, `PHOTO_ROOT`, etc.
- **Backwards Compatible** - Works without configuration file

### New Files
- **[src/python/home_media_ai/config.py](src/python/home_media_ai/config.py)** - Configuration loader and PathResolver
- **[config.example.yaml](config.example.yaml)** - Template with all options
- **[config.synology.yaml](config.synology.yaml)** - For Synology NAS
- **[config.dev.yaml](config.dev.yaml)** - For development machines
- **[config.docker.yaml](config.docker.yaml)** - For Docker containers
- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** - Complete configuration guide
- **[requirements.txt](requirements.txt)** - Added PyYAML dependency

### Usage
```python
# Media objects automatically use path resolver
media.get_full_path()  # Resolves to local path using config.yaml mappings

# Manual path resolution
from home_media_ai.config import get_path_resolver
resolver = get_path_resolver()
local_path = resolver.resolve_path(storage_root, directory, filename)

# MediaImporter uses config automatically
importer = MediaImporter(database_uri)  # Reads storage_root from config
```

### Example Configuration
```yaml
# config.yaml
storage_roots:
  "/volume1/photos": "/mnt/nas/photos"  # Map NAS path to local mount

database:
  uri: "mariadb+mariadbconnector://user:pass@host/db"

scanning:
  storage_root: "/volume1/photos"  # Path to store in database
```

See **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** for complete guide with examples.

## Next Steps

1. **Create migration script** to parse existing `file_path` values into components
2. **Configure path mappings** for your environment:
   - Copy appropriate `config.*.yaml` to `config.yaml`
   - Set storage_roots for your local mounts
3. **Test with sample data** before running on production database
4. **Backup database** before running migration
5. **Deploy configuration** to all systems accessing the database
6. **Monitor application** for any edge cases after deployment
