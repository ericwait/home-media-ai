-- =====================================================
-- Taxonomy Management Tables
-- =====================================================
-- These tables track authoritative taxonomy sources,
-- their versions, and the hierarchical node structure.
-- =====================================================

-- Track different taxonomy sources (WFO, GBIF, etc.)
CREATE TABLE IF NOT EXISTS taxonomies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    source VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci;

-- Track versions of ingested taxonomy files
CREATE TABLE IF NOT EXISTS taxonomy_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    taxonomy_id INT NOT NULL,
    downloaded_at DATETIME NOT NULL,
    file_name VARCHAR(255),
    file_size BIGINT,
    checksum CHAR(64) UNIQUE,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (taxonomy_id) REFERENCES taxonomies(id) ON DELETE CASCADE,
    INDEX idx_taxonomy_downloaded (taxonomy_id, downloaded_at),
    INDEX idx_checksum (checksum)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci;

-- Hierarchical taxonomy nodes (families, genera, species, etc.)
CREATE TABLE IF NOT EXISTS taxonomy_nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    taxonomy_id INT NOT NULL,
    parent_id INT,
    external_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    rank VARCHAR(50),
    status VARCHAR(50),
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (taxonomy_id) REFERENCES taxonomies(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES taxonomy_nodes(id) ON DELETE SET NULL,
    UNIQUE KEY unique_taxonomy_external (taxonomy_id, external_id),
    INDEX idx_taxonomy_parent (taxonomy_id, parent_id),
    INDEX idx_name (name),
    INDEX idx_rank_status (rank, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci;
