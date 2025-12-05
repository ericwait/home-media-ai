# 🏠 Home Media AI

> **⚠️ Vibe Coding Experiment**
> This project is built almost entirely through AI-assisted development (Claude prompts). I'm exploring the limits of taking a project from initial concept to real-world "production" use by my family (non-programmers) using primarily natural language direction rather than traditional coding. Consider this both a functional tool and an experiment in AI-powered software development.

A flexible system for organizing, classifying, and exploring personal media collections using hierarchical classification systems.
This project combines authoritative classification data with personal media collections to build a reproducible, auditable knowledge base.

## 📖 Overview

- **Universal Classification**: Work with any hierarchical system - biological taxonomy, geographic regions, subject categories, or your own custom classifications
- **Smart Media Organization**: Automatically discover and track your photos, videos, and audio files with intelligent duplicate detection and relationship mapping
- **Flexible Connections**: Link your media to multiple classification systems with confidence tracking
- **Visual Exploration**: Interactive diagrams and dashboards to explore your organized collections
- **Built for Scale**: Handles large personal collections (tested with 700K+ files)

## ⚙️ Requirements

- MariaDB 10.11+ instance (remote or local) with computed column support
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
mamba install numpy pandas matplotlib mariadb seaborn scikit-learn opencv pillow sqlalchemy jupyterlab exifread
```

Set up the database schema:

```sh
# Create tables and initial data
mysql -u user -p database < src/sql/schema.sql
```

Run classification data ingestion (example with WFO plant data):

```sh
python src/python/import_flora_wfo_data.py
```

Run media discovery and ingestion:

```sh
python src/python/discover_media.py --base-path /path/to/your/media
```

## 📂 Repository Structure

```sh
.
├── data/        # Classification sources, test fixtures, working files
├── doc/         # Documentation and examples
├── src/         # Source code
│   ├── python/  # Python scripts and utilities
│   └── sql/     # Database schema and migrations
└── .vscode/     # VS Code settings (optional)
```

## 🔧 Key Design Principles

- **Your Files Stay Put**: Once discovered, file locations are tracked but never moved by the system
- **Works Everywhere**: Handles Windows, Mac, and Linux file paths seamlessly
- **Relationship Aware**: Tracks which files are originals vs edited versions
- **Safe by Default**: Files are marked as deleted rather than actually removed
- **Built to Last**: Everything is checksummed and versioned for long-term reliability

## 🌍 Supported Classification Systems

This system is designed to work with any hierarchical classification:

- **Biological**: World Flora Online (WFO), GBIF species data, custom taxonomies
- **Geographic**: Country/state/city hierarchies, ecological regions, custom locations
- **Subject-Based**: Library classification systems, custom topic hierarchies
- **Technical**: Equipment catalogs, software versions, custom object classifications

## 🔮 Roadmap

- **Phase I**: Core media discovery and database schema *(in progress)*
- **Phase II**: Classification system integration and linking
- **Phase III**: Advanced organization tools and bulk operations
- **Phase IV**: Interactive visualization and exploration interfaces
- **Phase V**: AI-powered suggestions and advanced analytics

## 🧪 Example Use Cases

- **Nature Photography**: Link plant photos to WFO taxonomy + geographic locations
- **Travel Documentation**: Organize photos by location hierarchies + subject matter
- **Technical Documentation**: Classify equipment photos by manufacturer/model + project context
- **Family Archives**: Organize by date/location + custom family/event categories

## 📚 Documentation

- **[Database Schema](doc/database_schema.md)**: Comprehensive technical reference
- **[Schema Diagram](doc/database_schema.mmd)**: Visual representation of table relationships
- **API Documentation**: *(Coming in Phase II)*
- **User Guides**: *(Coming in Phase III)*

## 🤝 Contributing

This project is designed to be domain-agnostic and extensible.
Whether you're working with plants, animals, locations, or completely custom classification systems, the core architecture should accommodate your needs.

See the database schema documentation for technical details on adding new classification systems or extending the media management capabilities.
