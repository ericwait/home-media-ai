# Synology NAS Setup ("The Vault")

## Role
*   **Name:** The Vault
*   **Function:** Central storage library for all master media files.
*   **Availability:** Always-on.

## Hardware Configuration
*   **Storage:** 3.7 TB+ Spinning Disks (RAID configuration recommended for redundancy).
*   **Network:** Gigabit Ethernet (or faster).

## Services & Configuration

### 1. File Services
*   **Protocol:** SMB (Server Message Block) and/or NFS (Network File System).
*   **Shares:**
    *   `/volume1/photos` (or similar): The root directory for the media library.

### 2. User Permissions
Security is critical. The "Library" should be immutable to most processes.

*   **Admin/Owner:** Full Read/Write access.
*   **MacBook Server (Ingest/API):**
    *   **Read:** Recursive read access to all media files.
    *   **Write:** Limited write access strictly for "Sidecar" files (XMP) if "Write-back" is enabled. *Ideally, use a specific service account.*
*   **Alienware Worker:**
    *   **Read:** Read-only access to media files for processing.
    *   **Write:** None (typically). It sends results to the Redis/DB on the server, not the file system.

### 3. Directory Structure
(Proposed structure)
```text
/photos
  /2023
    /2023-01-01_EventName
      IMG_001.CR2
      IMG_001.JPG
      IMG_001.xmp
```

## Maintenance
*   Ensure regular scrubbing and SMART tests.
*   Backup critical data to an offsite location (e.g., cloud or another NAS).
