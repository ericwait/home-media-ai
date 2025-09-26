# 📊 Database Schema – Home Media AI

This document provides a technical reference for the database schema used in the **Home Media AI** project.
It is intended for developers and contributors who need to understand the structure, relationships, and rationale behind the schema.

---

## Overview

The database supports two main domains that can be applied to any type of media collection:

1. **Classification Data** – Hierarchical classification systems from any domain (biological taxonomy, geographic hierarchies, subject classifications, custom categories, etc.)
2. **Media Metadata** – Local photo, video, and audio files with original/derivative tracking and comprehensive metadata

The system is designed to link these domains flexibly, allowing media to be associated with multiple classification systems simultaneously.

---

## Core Tables

### `media_types`

Defines broad categories of media for grouping and search purposes.

| Column        | Type         | Notes |
|---------------|--------------|-------|
| `id`          | INT PK       | Auto‑increment |
| `name`        | VARCHAR(50)  | Short identifier (`image`, `video`, `audio`, `document`, etc.) |
| `description` | TEXT         | Human‑readable explanation |

---

### `file_formats`

Maps file extensions to specific formats with processing information.

| Column        | Type         | Notes |
|---------------|--------------|-------|
| `id`          | INT PK       | Auto‑increment |
| `extension`   | VARCHAR(10)  | Canonical file extension (`jpg`, `tiff`, `mp4`, `wav`, etc.) |
| `mime_type`   | VARCHAR(100) | Full MIME type (`image/jpeg`, `video/mp4`, `audio/wav`) |
| `media_type_id`| INT FK      | References `media_types.id` |
| `priority`    | INT          | Processing priority hint (higher = typically higher quality) |
| `description` | TEXT         | Human‑readable format description |

---

### `extension_aliases`

Handles extension normalization (e.g., `.tif` → `.tiff`, `.JPG` → `.jpg`).

| Column      | Type         | Notes |
|-------------|--------------|-------|
| `alias`     | VARCHAR(10)  | Variant extension (`tif`, `JPG`, `jpeg`) |
| `canonical` | VARCHAR(10)  | Canonical form, references `file_formats.extension` |

---

### `media`

Core table for tracking all media files on the NAS. Files should not move once entered.
**Original** files are the first in a provenance chain (`origin_id` is NULL).
**Derivatives** are files created from other files and point back to their source.

| Column         | Type          | Notes |
|----------------|---------------|-------|
| `id`           | BIGINT PK     | Auto‑increment |
| `base_path`    | VARCHAR(500)  | Directory path (filesystem agnostic) |
| `filename`     | VARCHAR(255)  | Just the filename portion |
| `file_path`    | TEXT          | Virtual computed column: `CONCAT(base_path, '/', filename)` |
| `file_hash`    | CHAR(64)      | SHA‑256 hash, unique |
| `file_size`    | BIGINT        | Size in bytes |
| `media_type_id`| INT FK        | References `media_types.id` |
| `format_id`    | INT FK        | References `file_formats.id` |
| `created`      | DATETIME      | Filesystem creation timestamp |
| `ingested_at`  | TIMESTAMP     | When first discovered by system |
| `updated_at`   | TIMESTAMP     | Last metadata update |
| `deleted_at`   | TIMESTAMP     | Soft delete timestamp (NULL = active) |
| `origin_id`    | BIGINT FK     | References `media.id` if derivative; NULL if original |
| `is_original`  | BOOLEAN       | Computed: `(origin_id IS NULL)` STORED |
| `has_errors`   | BOOLEAN       | True if processing encountered errors |
| `error_details`| JSON          | Structured error information |
| `metadata`     | JSON          | File‑specific data (EXIF, dimensions, codec, etc.) |

---

## Classification System Tables

### `classification_systems`

Defines different hierarchical classification systems that can be used to organize media.

| Column             | Type         | Notes |
|--------------------|--------------|-------|
| `id`               | INT PK       | Auto‑increment |
| `name`             | VARCHAR(100) | System identifier (`WFO`, `Geographic`, `Dewey_Decimal`, `Custom_Birds`, etc.) |
| `description`      | TEXT         | Human‑readable explanation of the classification system |
| `source_url`       | TEXT         | Optional URL to the authoritative source |
| `classification_type` | VARCHAR(50) | Category of system (`biological`, `geographic`, `subject`, `custom`) |

---

### `classification_versions`

Tracks versions of classification data ingested into the system for reproducibility.

