-- =====================================================
-- Media Management Tables
-- =====================================================
-- Track images, videos, and their relationships.
-- RAW files are treated as originals; derivatives
-- reference their origin via origin_id.
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
    file_path TEXT NOT NULL,
    file_hash CHAR(64) NOT NULL UNIQUE,
    file_size BIGINT NOT NULL,
    file_ext VARCHAR(10),
    media_type_id INT NOT NULL,
    created DATETIME,
    is_original BOOLEAN DEFAULT FALSE,
    origin_id INT,
    metadata JSON NOT NULL DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (media_type_id) REFERENCES media_types(id) ON DELETE RESTRICT,
    FOREIGN KEY (origin_id) REFERENCES media(id) ON DELETE SET NULL,
    INDEX idx_file_hash (file_hash),
    INDEX idx_created (created),
    INDEX idx_media_type (media_type_id),
    INDEX idx_original (is_original),
    INDEX idx_origin (origin_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_520_ci;
