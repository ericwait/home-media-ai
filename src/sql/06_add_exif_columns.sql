-- =====================================================
-- Add EXIF Metadata Columns to Media Table
-- =====================================================
-- Adds columns for commonly-used EXIF fields that may be
-- useful for searching, filtering, and ML model training.
-- Additional metadata remains in the JSON field.
-- =====================================================

-- Add GPS coordinates (for geotagging and location-based queries)
ALTER TABLE media
ADD COLUMN gps_latitude DECIMAL(10, 8) NULL COMMENT 'GPS latitude in decimal degrees',
ADD COLUMN gps_longitude DECIMAL(11, 8) NULL COMMENT 'GPS longitude in decimal degrees',
ADD COLUMN gps_altitude DECIMAL(8, 2) NULL COMMENT 'GPS altitude in meters';

-- Add camera information (useful for filtering by equipment)
ALTER TABLE media
ADD COLUMN camera_make VARCHAR(100) NULL COMMENT 'Camera manufacturer',
ADD COLUMN camera_model VARCHAR(100) NULL COMMENT 'Camera model',
ADD COLUMN lens_model VARCHAR(100) NULL COMMENT 'Lens model if available';

-- Add image dimensions (useful for filtering and display)
ALTER TABLE media
ADD COLUMN width INT NULL COMMENT 'Image width in pixels',
ADD COLUMN height INT NULL COMMENT 'Image height in pixels';

-- Add quality rating (0-5 stars, for ML training and manual curation)
-- This is the XMP Rating field commonly used in photo management software
ALTER TABLE media
ADD COLUMN rating TINYINT NULL COMMENT 'Quality rating 0-5 stars' CHECK (rating >= 0 AND rating <= 5);

-- Rename metadata column to exif_data (metadata is reserved by SQLAlchemy)
ALTER TABLE media
CHANGE COLUMN metadata exif_data JSON NULL DEFAULT '{}' COMMENT 'Additional EXIF metadata as JSON';

-- Create indexes for commonly-queried fields
CREATE INDEX idx_media_gps ON media(gps_latitude, gps_longitude);
CREATE INDEX idx_media_camera ON media(camera_make, camera_model);
CREATE INDEX idx_media_rating ON media(rating);
CREATE INDEX idx_media_dimensions ON media(width, height);

-- Verify new columns
SHOW COLUMNS FROM media LIKE '%gps%';
SHOW COLUMNS FROM media LIKE '%camera%';
SHOW COLUMNS FROM media LIKE 'rating';
SHOW COLUMNS FROM media LIKE 'width';