| Column        | Type        | Notes |
|---------------|-------------|-------|
| `id`          | INT PK      | Auto‑increment |
| `system_id`   | INT FK      | References `classification_systems.id` |
| `version_string` | VARCHAR(50) | Version identifier (`2024-06`, `v1.2.3`, etc.) |
| `downloaded_at` | DATETIME   | UTC timestamp of ingestion |
| `file_name`   | VARCHAR(255)| Name of the ingested file |
| `file_size`   | BIGINT      | Size in bytes |
| `checksum`    | CHAR(64)    | SHA‑256 hash, unique |
| `is_current`  | BOOLEAN     | Only one current version per system |
| `notes`       | TEXT        | Freeform notes |

---

### `classification_nodes`

Hierarchical nodes within classification systems. Flexible structure supports any type of hierarchy.

| Column              | Type         | Notes |
|---------------------|--------------|-------|
| `id`                | BIGINT PK    | Auto‑increment |
| `version_id`        | INT FK       | References `classification_versions.id` |
| `external_id`       | VARCHAR(100) | Identifier from source system (WFO ID, GBIF key, etc.) |
| `parent_id`         | BIGINT FK    | Self‑referencing for hierarchy |
| `name`              | VARCHAR(255) | Primary name/identifier |
| `rank`              | VARCHAR(50)  | Level in hierarchy (varies by system) |
| `status`            | VARCHAR(50)  | Status within system (`accepted`, `synonym`, `deprecated`) |
| `authorship`        | VARCHAR(255) | Authority/source attribution |
| `metadata`          | JSON         | System‑specific data (scientific details, coordinates, etc.) |

---

## Relationships

- **Media ↔ Classifications**: Junction table links media to classification nodes with confidence scoring
- **Media ↔ Media Types**: Each media record references a broad category in `media_types`
- **Media ↔ File Formats**: Each media record references specific format details in `file_formats`
- **Media Types ↔ File Formats**: File formats belong to media types (one-to-many)
- **Media (self‑referential)**: Derivatives point back to their origin via `origin_id`
- **Classifications**: Hierarchical tree structure within each system version
- **Extension Normalization**: Aliases map to canonical forms in `file_formats`

---

## Design Principles

- **Domain Agnostic**: Works for any hierarchical classification system
- **Scale Ready**: Designed for 700K+ files with partitioning strategy
- **Filesystem Agnostic**: Path handling works across Windows/Mac/Linux
- **Data Integrity**: Computed columns and constraints prevent inconsistency
- **Reproducibility**: Every file and classification version tracked with checksums
- **Flexibility**: JSON metadata fields accommodate system-specific requirements
- **Extensibility**: Schema handles multiple classification systems simultaneously
- **Performance**: Strategic indexing and partitioning for large datasets
- **Error Resilience**: Structured error handling without breaking workflows
- **Auditability**: Soft deletes and comprehensive temporal tracking

---

## Key Assumptions

1. **File Immutability**: Once a file gets a row in the media table, its location should not change
2. **Provenance Tracking**: Original files have `origin_id = NULL`, derivatives point to their source
3. **Extension Normalization**: Case variations and synonyms (`.tif`/`.tiff`) handled via aliases
4. **Soft Deletes**: Files are marked deleted rather than removed for recovery and audit
5. **Concurrent Access**: Multiple processes may access the same entries with proper transaction handling
6. **Processing Separation**: Processing pipelines are decoupled from media entries to avoid table bloat

---

## Use Cases

This generic schema supports diverse applications:

- **Biological Collections**: Plants (WFO), animals (GBIF), fungi, etc.
- **Geographic Organization**: Country/state/city hierarchies, ecological regions
- **Subject Classification**: Library systems, custom topic hierarchies
- **Equipment/Object Catalogs**: Technical specifications, model hierarchies
- **Mixed Collections**: Multiple classification systems on the same media

---

## Performance Optimizations

- **Partitioning**: Date-based partitioning by `ingested_at` for large datasets
- **Computed Columns**: `is_original` and `file_path` for fast common queries
- **Strategic Indexing**: Hash, filename, timestamp, and status indexes
- **Path Optimization**: Separate `base_path`/`filename` for efficient searches
- **JSON Metadata**: Flexible storage without schema changes

---

## Roadmap

- **Phase II**: Implement media-classification linking with confidence scoring
- **Phase III**: Build flexible query interfaces for different classification types
- **Phase IV**: Create visualization tools that adapt to different hierarchy types
- **Phase V**: Advanced features (thumbnails, processing pipelines, duplicate detection)
