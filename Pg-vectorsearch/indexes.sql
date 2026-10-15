-- Search indexes for the Tiger Cloud pg_vectorsearch cookbook.
-- Run after load.py and embed.py:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f indexes.sql

-- 1. Time and metadata filters
CREATE INDEX IF NOT EXISTS incident_events_time_idx
  ON incident_events (occurred_at DESC);

CREATE INDEX IF NOT EXISTS incident_events_service_time_idx
  ON incident_events (service, occurred_at DESC);

CREATE INDEX IF NOT EXISTS incident_events_incident_idx
  ON incident_events (incident_id)
  WHERE incident_id IS NOT NULL;

-- 2. PostgreSQL full-text search
CREATE INDEX IF NOT EXISTS incident_events_tsv_idx
  ON incident_events USING gin (content_tsv);

-- 3. PRISM approximate nearest-neighbor search
-- vec32_cosine_ops matches the <=> cosine-distance operator used by search.py.
CREATE INDEX IF NOT EXISTS incident_events_embedding_prism_idx
  ON incident_events USING prism (embedding vec32_cosine_ops);
