# MacBook Pro Setup ("The Server")

## Role
*   **Name:** The Server / The Brain
*   **Function:** Hosts the core application, database, and user interface.
*   **Availability:** Always-on (or Wake-on-LAN capable).

## Hardware Configuration
*   **Storage:**
    *   **Internal NVMe:** Hosting the OS, Code, PostgreSQL Database (for speed), and Redis.
    *   **DAS (Direct Attached Storage):** Hosting generated thumbnails, proxy files, and potentially the vector index if it grows too large.
*   **Network:** Wired Ethernet preferred for stable NAS connection.

## Software Stack & Installation

### 1. Prerequisites
*   **OS:** macOS (latest stable).
*   **Package Manager:** Homebrew (`brew`).
*   **Runtime:**
    *   Python 3.11+ (via Conda/Mamba recommended).
    *   Node.js (for React frontend).

### 2. Database (PostgreSQL)
*   **Install:** `brew install postgresql`
*   **Extensions:**
    *   `pgvector`: For vector embeddings (CLIP).
    *   `ltree`: For hierarchical taxonomy.
*   **Configuration:**
    *   Ensure DB listens on local interface (or exposed if Worker needs direct DB access, though API is preferred).

### 3. Message Queue (Redis)
*   **Install:** `brew install redis`
*   **Role:** Broker for job queue between Server and Worker.

### 4. Application Services
*   **Backend:** FastAPI application running via Uvicorn/Gunicorn.
*   **Frontend:** React (Vite) application served via Nginx or simple dev server for home use.

### 5. Mounting the Vault
*   Mount the Synology NAS share (SMB/NFS) to a consistent mount point, e.g., `/Volumes/photos`.
*   Ensure auto-mount on boot.

## Deployment Steps (Draft)
```bash
# 1. Clone Repo
git clone ...

# 2. Setup Environment
mamba env create -f environment.yaml

# 3. Start Services
brew services start postgresql
brew services start redis

# 4. Run Server
uvicorn src.python.main:app --reload
```
