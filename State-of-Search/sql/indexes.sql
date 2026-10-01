-- Relational, fuzzy, and native PostgreSQL full-text search.
CREATE INDEX IF NOT EXISTS search_items_time_idx
  ON search_items (occurred_at DESC);
CREATE INDEX IF NOT EXISTS search_items_service_time_idx
  ON search_items (service, occurred_at DESC);
CREATE INDEX IF NOT EXISTS search_items_error_code_idx
  ON search_items (error_code) WHERE error_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS search_items_family_idx
  ON search_items (incident_family) WHERE incident_family IS NOT NULL;
CREATE INDEX IF NOT EXISTS search_items_metadata_idx
  ON search_items USING gin (metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS search_items_trgm_idx
  ON search_items USING gin ((title || ' ' || content) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS search_items_fts_idx
  ON search_items USING gin (content_tsv);

-- BM25 can be built as soon as text is loaded. `doctor` shows exactly which
-- methods are present; the demo never substitutes one method for another.
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'bm25') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS search_items_bm25_idx '
         || 'ON search_items USING bm25 (content) '
         || 'WITH (text_config=''english'')';
  END IF;

END
$block$;

ANALYZE search_items;
