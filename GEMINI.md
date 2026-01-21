# GEMINI Project Context: home-media-ai

## 1. Project Vision & Architecture
**Goal:** To build a distributed, private, AI-powered system for indexing, classifying, and curating a multi-terabyte home media collection. The system emphasizes "pixel-wise" understanding (segmentation), taxonomy management, and high-performance retrieval without relying on cloud services.

### The "3-Node" Distributed Architecture
The system is split across three hardware nodes to balance storage capacity, always-on availability, and on-demand compute power.

1.  **The Server (MacBook Pro):**
    * **Role:** The "Brain" and User Interface. Always-on (or wake-on-lan).
    * **Storage:** NVMe (Fast DB access) + DAS (Thumbnails/Proxies).
    * **Responsibilities:** Hosting the Web UI, API, Database, and Job Queue.
2.  **The Vault (Synology NAS):**
    * **Role:** The "Library."
    * **Storage:** Spinning Disks (3.7 TB+).
    * **Responsibilities:** Storing the master RAW/JPEG files. Mounted via SMB/NFS to other nodes. Read-only for most processes; "Write-back" operations are strictly controlled via the API.
3.  **The Worker (Alienware Laptop):**
    * **Role:** The "Muscle." On-demand.
    * **Hardware:** NVIDIA GPU.
    * **Responsibilities:** Running heavy AI inference (YOLO, SAM-2, CLIP). Connects to the Server to pull jobs, processes images from the Vault, and returns metadata/masks to the Server.

### The Tech Stack (The "Wait Stack")
* **Core Library:** `home-media` (Python 3.11) - *See Section 3*.
* **Database:** PostgreSQL (with `pgvector` for embeddings and `ltree` for taxonomy).
* **Backend API:** FastAPI (Python).
* **Frontend:** React (Vite).
* **Message Queue:** Redis (Connects the Mac Server to the Alienware Worker).
* **AI Models:**
    * **Detection/Segmentation:** YOLOv8/v11 or SAM-2.
    * **Embeddings:** CLIP (for semantic search).
    * **Taxonomy:** Custom graph logic implemented via Postgres `ltree`.

---

## 2. Implementation Roadmap
The project is executed in prioritized phases. We are currently transitioning from Phase 0 to Phase 1.

* **Phase 0: Infrastructure (Done/In Progress)**
    * Set up `home-media` library structure.
    * Define core data models (`Image`, `ImageFile`).
    * Implement basic file scanning logic.
* **Phase 1: The Basic Viewer (Current Focus)**
    * **Goal:** A fast, date-based web gallery running on the Mac.
    * **Task:** Use `home-media` scanner to populate Postgres.
    * **Task:** Build FastAPI endpoints for `GET /images` and thumbnails.
    * **Task:** Build React Frontend for infinite scroll grid.
* **Phase 2: Metadata & Ratings**
    * **Goal:** User curation (Ratings, Location).
    * **Task:** Implement "Write-back" logic (API -> ExifTool -> NAS Sidecar).
* **Phase 3: The "Muscle" & Object Masks**
    * **Goal:** Pixel-wise segmentation using the Alienware.
    * **Task:** Build the Redis Worker script using PyTorch/CUDA.
    * **Task:** Store RLE (Run-Length Encoded) masks in Postgres/DAS.
* **Phase 4: Graph Inspection & Taxonomy**
    * **Goal:** "Show me all Trucks" or "Show me Zoey."
    * **Task:** Implement recursive `ltree` queries.
    * **Task:** Train/Fine-tune embeddings for specific entities (e.g., Zoey the dog).
* **Phase 5: Refinement**
    * **Goal:** Correcting AI mistakes via UI.
    * **Task:** Build visual mask editor and label correction tools.

---

## 3. Current Library Implementation (`home-media`)
The `home-media` Python library is the foundation of this system. It is currently designed to be imported by the future API and Worker scripts to handle the low-level file operations.

### Key Components
* **Technology Stack**: Python 3.11 (Conda/Mamba), Pandas, Pillow, ExifRead, Pytest.
* **Data Models (`src/python/home_media/models`):**
    * `Image`: Represents a single abstract "moment" (groups RAW+JPG).
    * `ImageFile`: Represents a concrete file on disk.
    * `FileFormat` & `FileRole`: Enums for file classification (e.g., `ORIGINAL`, `SIDECAR`).
* **Scanner Module (`src/python/home_media/scanner`):**
    * **Function:** `scan_directory` traverses paths, groups related files, and extracts metadata.
    * **Output:** Returns Pandas DataFrames (`images_df`, `files_df`).
    * **Strategic Note:** This module will serve as the "Ingest Engine" for Phase 1, feeding data from the NAS into the PostgreSQL database.

### Development Conventions
* **Testing:** High coverage (80%+) using `pytest`. Tests are marked `unit`, `integration`, and `slow`.
* **CI/CD:** GitHub Actions for cross-platform testing (Windows, macOS, Ubuntu).
* **Style:** Type hints, dataclasses, and strict modularity.

### Building and Running
**Environment Setup:**
```bash
mamba env create -f environment.yaml
mamba activate home-media
pip install -e .

```

**Running Tests:**

```bash
pytest --cov=home_media --cov-report=term-missing

```

**Example Usage:**

```python
from home_media import scan_directory
from pathlib import Path

# This logic will eventually reside inside the Phase 1 Ingest Script
images_df, files_df = scan_directory(Path("/Volumes/Photos"))
```

### Strategic Connection
The existing `home-media` library is the **logic layer** for the new architecture.
1.  **The API (MacBook)** will import `home_media.models` to understand what an "Image" is.
2.  **The Ingester (MacBook)** will use `home_media.scanner` to crawl the NAS and populate the DB.
3.  **The Worker (Alienware)** will eventually use `home_media` utilities to handle file path resolution when loading images for AI processing.