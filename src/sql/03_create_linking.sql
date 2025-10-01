-- =====================================================
-- Media-Taxonomy Linking Tables
-- =====================================================
-- Connect media files to taxonomy nodes with
-- assignment tracking and provenance.
-- =====================================================

-- Link media to taxonomy nodes
CREATE TABLE IF NOT EXISTS media_taxonomy_links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    media_id INT NOT NULL,
    taxonomy_node_id INT NOT NULL,
    assigned_by VARCHAR(100),
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    confidence DECIMAL(5,4),
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (media_id) REFERENCES media(id) ON DELETE CASCADE,
    FOREIGN KEY (taxonomy_node_id) REFERENCES taxonomy_nodes(id) ON DELETE CASCADE,
    UNIQUE KEY unique_media_taxonomy (media_id, taxonomy_node_id),
    INDEX idx_media (media_id),
    INDEX idx_taxonomy_node (taxonomy_node_id),
    INDEX idx_assigned_by (assigned_by),
    INDEX idx_confidence (confidence)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci;
