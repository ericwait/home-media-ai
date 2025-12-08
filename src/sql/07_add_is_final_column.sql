-- =====================================================
-- Add is_final Column for Efficient Final State Queries
-- =====================================================
-- This migration adds an 'is_final' column to track images
-- with no children (end of processing chain).
--
-- States:
-- - Original: origin_id IS NULL (no parent)
-- - Derivative: origin_id IS NOT NULL (has parent)
-- - Final: is_final = TRUE (no children)
--
-- SAFE TO RUN MULTIPLE TIMES: This script checks if
-- the column and index already exist before creating them.
-- =====================================================

-- Add the is_final column (default FALSE) if it doesn't exist
SET @column_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'media'
    AND COLUMN_NAME = 'is_final'
);

SET @sql = IF(@column_exists = 0,
    'ALTER TABLE media ADD COLUMN is_final BOOLEAN DEFAULT FALSE AFTER is_original',
    'SELECT "Column is_final already exists, skipping..." AS Info'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Create an index for efficient querying if it doesn't exist
SET @index_exists = (
    SELECT COUNT(*)
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'media'
    AND INDEX_NAME = 'idx_is_final'
);

SET @sql = IF(@index_exists = 0,
    'CREATE INDEX idx_is_final ON media(is_final)',
    'SELECT "Index idx_is_final already exists, skipping..." AS Info'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Create a stored procedure to update is_final status
-- This marks an image as final if no children reference it
DELIMITER //

CREATE OR REPLACE PROCEDURE update_is_final()
BEGIN
    -- Mark all images as final initially
    UPDATE media SET is_final = TRUE;

    -- Mark images with children as NOT final
    UPDATE media m
    INNER JOIN (
        SELECT DISTINCT origin_id
        FROM media
        WHERE origin_id IS NOT NULL
    ) children ON m.id = children.origin_id
    SET m.is_final = FALSE;
END //

DELIMITER ;

-- Run the initial update to populate is_final values
CALL update_is_final();

-- Create triggers to maintain is_final automatically

-- Trigger: When a new derivative is added, mark its parent as NOT final
DELIMITER //

CREATE OR REPLACE TRIGGER maintain_is_final_on_insert
AFTER INSERT ON media
FOR EACH ROW
BEGIN
    -- If this new image has a parent, mark the parent as NOT final
    IF NEW.origin_id IS NOT NULL THEN
        UPDATE media
        SET is_final = FALSE
        WHERE id = NEW.origin_id;
    END IF;
END //

DELIMITER ;

-- Trigger: When an image's parent changes, update both old and new parents
DELIMITER //

CREATE OR REPLACE TRIGGER maintain_is_final_on_update
AFTER UPDATE ON media
FOR EACH ROW
BEGIN
    -- If origin_id changed (handling NULL comparisons properly for MariaDB)
    IF NOT (OLD.origin_id <=> NEW.origin_id) THEN

        -- Check if old parent should become final (if it has no other children)
        IF OLD.origin_id IS NOT NULL THEN
            UPDATE media
            SET is_final = NOT EXISTS(
                SELECT 1 FROM media WHERE origin_id = OLD.origin_id AND id != NEW.id
            )
            WHERE id = OLD.origin_id;
        END IF;

        -- Mark new parent as NOT final (it now has at least this child)
        IF NEW.origin_id IS NOT NULL THEN
            UPDATE media
            SET is_final = FALSE
            WHERE id = NEW.origin_id;
        END IF;
    END IF;
END //

DELIMITER ;

-- Trigger: When an image is deleted, check if its parent should become final
DELIMITER //

CREATE OR REPLACE TRIGGER maintain_is_final_on_delete
AFTER DELETE ON media
FOR EACH ROW
BEGIN
    -- If this image had a parent, check if parent should become final
    IF OLD.origin_id IS NOT NULL THEN
        UPDATE media
        SET is_final = NOT EXISTS(
            SELECT 1 FROM media WHERE origin_id = OLD.origin_id
        )
        WHERE id = OLD.origin_id;
    END IF;
END //

DELIMITER ;

-- =====================================================
-- Usage Examples
-- =====================================================

-- Find all final images (ready for export/sharing)
-- SELECT * FROM media WHERE is_final = TRUE;

-- Find original + final (camera images never edited)
-- SELECT * FROM media WHERE is_original = TRUE AND is_final = TRUE;

-- Find derivative + final (edited versions at end of chain)
-- SELECT * FROM media WHERE is_original = FALSE AND is_final = TRUE;

-- Find originals that have been edited (NOT final)
-- SELECT * FROM media WHERE is_original = TRUE AND is_final = FALSE;

-- Manual refresh if needed (rarely required due to triggers)
-- CALL update_is_final();
