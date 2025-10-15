# Configuration Guide

Home Media AI uses a flexible configuration system that allows different machines to access the same database with different local file paths. This is essential for cross-platform compatibility.

## Quick Start

1. **Copy example configuration:**
   ```bash
   # For Synology NAS
   cp config.synology.yaml config.yaml

   # For development machine
   cp config.dev.yaml config.yaml

   # For Docker container
   cp config.docker.yaml config.yaml
   ```

2. **Edit `config.yaml`** to match your environment

3. **Set environment variables** (optional, overrides config file):
   ```bash
   export HOME_MEDIA_AI_URI="mariadb+mariadbconnector://user:pass@host/db"
   export PHOTO_ROOT="/mnt/media"
   ```

## Configuration File Locations

The system searches for `config.yaml` in the following locations (in order):

1. Current working directory: `./config.yaml`
2. Project root: `<project_root>/config.yaml`
3. User config directory: `~/.config/home-media-ai/config.yaml`

## Configuration Sections

### Storage Root Mappings

The core feature that enables cross-platform compatibility. Maps database `storage_root` values to local filesystem paths.

```yaml
storage_roots:
  # Database path -> Local mount point
  "/volume1/photos": "/mnt/nas/photos"   # Example: NAS mapped to local mount
  "/volume1/photo/RAW": "/Volumes/NAS"   # Example: macOS mount
```

**How it works:**
- Files are stored in the database with their original `storage_root` (e.g., `/volume1/photos`)
- On your local machine, you map that path to where you actually mount the files
- The `PathResolver` automatically translates paths when accessing files

### Path Resolution Strategy

Controls how paths are resolved when accessing files:

```yaml
path_resolution:
  strategy: "mapped"  # Options: "mapped", "database", "local_only"
  validate_exists: false
  normalize_separators: true
```

**Strategies:**
- **`mapped`** (recommended): Try mapped path first, fall back to database path if not found
- **`database`**: Always use database paths as-is (useful on the NAS itself)
- **`local_only`**: Only use mapped paths, fail if no mapping exists (strict mode)

