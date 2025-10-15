# Configuration System Summary

## Problem Solved

The original issue was that each computer/script might mount data somewhere different. The database stores `storage_root` values like `/volume1/photos`, but:
- On a development Mac, this might be mounted at `/Volumes/NAS`
- In a Docker container, it might be `/mnt/media`
- On the NAS itself, it stays as `/volume1/photos`

Without a configuration system, code would fail to find files because it used the database path directly.

## Solution Overview

A flexible configuration system that:
1. **Maps database paths to local paths** via `config.yaml`
2. **Automatically resolves paths** when accessing files
3. **Falls back gracefully** if no mapping exists
4. **Works without configuration** for backwards compatibility

## How It Works

### 1. Storage Root Mapping

In `config.yaml`, you define mappings:

```yaml
storage_roots:
  "/volume1/photos": "/Users/you/mnt/nas"  # Database path -> Local mount
```

### 2. Automatic Path Resolution

When code accesses a file:

```python
# Database has: storage_root="/volume1/photos", directory="2024", filename="IMG.CR2"
path = media.get_full_path()
# Returns: /Users/you/mnt/nas/2024/IMG.CR2 (mapped to local mount)
```

### 3. Resolution Strategies

- **`mapped`**: Try mapping first, fall back to database path
- **`database`**: Always use database path (for NAS itself)
- **`local_only`**: Only use mappings, fail if none exists

## Architecture

```
┌─────────────────┐
│  Database       │
│  storage_root:  │
│  /volume1/photos│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  config.yaml    │
│  Mappings:      │
│  /volume1/photos│
│    -> /mnt/nas  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PathResolver   │
│  Applies        │
│  mappings       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Local Path     │
│  /mnt/nas/2024/ │
│  IMG.CR2        │
└─────────────────┘
```

## Key Components

### 1. Configuration Loader ([src/python/home_media_ai/config.py](src/python/home_media_ai/config.py))

```python
from home_media_ai.config import get_config

config = get_config()  # Automatically loads config.yaml
print(config.storage_roots)  # {'"/volume1/photos": "/mnt/nas"}
```

**Features:**
- Searches multiple locations for `config.yaml`
- Supports environment variable overrides
- Provides dataclass-based configuration structure

### 2. PathResolver

```python
from home_media_ai.config import get_path_resolver

resolver = get_path_resolver()
path = resolver.resolve_path("/volume1/photos", "2024", "IMG.CR2")
# Returns: /mnt/nas/2024/IMG.CR2
```

**Features:**
- Applies storage root mappings
- Handles partial path matches (e.g., `/volume1/photo/RAW` matches `/volume1/photos`)
- Falls back gracefully if no mapping exists
- Normalizes path separators for OS

### 3. Media.get_full_path()

Updated to use PathResolver automatically:

```python
media = session.query(Media).first()
path = media.get_full_path()  # Automatically uses mappings from config.yaml
```

**Behavior:**
- `use_local_mapping=True` (default): Uses PathResolver
- `use_local_mapping=False`: Returns database path directly

### 4. MediaImporter Configuration

```python
# Option 1: Use config.yaml automatically
importer = MediaImporter(database_uri)

# Option 2: Override with explicit storage_root
importer = MediaImporter(database_uri, storage_root="/custom/path")

# Option 3: Disable config
importer = MediaImporter(database_uri, use_config=False)
```

### 5. Web Service Integration

The web service automatically loads configuration on startup:

```python
# src/web/app.py
from home_media_ai.config import PathResolver, Config

config = Config.load()
path_resolver = PathResolver(config)

def resolve_media_path(storage_root, directory, filename):
    return path_resolver.resolve_path(storage_root, directory, filename)
```

## Configuration Files

### Core Configuration
- **[config.example.yaml](config.example.yaml)** - Template with all options documented

### Environment-Specific
- **[config.synology.yaml](config.synology.yaml)** - For Synology NAS (database paths)
- **[config.dev.yaml](config.dev.yaml)** - For development machines (mapped paths)
- **[config.docker.yaml](config.docker.yaml)** - For Docker containers (container mounts)

### Usage Pattern

1. Copy appropriate config: `cp config.dev.yaml config.yaml`
2. Edit for your environment
3. Application automatically uses it

## Environment Variables

Override configuration with environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `HOME_MEDIA_AI_URI` | Database connection | `mariadb+mariadbconnector://...` |
| `PHOTO_ROOT` | Web service media root | `/mnt/media` |
| `STORAGE_ROOT` | Scanning storage root | `/volume1/photos` |

