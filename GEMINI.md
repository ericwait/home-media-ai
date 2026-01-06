# Home Media AI - Project Context

## Project Overview

**Home Media AI** is a flexible system for organizing, classifying, and exploring personal media collections (photos, videos) using hierarchical classification systems and AI. It is designed to work with existing file structures without moving files, making it safe for large archives.

**Key Philosophy:** "Vibe Coding Experiment" - This project is primarily built through AI-assisted development (Claude/LLM prompts). The goal is to explore the limits of natural language driven software development.

### Core Architecture

-   **Database (MariaDB):** The central source of truth. Uses computed columns and stores metadata, taxonomy, and file paths.
-   **Python Package (`src/python/home_media_ai`):** The core logic for media scanning, importing, metadata extraction (EXIF/XMP), and querying.
-   **Web Application (`src/web/`):** A Flask-based web interface for browsing media, viewing dashboards, and exploring relationships.
-   **Legacy/Auxiliary:** `src/matlab` contains MATLAB scripts for specific processing tasks (likely legacy or specialized).

### Technologies

-   **Language:** Python 3.12 (primary), SQL, MATLAB.
-   **Database:** MariaDB 10.11+ (requires `utf8mb4`).
-   **Libraries:** SQLAlchemy, Pandas, Pillow, rawpy, exifread, Flask, Ultralytics (YOLO).
-   **Infrastructure:** Docker, Conda/Mamba.

## Building and Running

### 1. Environment Setup

The project uses Conda/Mamba for dependency management.

```bash
# Create environment
mamba env create -f environment.yml
mamba activate home-media-ai-stable
```

**Note:** When executing Python scripts directly, use the full path to the interpreter: `D:\mamba_envs\home-media-ai-stable\python.exe`

### 2. Configuration

The system relies on a `config.yaml` file to handle cross-platform path resolution (mapping NAS paths to local mount points).

1.  Copy a template: `cp src/python/config.example.yaml config.yaml` (or `config.dev.yaml` / `config.synology.yaml`).
2.  Edit `config.yaml` to define `storage_roots` mapping database paths to local paths.
3.  Set `HOME_MEDIA_AI_URI` environment variable for the database connection.

### 3. Database Initialization

SQL scripts in `src/sql/` set up the schema.

```bash
mysql -u user -p dbname < src/sql/01_create_taxonomies.sql
mysql -u user -p dbname < src/sql/02_create_media.sql
# ... run other migration scripts as needed
```

### 4. Running Components

*   **Media Scan & Import:**
    ```bash
    python src/python/scripts/scan_media.py /path/to/media --extract-exif
    ```
*   **Web Interface:**
    ```bash
    cd src/web
    python app.py
    # or via Docker
    docker-compose up
    ```
*   **Jupyter Notebooks:**
    Located in `src/python/notebooks/` for exploration and development.

### 5. Testing

```bash
pytest src/python/tests/ -v
```

## Development Conventions

*   **AI-First:** Changes are often driven by natural language prompts. Maintain the existing style and architectural patterns which have been established by this process.
*   **Path Safety:** The system **never moves or deletes** actual media files. It only reads and indexes them.
*   **Path Resolution:** Crucial for cross-platform compatibility (Windows vs Linux vs NAS). Always use the `PathResolver` or `Media.get_full_path()` methods rather than raw string manipulation when accessing files.
*   **Database Schema:** The schema is the contract. Changes to data structure usually require SQL migrations.
*   **Mixed Codebase:** Be aware of the interaction between Python, SQL, and potentially MATLAB components.

## Directory Structure

*   `src/python/home_media_ai/`: Main Python package.
*   `src/sql/`: Database DDL and migrations.
*   `src/web/`: Flask web application.
*   `docs/`: Documentation (Schema, Config, etc.).
*   `data/`: Working data, logs, and temporary files.
