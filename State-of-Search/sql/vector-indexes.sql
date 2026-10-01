-- Build ANN indexes only after embeddings and the method tables are populated.
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'hnsw') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS vectors_hnsw_idx '
         || 'ON vectors_hnsw USING hnsw (embedding vector_cosine_ops)';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'ivfflat') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS vectors_ivfflat_idx '
         || 'ON vectors_ivfflat USING ivfflat (embedding vector_cosine_ops) '
         || 'WITH (lists = 100)';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_am WHERE amname = 'diskann') THEN
    EXECUTE 'CREATE INDEX IF NOT EXISTS vectors_diskann_idx '
         || 'ON vectors_diskann USING diskann (embedding vector_cosine_ops)';
  END IF;

END
$block$;

ANALYZE vectors_hnsw;
ANALYZE vectors_ivfflat;
ANALYZE vectors_diskann;
