# 🌿 Home Media AI

Work with home images and video to classify, organize, and explore their content.
This project combines authoritative plant taxonomy data with personal media collections to build a reproducible, auditable knowledge base.

## 📖 Overview

- **Taxonomy ingestion**: Scripts download and normalize the World Flora Online backbone into a MariaDB database.
- **Visualization**: Mermaid diagrams and other assets provide quick overviews of families, genera, and higher‑level groups.
- **Image management** *(in progress)*: Local photos will be scraped, hashed, and linked into the taxonomy, with RAW files treated as canonical masters and derivatives tracked explicitly.
- **Documentation**: High‑level guidance lives here. Each subdirectory will eventually have its own technical manual.

## ⚙️ Requirements

- MariaDB 10.1+ instance (remote or local)
- Database configured with UTF‑8 support (`utf8mb4`, `utf8mb4_unicode_520_ci`)
- Connection string provided via environment variable:

  ```sh
  export HOME_MEDIA_AI_URI="mariadb+mariadbconnector://user:password@host:port/dbname"
  ```

## 🚀 Quickstart

Create a development environment with [mamba](https://mamba.readthedocs.io/):

```sh
mamba env create -n home-media-ai python
mamba activate home-media-ai
mamba install numpy pandas matplotlib mariadb seaborn scikit-learn opencv pillow sqlalchemy jupyterlab
```

Run the ingestion pipeline:

```sh
python src/python/import_flora_wfo_data.py
```

## 📂 Repository Structure

```sh
.
├── data/        # Working data (WFO backbone, test fixtures, intermediate files)
├── doc/         # Documentation assets and examples
├── src/python/  # Source code (pipelines, utilities, notebooks)
└── .vscode/     # Suggested VS Code settings (optional)
```

## 🔮 Roadmap

- Phase I: Image metadata scraping (hashing, EXIF, RAW/derivative relationships)
- Phase II: Linking images to taxa
- Phase III: Richer visualization and query dashboards
- Phase IV: Full documentation site
