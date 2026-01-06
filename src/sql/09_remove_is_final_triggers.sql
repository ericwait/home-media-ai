-- =====================================================
-- Remove Triggers causing OperationalError
-- =====================================================
-- The triggers maintain_is_final_on_insert/update/delete
-- cause "Can't update table 'media'..." errors during import
-- because they attempt to update the same table involved
-- in the triggering statement.
--
-- We will rely on periodic calls to update_is_final() instead.
-- =====================================================

DROP TRIGGER IF EXISTS maintain_is_final_on_insert;
DROP TRIGGER IF EXISTS maintain_is_final_on_update;
DROP TRIGGER IF EXISTS maintain_is_final_on_delete;
