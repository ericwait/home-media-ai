# 📊 Database Schema – Home Media AI

This document provides a technical reference for the database schema used in the **Home Media AI** project.
It is intended for developers and contributors who need to understand the structure, relationships, and rationale behind the schema.

---

## Overview

The database currently supports two main domains:

1. **Taxonomy Data** – Ingested from the [World Flora Online Backbone](http://www.worldfloraonline.org/).
2. **Image Metadata** – Local photo and video files, with RAW masters and derivative tracking.

Future expansions will link these domains (e.g., associating images with taxa).

---

## Tables

### `images`

Phase I schema for local image metadata.  
**Original** files are treated as the canonical start of a provenance chain.  
If multiple files share the same timestamp, RAW‑like formats take precedence as the original, and others are marked as derivatives.

| Column       | Type         | Notes                                                                 |
|--------------|--------------|----------------------------------------------------------------------|
| `id`         | INT PK       | Auto‑increment                                                       |
| `file_path`  | TEXT         | Fully qualified path                                                 |
| `file_hash`  | CHAR(64)     | SHA‑256 hash, unique                                                 |
| `file_size`  | BIGINT       | Size in bytes                                                        |
| `file_ext`   | VARCHAR(10)  | File extension (`jpg`, `dng`, `tif`, etc.)                           |
| `created`    | DATETIME     | Filesystem timestamp                                                 |
| `is_original`| BOOLEAN      | True if this file is the original in its provenance chain            |
| `origin_id`  | INT FK       | References `images.id` if derivative; NULL if this is the original   |

### `wfo_versions`

Tracks versions of the WFO backbone ZIP file ingested into the system.

| Column        | Type        | Notes |
|---------------|-------------|------|
| `id`          | INT PK      | Auto‑increment |
| `downloaded_at` | DATETIME   | UTC timestamp of ingestion |
| `file_name`   | VARCHAR(255) | Name of the ingested file |
| `file_size`   | BIGINT      | Size in bytes |
| `checksum`    | CHAR(64)    | SHA‑256 hash, unique |
| `notes`       | TEXT        | Freeform notes |

---

### `plant_taxonomy`

Normalized subset of the WFO backbone.
Focuses on accepted taxa and core metadata.

| Column              | Type         | Notes |
|---------------------|--------------|------|
| `taxon_id`          | VARCHAR(50) PK | WFO taxon identifier |
| `parent_id`         | VARCHAR(50) | Parent taxon (hierarchy) |
| `scientific_name`   | VARCHAR(255) | Canonical name |
| `authorship`        | VARCHAR(255) | Author citation |
| `taxon_rank`        | VARCHAR(50)  | e.g., family, genus, species |
| `family`            | VARCHAR(100) | Family name |
| `genus`             | VARCHAR(100) | Genus name |
| `taxonomic_status`  | VARCHAR(50)  | Accepted / synonym |
| `source_references` | TEXT         | Reference citations |
| `source`            | VARCHAR(255) | Source dataset |
| `major_group`       | VARCHAR(100) | Angiosperms, Gymnosperms, etc. |
| `created`           | DATE         | Record creation date |
| `modified`          | DATE         | Last modification date |

---

### `plant_images`

Phase I schema for local image metadata.
RAW files are treated as canonical masters; processed formats are tracked as derivatives.

| Column       | Type         | Notes |
|--------------|--------------|------|
| `id`         | INT PK       | Auto‑increment |
| `file_path`  | TEXT         | Fully qualified path |
| `file_hash`  | CHAR(64)     | SHA‑256 hash, unique |
| `file_size`  | BIGINT       | Size in bytes |
| `file_ext`   | VARCHAR(10)  | File extension (jpg, dng, etc.) |
| `created`    | DATETIME     | Filesystem timestamp |
| `is_raw`     | BOOLEAN      | True if RAW (dng, cr2, nef, arw) |
| `master_id`  | INT FK       | References `plant_images.id` if derivative |

---

## Relationships

- **Taxonomy ↔ Images**: Not yet implemented. Future schema will add a `taxon_id` foreign key in `plant_images` to link media to taxa.
- **Images (self‑referential)**: Derivatives point back to their RAW master via `master_id`.

---

## Design Principles

- **Reproducibility**: Every ingested file is tracked with a checksum.
- **Minimalism first**: Start with essential columns, expand iteratively.
- **Extensibility**: Schema designed to accommodate EXIF/GPS metadata and taxon links in later phases.
- **Auditability**: Versioning tables ensure provenance of both taxonomy and media data.

---

## Roadmap

- **Phase II**: Add EXIF metadata columns (`exif_datetime`, `camera_model`, `gps_lat`, `gps_lon`).
- **Phase III**: Link `plant_images` to `plant_taxonomy` via `taxon_id`.
- **Phase IV**: Build reporting and visualization layers (dashboards, dendrograms).