-- =====================================================
-- Useful Queries for Home Media AI
-- =====================================================
-- Common queries for exploring taxonomy and media data.
-- =====================================================

-- ==================
-- Taxonomy Queries
-- ==================

-- Get taxonomy hierarchy for a specific taxon (recursive CTE)
WITH RECURSIVE taxon_path AS (
    SELECT 
        id,
        parent_id,
        name,
        rank,
        external_id,
        0 AS depth
    FROM taxonomy_nodes
    WHERE external_id = 'wfo-0000000001'  -- Replace with your taxon
    
    UNION ALL
    
    SELECT 
        tn.id,
        tn.parent_id,
        tn.name,
        tn.rank,
        tn.external_id,
        tp.depth + 1
    FROM taxonomy_nodes tn
    JOIN taxon_path tp ON tn.parent_id = tp.id
)
SELECT 
    CONCAT(REPEAT('  ', depth), name) AS hierarchy,
    rank,
    external_id
FROM taxon_path
ORDER BY depth;

-- Count taxa by rank for each taxonomy
SELECT 
    t.name AS taxonomy,
    tn.rank,
    COUNT(*) AS count
FROM taxonomy_nodes tn
JOIN taxonomies t ON tn.taxonomy_id = t.id
GROUP BY t.name, tn.rank
ORDER BY t.name, count DESC;

-- Find all children of a genus
SELECT 
    tn.name,
    tn.rank,
    tn.status,
    JSON_UNQUOTE(JSON_EXTRACT(tn.metadata, '$.family')) AS family
FROM taxonomy_nodes tn
WHERE tn.parent_id = (
    SELECT id FROM taxonomy_nodes WHERE name = 'Carex' LIMIT 1
)
ORDER BY tn.name;

-- ==================
-- Media Queries
-- ==================

-- Find all RAW files with their derivatives
SELECT
    CONCAT(original.storage_root, '/', original.directory, '/', original.filename) AS raw_file,
    original.file_hash AS raw_hash,
    COUNT(derivative.id) AS derivative_count,
    GROUP_CONCAT(derivative.file_ext) AS derivative_formats
FROM media original
LEFT JOIN media derivative ON derivative.origin_id = original.id
WHERE original.is_original = TRUE
GROUP BY original.id, original.storage_root, original.directory, original.filename, original.file_hash
ORDER BY derivative_count DESC;

-- Find orphaned derivatives (derivatives without originals)
SELECT
    m.id,
    CONCAT(m.storage_root, '/', m.directory, '/', m.filename) AS file_path,
    m.file_ext,
    m.origin_id
FROM media m
WHERE m.is_original = FALSE
  AND m.origin_id IS NULL;

-- Media files by type and size
SELECT 
    mt.name AS media_type,
    COUNT(*) AS file_count,
    SUM(m.file_size) / (1024*1024*1024) AS total_gb,
    AVG(m.file_size) / (1024*1024) AS avg_mb
FROM media m
JOIN media_types mt ON m.media_type_id = mt.id
GROUP BY mt.name
ORDER BY total_gb DESC;

-- ==================
-- Linking Queries
-- ==================

-- Find media linked to a specific taxon (and its children)
WITH RECURSIVE taxon_tree AS (
    SELECT id FROM taxonomy_nodes WHERE name = 'Cyperaceae'
    UNION ALL
    SELECT tn.id FROM taxonomy_nodes tn
    JOIN taxon_tree tt ON tn.parent_id = tt.id
)
SELECT
    CONCAT(m.storage_root, '/', m.directory, '/', m.filename) AS file_path,
    tn.name AS taxon_name,
    tn.rank,
    mtl.confidence,
    mtl.assigned_by
FROM media_taxonomy_links mtl
JOIN media m ON mtl.media_id = m.id
JOIN taxonomy_nodes tn ON mtl.taxonomy_node_id = tn.id
WHERE tn.id IN (SELECT id FROM taxon_tree)
ORDER BY mtl.confidence DESC;

-- Find unlinked media files
SELECT
    m.id,
    CONCAT(m.storage_root, '/', m.directory, '/', m.filename) AS file_path,
    m.file_ext,
    m.created
FROM media m
LEFT JOIN media_taxonomy_links mtl ON m.id = mtl.media_id
WHERE mtl.id IS NULL
  AND m.is_original = TRUE
ORDER BY m.created DESC;

-- Taxa with most associated media
SELECT 
    tn.name,
    tn.rank,
    COUNT(DISTINCT mtl.media_id) AS media_count,
    AVG(mtl.confidence) AS avg_confidence
FROM taxonomy_nodes tn
JOIN media_taxonomy_links mtl ON tn.id = mtl.taxonomy_node_id
GROUP BY tn.id, tn.name, tn.rank
ORDER BY media_count DESC
LIMIT 20;
