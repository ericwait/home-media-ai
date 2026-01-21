# Alienware Laptop Setup ("The Worker")

## Role

* **Name:** The Muscle
* **Function:** Performs heavy AI inference and image processing tasks.
* **Availability:** On-demand (can be turned off when not processing).

## Hardware Configuration

* **GPU:** NVIDIA GeForce RTX (Consumer grade) or similar.
* **Network:** High-speed connection to Server (for jobs) and NAS (for reading images).

## Software Stack & Installation

### 1. Prerequisites

* **OS:** Windows 11 (or Linux if dual-booting).
* **Drivers:** Latest NVIDIA Game Ready or Studio Drivers.
* **CUDA Toolkit:** Compatible version for PyTorch.

### 2. Environment

* **Python:** 3.11+ (via Mamba/Conda).
* **Libraries:**
    * `torch` (with CUDA support)
    * `ultralytics` (YOLO)
    * `segment-anything-2`
    * `redis` (client)

### 3. Mounting the Vault

* Mount the Synology NAS share to a consistent drive letter, e.g., `Z:\photos`.
* **Crucial:** The path mapping in the configuration must translate between Mac paths (`/Volumes/photos/...`) and Windows paths (`Z:\photos\...`).

## Operation

### The Worker Script

* Connects to Redis on the MacBook Pro.
* Listens for `job_queue` messages.
* **Workflow:**
    1. Receive Job: `{ "image_path": "/Volumes/photos/2023/IMG_001.CR2", "job_id": 123 }`
    2. Translate Path: `/Volumes/photos/...` -> `Z:\photos\...`
    3. Load Image: Read from NAS.
    4. Inference: Run YOLO/SAM-2/CLIP.
    5. Return Result: Post JSON/Masks back to Server API or Redis result queue.
