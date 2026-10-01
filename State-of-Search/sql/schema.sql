CREATE TABLE IF NOT EXISTS events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at timestamptz NOT NULL,
  service text NOT NULL,
  environment text NOT NULL,
  severity text NOT NULL,
  event_type text NOT NULL,
  region text,
  error_code text,
  incident_id text,
  content text NOT NULL,
  metadata jsonb
);

CREATE TABLE IF NOT EXISTS deployments (
  deploy_id text PRIMARY KEY,
  deployed_at timestamptz NOT NULL,
  service text NOT NULL,
  environment text NOT NULL,
  version text NOT NULL,
  previous_version text,
  git_sha text,
  deployer text,
  strategy text,
  status text,
  duration_seconds integer,
  change_summary text,
  metadata jsonb
);

CREATE TABLE IF NOT EXISTS source_documents (
  doc_id text PRIMARY KEY,
  doc_type text NOT NULL,
  title text NOT NULL,
  section text NOT NULL,
  service text,
  incident_family text,
  incident_id text,
  published_at timestamptz,
  content text NOT NULL
);

CREATE TABLE IF NOT EXISTS labeled_questions (
  question_id integer PRIMARY KEY,
  question text NOT NULL,
  query_kind text,
  expected_family text,
  expected_incident_ids text[],
  expected_services text[],
  notes text
);

-- One retrieval corpus keeps every method on identical rows.
CREATE TABLE IF NOT EXISTS search_items (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source_kind text NOT NULL,
  source_id text NOT NULL,
  title text NOT NULL,
  content text NOT NULL,
  service text,
  incident_id text,
  incident_family text,
  occurred_at timestamptz,
  environment text,
  region text,
  severity text,
  error_code text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding vector(1536),
  embedding_model text,
  content_tsv tsvector GENERATED ALWAYS AS
    (to_tsvector('english'::regconfig, title || ' ' || content)) STORED,
  UNIQUE (source_kind, source_id)
);

-- Separate thin tables make it possible to force a specific ANN access method
-- without relying on planner preference when several indexes share a column.
CREATE TABLE IF NOT EXISTS vectors_hnsw (
  item_id bigint PRIMARY KEY REFERENCES search_items(id) ON DELETE CASCADE,
  embedding vector(1536) NOT NULL
);

CREATE TABLE IF NOT EXISTS vectors_ivfflat (
  item_id bigint PRIMARY KEY REFERENCES search_items(id) ON DELETE CASCADE,
  embedding vector(1536) NOT NULL
);

CREATE TABLE IF NOT EXISTS vectors_diskann (
  item_id bigint PRIMARY KEY REFERENCES search_items(id) ON DELETE CASCADE,
  embedding vector(1536) NOT NULL
);

CREATE TABLE IF NOT EXISTS query_embeddings (
  query text PRIMARY KEY,
  embedding vector(1536) NOT NULL,
  model text NOT NULL,
  embedded_at timestamptz NOT NULL DEFAULT now()
);
