-- =====================================================
-- Migration Script
-- =====================================================
-- Migrate existing wfo_versions and plant_taxonomy
-- tables into the new normalized schema.
-- =====================================================

-- Create WFO taxonomy entry if it doesn't exist
INSERT IGNORE INTO taxonomies (name, description, source)
VALUES (
    'World Flora Online',
    'WFO Backbone - comprehensive plant taxonomy',
    'https://www.worldfloraonline.org/'
);

-- Migrate wfo_versions -> taxonomy_versions
INSERT INTO taxonomy_versions (
    taxonomy_id,
    downloaded_at,
    file_name,
    file_size,
    checksum,
    notes
)
SELECT 
    (SELECT id FROM taxonomies WHERE name = 'World Flora Online'),
    wv.downloaded_at,
    wv.file_name,
    wv.file_size,
    wv.checksum,
    wv.notes
FROM wfo_versions wv
WHERE NOT EXISTS (
    SELECT 1 FROM taxonomy_versions tv 
    WHERE tv.checksum = wv.checksum
);

-- Migrate plant_taxonomy -> taxonomy_nodes
-- This populates the hierarchical structure
INSERT INTO taxonomy_nodes (
    taxonomy_id,
    parent_id,
    external_id,
    name,
    rank,
    status,
    metadata
)
SELECT 
    (SELECT id FROM taxonomies WHERE name = 'World Flora Online'),
    NULL,  -- Will need second pass to resolve parent_id
    pt.taxon_id,
    pt.scientific_name,
    pt.taxon_rank,
    pt.taxonomic_status,
    JSON_OBJECT(
        'authorship', pt.authorship,
        'family', pt.family,
        'genus', pt.genus,
        'source_references', pt.source_references,
        'source', pt.source,
        'major_group', pt.major_group,
        'created', pt.created,
        'modified', pt.modified
    )
FROM plant_taxonomy pt
WHERE NOT EXISTS (
    SELECT 1 FROM taxonomy_nodes tn 
    WHERE tn.external_id = pt.taxon_id
);

-- Second pass: resolve parent relationships
UPDATE taxonomy_nodes tn
JOIN plant_taxonomy pt ON tn.external_id = pt.taxon_id
JOIN taxonomy_nodes parent ON parent.external_id = pt.parent_id
SET tn.parent_id = parent.id
WHERE pt.parent_id IS NOT NULL
  AND tn.parent_id IS NULL;

-- Verify migration counts
SELECT 
    'taxonomies' AS table_name,
    COUNT(*) AS row_count
FROM taxonomies
UNION ALL
SELECT 'taxonomy_versions', COUNT(*) FROM taxonomy_versions
UNION ALL
SELECT 'taxonomy_nodes', COUNT(*) FROM taxonomy_nodes;