**Settings:**
- `validate_exists`: Check if resolved path exists before returning (slower but safer)
- `normalize_separators`: Convert path separators to OS-native format (`/` or `\`)

### Database Connection

```yaml
database:
  uri: "mariadb+mariadbconnector://user:password@host:3306/home_media_ai"
```

You can also use environment variable substitution:
```yaml
database:
  uri: "${HOME_MEDIA_AI_URI}"
```

### Scanning Settings

Used when importing new files into the database:

```yaml
scanning:
  storage_root: "/volume1/photos"  # Root path to store in database
  batch_size: 100                  # Number of files to process in each batch
```

**Important:** The `storage_root` here is what gets **stored in the database**. This should be the canonical path that other machines will map to their local paths.

### Web Service Settings

```yaml
web:
  port: 5100
  host: "0.0.0.0"
  media_root: "/mnt/media"  # Local path where web service finds files
```

## Environment Variables

Environment variables override config file settings:

| Variable | Description | Example |
|----------|-------------|---------|
| `HOME_MEDIA_AI_URI` | Database connection string | `mariadb+mariadbconnector://...` |
| `PHOTO_ROOT` | Web service media root | `/mnt/media` |
| `STORAGE_ROOT` | Scanning storage root | `/volume1/photos` |

## Usage Examples

### Example 1: Development Machine

**Scenario:** You're developing on macOS, accessing a Synology NAS database.

**config.yaml:**
```yaml
storage_roots:
  "/volume1/photos": "/Users/you/mnt/nas"

database:
  uri: "mariadb+mariadbconnector://user:pass@nas.local:3306/home_media_ai"

scanning:
  storage_root: "/Users/you/Photos"  # For local imports
```

**How it works:**
- Files in database with `storage_root="/volume1/photos"` are accessed via `/Users/you/mnt/nas`
- When you import files from `/Users/you/Photos`, that path is stored in the database
- Other machines will need to map `/Users/you/Photos` to their local mount

### Example 2: Synology NAS

**Scenario:** Running directly on the NAS where files are stored.

**config.yaml:**
```yaml
storage_roots:
  "/volume1/photos": "/volume1/photos"  # Identity mapping

path_resolution:
  strategy: "database"  # Use database paths directly

database:
  uri: "mariadb+mariadbconnector://user:pass@localhost:3306/home_media_ai"

scanning:
  storage_root: "/volume1/photos"
```

### Example 3: Docker Container

**Scenario:** Web service running in Docker with volume mount.

**docker-compose.yml:**
```yaml
services:
  web:
    volumes:
      - /volume1/photos:/mnt/media:ro
    environment:
      - HOME_MEDIA_AI_URI=mariadb+mariadbconnector://...
```

**config.yaml:**
```yaml
storage_roots:
  "/volume1/photos": "/mnt/media"  # Map NAS path to container mount

web:
  media_root: "/mnt/media"
```

### Example 4: Multiple Storage Roots

**Scenario:** Files spread across multiple volumes.

**config.yaml:**
```yaml
storage_roots:
  "/volume1/photos": "/mnt/volume1"
  "/volume2/backup": "/mnt/volume2"
  "/external/drive": "/Volumes/External"

default_storage_root: "/mnt/volume1"  # Used when no mapping matches
```

## Python API

### Using Configuration in Code

```python
from home_media_ai.config import get_config, get_path_resolver

# Get global configuration
config = get_config()
print(config.storage_roots)

# Get path resolver
resolver = get_path_resolver()

# Resolve a path
local_path = resolver.resolve_path(
    storage_root="/volume1/photos",
    directory="2024/January",
    filename="IMG_001.CR2"
)
print(local_path)  # Resolves to your local mount
```

### Using Media.get_full_path()

```python
from home_media_ai.media_query import MediaQuery

query = MediaQuery(session)
results = query.rating(5).all()

for media in results:
    # Automatically uses path resolver
    local_path = media.get_full_path()
    print(local_path)

    # Or get database path without mapping
    db_path = media.get_full_path(use_local_mapping=False)
```

### Custom Configuration

```python
from home_media_ai.config import Config, PathResolver, set_config

# Create custom configuration
config = Config()
config.storage_roots = {
    "/volume1/photos": "/my/custom/mount"
}

# Set as global configuration
set_config(config)

# Now all Media.get_full_path() calls will use this config
```

### MediaImporter with Configuration

```python
from home_media_ai.importer import MediaImporter

# Uses config.yaml automatically
importer = MediaImporter(database_uri)

# Or override with explicit storage_root
importer = MediaImporter(database_uri, storage_root="/custom/path")

# Or disable config entirely
importer = MediaImporter(database_uri, use_config=False)
```

## Web Service Configuration

The web service ([src/web/app.py](../src/web/app.py)) automatically loads configuration on startup.

**Priority:**
1. Configuration file (`config.yaml`)
2. Environment variables (`PHOTO_ROOT`, `HOME_MEDIA_AI_URI`)
3. Default values

**Logs:**
```
INFO - Path resolver loaded with mappings: {'/volume1/photos': '/mnt/media'}
```

Or if config not available:
```
WARNING - Path resolver not available, using simple path construction
```

## Troubleshooting

### Files Not Found

**Problem:** `FileNotFoundError` when accessing media files

**Solutions:**
1. Check your `storage_roots` mappings in `config.yaml`
2. Verify local mount points exist: `ls /mnt/media`
3. Check database `storage_root` values: `SELECT DISTINCT storage_root FROM media;`
4. Enable path validation: `validate_exists: true` in config

### Wrong Paths in Database

**Problem:** Paths in database don't match expected storage roots

**Solution:**
When importing, ensure `scanning.storage_root` is set correctly:
```yaml
scanning:
  storage_root: "/volume1/photos"  # This goes into the database
```

### Configuration Not Loading

**Problem:** Application not finding `config.yaml`

**Solutions:**
1. Check file location: `./config.yaml`, `<project_root>/config.yaml`, or `~/.config/home-media-ai/config.yaml`
2. Verify YAML syntax: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
3. Use environment variables as override
4. Check logs for "Path resolver not available" message

### Docker Container Issues

**Problem:** Container can't access files

**Solutions:**
1. Verify volume mount in `docker-compose.yml`:
   ```yaml
   volumes:
     - /volume1/photos:/mnt/media:ro
   ```
2. Check `storage_roots` mapping in `config.yaml`:
   ```yaml
   storage_roots:
     "/volume1/photos": "/mnt/media"
   ```
3. Ensure `media_root` matches container mount:
   ```yaml
   web:
     media_root: "/mnt/media"
   ```

## Best Practices

1. **Use Canonical Paths in Database:**
   - Store stable, canonical paths in the database (e.g., `/volume1/photos`)
   - Map these to local mounts in each environment's `config.yaml`

2. **Version Control:**
   - Add `config.yaml` to `.gitignore`
   - Commit `config.example.yaml`, `config.dev.yaml`, etc.
   - Each developer maintains their own `config.yaml`

3. **Environment-Specific Configs:**
   - Keep separate config files: `config.synology.yaml`, `config.dev.yaml`
   - Copy appropriate one to `config.yaml` for your environment

4. **Docker Deployments:**
   - Use environment variables for sensitive data
   - Mount `config.yaml` as a volume
   - Or use `config.docker.yaml` with volume mounts

5. **Testing Path Resolution:**
   ```python
   from home_media_ai.config import get_path_resolver

   resolver = get_path_resolver()

   # Test your mappings
   test_cases = [
       ("/volume1/photos", "2024", "test.jpg"),
       ("/volume2/backup", None, "backup.jpg"),
   ]

   for storage, directory, filename in test_cases:
       resolved = resolver.resolve_path(storage, directory, filename)
       print(f"{storage}/{directory}/{filename} -> {resolved}")
       print(f"  Exists: {resolved.exists()}")
   ```

## Migration from Old System

If you're migrating from the old single-path system:

1. **No configuration needed initially** - system works without `config.yaml`
2. **Create config when needed** for cross-platform access
3. **Existing code continues to work** - configuration is opt-in
4. **Gradual adoption** - add mappings as you work on different machines

## Advanced: Multiple Database Environments

```yaml
# config.production.yaml
database:
  uri: "mariadb+mariadbconnector://user:pass@prod-nas:3306/home_media_ai"

# config.staging.yaml
database:
  uri: "mariadb+mariadbconnector://user:pass@staging-nas:3306/home_media_ai"
```

Load specific config:
```python
from home_media_ai.config import Config

config = Config.load("config.production.yaml")
```

## See Also

- [Migration Summary](../MIGRATION_SUMMARY.md) - Overview of path component changes
- [Web Service README](../src/web/README.md) - Docker deployment guide
- [Database Schema](database_schema.md) - Table structure details
