-- =====================================================
-- Media Management Tables
-- =====================================================
-- Track images, videos, and their relationships using
-- a doubly-linked list structure (parent-child).
--
-- Three states:
-- - Original: No parent (origin_id IS NULL)
-- - Derivative: Has parent (origin_id IS NOT NULL)
-- - Final: No children (no records reference via origin_id)
--
-- Note: "Original" refers to parentage, not file format.
-- A JPEG with no parent is "Original" even though it's
-- not a RAW camera file.
-- =====================================================

-- Define media type categories
CREATE TABLE IF NOT EXISTS media_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    mime_group VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci;

-- Insert common media types
INSERT IGNORE INTO media_types (name, description, mime_group) VALUES
    ('raw_image', 'RAW camera formats (DNG, CR2, NEF, ARW)', 'image'),
    ('jpeg', 'JPEG compressed image', 'image'),
    ('png', 'PNG lossless image', 'image'),
    ('tiff', 'TIFF image format', 'image'),
    ('heic', 'HEIC/HEIF image format', 'image'),
    ('video_mp4', 'MP4 video container', 'video'),
    ('video_mov', 'MOV/QuickTime video', 'video'),
    ('video_avi', 'AVI video container', 'video');

-- Core media table with provenance tracking
CREATE TABLE IF NOT EXISTS media (
    id INT AUTO_INCREMENT PRIMARY KEY,
    -- File path components (new schema)
    storage_root VARCHAR(500),
    directory VARCHAR(500),
    filename VARCHAR(255) NOT NULL,
    -- Deprecated: file_path will be removed after migration
    file_path TEXT,
    file_hash CHAR(64) NOT NULL UNIQUE,
    file_size BIGINT NOT NULL,
    file_ext VARCHAR(10),
    media_type_id INT NOT NULL,
    created DATETIME,
    -- Parent-child relationship tracking (doubly-linked list)
    is_original BOOLEAN DEFAULT FALSE,  -- TRUE if no parent (origin_id IS NULL)
    origin_id INT,                      -- Parent image ID; NULL for originals
    metadata JSON NOT NULL DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (media_type_id) REFERENCES media_types(id) ON DELETE RESTRICT,
    FOREIGN KEY (origin_id) REFERENCES media(id) ON DELETE SET NULL,
    INDEX idx_file_hash (file_hash),
    INDEX idx_created (created),
    INDEX idx_media_type (media_type_id),
    INDEX idx_original (is_original),
    INDEX idx_origin (origin_id),
    INDEX idx_storage_root (storage_root),
    INDEX idx_filename (filename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci;
