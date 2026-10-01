DROP INDEX IF EXISTS
  vectors_hnsw_idx,
  vectors_ivfflat_idx,
  vectors_diskann_idx;

TRUNCATE TABLE
  query_embeddings,
  vectors_diskann,
  vectors_ivfflat,
  vectors_hnsw,
  search_items,
  labeled_questions,
  source_documents,
  deployments,
  events
RESTART IDENTITY CASCADE;
