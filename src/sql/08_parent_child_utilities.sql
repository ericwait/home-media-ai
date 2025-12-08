-- =====================================================
-- Parent-Child Relationship Utilities
-- =====================================================
-- Helper queries and procedures for working with the
-- parent-child (origin_id) relationships in the media table.
--
-- The one-to-many relationship already exists via:
-- - origin_id: Each child points to one parent
-- - Multiple children can share the same origin_id
-- =====================================================

-- =====================================================
-- Stored Procedures
-- =====================================================

-- Get all children of a specific parent image
DELIMITER //

CREATE OR REPLACE PROCEDURE get_children(IN parent_id INT)
BEGIN
    SELECT
        m.*,
        'derivative' as relationship_type
    FROM media m
    WHERE m.origin_id = parent_id
    ORDER BY m.created ASC;
END //

DELIMITER ;

-- Get the parent of a specific image
DELIMITER //

CREATE OR REPLACE PROCEDURE get_parent(IN child_id INT)
BEGIN
    SELECT
        parent.*,
        'original' as relationship_type
    FROM media child
    INNER JOIN media parent ON child.origin_id = parent.id
    WHERE child.id = child_id;
END //

DELIMITER ;

-- Get the full processing chain (ancestors and descendants) for an image
DELIMITER //

CREATE OR REPLACE PROCEDURE get_processing_chain(IN image_id INT)
BEGIN
    -- First, find the root/original ancestor
    WITH RECURSIVE ancestors AS (
        SELECT id, origin_id, 0 as level
        FROM media
        WHERE id = image_id

        UNION ALL

        SELECT m.id, m.origin_id, a.level - 1
        FROM media m
        INNER JOIN ancestors a ON m.id = a.origin_id
    ),
    root AS (
        SELECT id FROM ancestors ORDER BY level ASC LIMIT 1
    ),
    -- Then get all descendants from that root
    descendants AS (
        SELECT m.*, 0 as depth, CAST(m.id AS CHAR(1000)) as path
        FROM media m
        WHERE m.id = (SELECT id FROM root)

        UNION ALL

        SELECT m.*, d.depth + 1, CONCAT(d.path, ' -> ', m.id)
        FROM media m
        INNER JOIN descendants d ON m.origin_id = d.id
    )
    SELECT
        id,
        storage_root,
        directory,
        filename,
        created,
        is_original,
        origin_id,
        is_final,
        rating,
        depth,
        path as processing_path
    FROM descendants
    ORDER BY depth ASC, created ASC;
END //

DELIMITER ;

-- Count children for each image
DELIMITER //

CREATE OR REPLACE PROCEDURE get_child_counts()
BEGIN
    SELECT
        m.id,
        m.filename,
        m.is_original,
        m.is_final,
        COUNT(children.id) as child_count
    FROM media m
    LEFT JOIN media children ON children.origin_id = m.id
    GROUP BY m.id, m.filename, m.is_original, m.is_final
    HAVING child_count > 0
    ORDER BY child_count DESC;
END //

DELIMITER ;

-- Find orphaned derivatives (derivatives whose parent no longer exists)
DELIMITER //

CREATE OR REPLACE PROCEDURE find_orphaned_derivatives()
BEGIN
    SELECT
        m.id,
        m.filename,
        m.origin_id as missing_parent_id
    FROM media m
    WHERE m.origin_id IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM media parent WHERE parent.id = m.origin_id
    );
END //

DELIMITER ;

-- =====================================================
-- Useful Queries (as comments for reference)
-- =====================================================

-- Find all parent-child pairs
-- SELECT
--     parent.id as parent_id,
--     parent.filename as parent_filename,
--     child.id as child_id,
--     child.filename as child_filename,
--     child.created as derivative_created
-- FROM media parent
-- INNER JOIN media child ON child.origin_id = parent.id
-- ORDER BY parent.id, child.created;

-- Find images with the most derivatives
-- SELECT
--     m.id,
--     m.filename,
--     COUNT(children.id) as derivative_count
-- FROM media m
-- INNER JOIN media children ON children.origin_id = m.id
-- GROUP BY m.id, m.filename
-- ORDER BY derivative_count DESC
-- LIMIT 20;

-- Find processing chains longer than 2 levels (original -> derivative -> derivative)
-- WITH RECURSIVE chains AS (
--     SELECT
--         id,
--         origin_id,
--         filename,
--         1 as depth,
--         CAST(id AS CHAR(1000)) as path
--     FROM media
--     WHERE is_original = TRUE
--
--     UNION ALL
--
--     SELECT
--         m.id,
--         m.origin_id,
--         m.filename,
--         c.depth + 1,
--         CONCAT(c.path, ' -> ', m.id)
--     FROM media m
--     INNER JOIN chains c ON m.origin_id = c.id
-- )
-- SELECT * FROM chains WHERE depth >= 3;

-- Get statistics about parent-child relationships
-- SELECT
--     'Total Images' as metric,
--     COUNT(*) as count
-- FROM media
-- UNION ALL
-- SELECT
--     'Original Images (no parent)',
--     COUNT(*)
-- FROM media WHERE is_original = TRUE
-- UNION ALL
-- SELECT
--     'Derivative Images (has parent)',
--     COUNT(*)
-- FROM media WHERE is_original = FALSE
-- UNION ALL
-- SELECT
--     'Final Images (no children)',
--     COUNT(*)
-- FROM media WHERE is_final = TRUE
-- UNION ALL
-- SELECT
--     'Originals with Derivatives',
--     COUNT(DISTINCT origin_id)
-- FROM media WHERE origin_id IS NOT NULL;

-- =====================================================
-- Example Usage
-- =====================================================

-- Get all children of image ID 12345
-- CALL get_children(12345);

-- Get the parent of image ID 67890
-- CALL get_parent(67890);

-- Get the full processing chain for image ID 12345
-- CALL get_processing_chain(12345);

-- Count children for all images
-- CALL get_child_counts();

-- Find any orphaned derivatives
-- CALL find_orphaned_derivatives();