Priority: Environment Variables > config.yaml > Defaults

## Use Cases

### Use Case 1: Development Machine

**Scenario:** Developing on macOS, NAS mounted via SMB

**config.yaml:**
```yaml
storage_roots:
  "/volume1/photos": "/Volumes/NAS-Photos"

database:
  uri: "mariadb+mariadbconnector://user:pass@nas.local:3306/home_media_ai"
```

**Result:** Files stored as `/volume1/photos/2024/IMG.CR2` in database are accessed at `/Volumes/NAS-Photos/2024/IMG.CR2` locally.

### Use Case 2: Docker Container

**docker-compose.yml:**
```yaml
volumes:
  - /volume1/photos:/mnt/media:ro
```

**config.yaml:**
```yaml
storage_roots:
  "/volume1/photos": "/mnt/media"

web:
  media_root: "/mnt/media"
```

**Result:** Database paths automatically mapped to container mount.

### Use Case 3: Multiple Storage Volumes

**config.yaml:**
```yaml
storage_roots:
  "/volume1/photos": "/mnt/volume1"
  "/volume2/backup": "/mnt/volume2"
  "/external/drive": "/Volumes/External"

default_storage_root: "/mnt/volume1"
```

**Result:** Different database storage roots mapped to different local mounts.

## Backwards Compatibility

### Without Configuration
System works without `config.yaml`:
- Falls back to database paths directly
- Environment variables still work
- No breaking changes

### Migration Path
1. **Phase 1** (current): Add configuration system, optional
2. **Phase 2**: Create config for each environment
3. **Phase 3**: Configuration becomes standard practice
4. **Future**: Could make config required for certain features

## Testing Path Resolution

Quick test script:

```python
from home_media_ai.config import get_path_resolver

resolver = get_path_resolver()

# Test cases
tests = [
    ("/volume1/photos", "2024/01/02", "IMG_001.CR2"),
    ("/volume1/photo/RAW", "2024", "DSC_001.NEF"),
    ("/custom/path", None, "test.jpg"),
]

for storage_root, directory, filename in tests:
    resolved = resolver.resolve_path(storage_root, directory, filename)
    print(f"Input:    {storage_root}/{directory}/{filename}")
    print(f"Resolved: {resolved}")
    print(f"Exists:   {resolved.exists()}")
    print()
```

## Benefits

1. **Cross-Platform Compatibility**
   - Same database works on Mac, Linux, Windows, NAS, Docker
   - Each environment configures its own mount points

2. **Flexible Deployment**
   - Development machines mount NAS via SMB/NFS
   - Docker containers use volume mounts
   - NAS itself uses direct paths

3. **No Code Changes**
   - Existing code automatically benefits
   - `media.get_full_path()` just works

4. **Environment Isolation**
   - Each machine has its own `config.yaml`
   - No hardcoded paths in code
   - Easy to move between environments

5. **Graceful Degradation**
   - Works without configuration
   - Falls back to database paths
   - Logs warnings when mapping fails

## Documentation

Complete documentation available at:
- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** - Full configuration guide
- **[MIGRATION_SUMMARY.md](MIGRATION_SUMMARY.md)** - Migration overview including config
- **[README.md updates needed]** - Quick start guide

## Installation

1. **Install PyYAML:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create configuration:**
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml for your environment
   ```

3. **Test configuration:**
   ```python
   from home_media_ai.config import get_config
   config = get_config()
   print(f"Storage roots: {config.storage_roots}")
   ```

4. **Use in code:**
   ```python
   # Automatically uses config
   from home_media_ai.media_query import MediaQuery
   results = MediaQuery(session).rating(5).all()
   for media in results:
       print(media.get_full_path())  # Mapped to local path
   ```

## Future Enhancements

Possible future additions:
- **Remote storage backends** (S3, Google Cloud Storage)
- **Cache remote files locally**
- **Multiple database support** (different configs per database)
- **GUI configuration tool**
- **Automatic path detection** (scan for common mount points)

## Summary

The configuration system solves the multi-environment path problem by:
1. Storing canonical paths in database (`/volume1/photos`)
2. Mapping those paths to local mounts per machine
3. Automatically resolving paths when accessing files
4. Supporting environment-specific configuration files
5. Maintaining backwards compatibility

**Result:** One database, many environments, seamless file access. ✅
