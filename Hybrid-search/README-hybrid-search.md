## Getting Started

### Prerequisites

- Postgres 17 or 18
- pg_textsearch extension
- pgvectorscale extension (which depends on pgvector)

### Option 1: Tiger Cloud (fastest path)

pg_textsearch and pgvectorscale are already installed on every Tiger Cloud service running Postgres 17+. No extension installation or server restart needed. Open a SQL editor in the [Tiger Cloud console](https://console.cloud.timescale.com) and continue to the next section.

### Option 2: Self-hosted

pg_textsearch requires listing in `shared_preload_libraries`, which needs a server restart:

```sql
-- postgresql.conf
shared_preload_libraries = 'pg_textsearch'
```

Download pre-built binaries for both extensions:
- pg_textsearch: [GitHub Releases](https://github.com/timescale/pg_textsearch/releases)
- pgvectorscale: [GitHub Releases](https://github.com/timescale/pgvectorscale/releases)

After restarting Postgres, create the extensions:

```sql
-- BM25 keyword search
CREATE EXTENSION pg_textsearch;

-- StreamingDiskANN vector search (CASCADE installs pgvector dependency)
CREATE EXTENSION vectorscale CASCADE;
```

---

## Step 1: Create a Table with Text and Embeddings

```sql
CREATE TABLE documents (
  id bigserial PRIMARY KEY,
  title text,
  content text,
  embedding vector(1536)  -- e.g. OpenAI text-embedding-3-small
);
```

Insert some sample data:

```sql
INSERT INTO documents (title, content) VALUES
  ('PostgreSQL Overview',
   'PostgreSQL is a powerful open source relational database system'),
  ('Search Technology',
   'Full text search enables finding relevant documents quickly'),
  ('Information Retrieval',
   'BM25 is a ranking function used by search engines to estimate relevance'),
  ('Database Indexing',
   'An index is a data structure that improves the speed of data retrieval');
```

In a real application, you would also populate the `embedding` column with vectors from an embedding model. See Raja Rao's [pg_textsearch_demo](https://github.com/rajaraodv/pg_textsearch_demo) for a working example with OpenAI embeddings.

---

## Step 2: Create Indexes

```sql
-- BM25 index for keyword search
CREATE INDEX docs_bm25_idx ON documents
  USING bm25(content) WITH (text_config = 'english');

-- StreamingDiskANN index for vector similarity search
CREATE INDEX docs_embedding_idx ON documents
  USING diskann (embedding vector_cosine_ops);
```

The `USING bm25` syntax creates a pg_textsearch BM25 index with English stemming and stopword removal.

The `USING diskann` syntax creates a pgvectorscale StreamingDiskANN index, which stores the graph on disk rather than requiring the entire index to fit in RAM. This is the key advantage over pgvector's built-in HNSW index for large embedding collections.

---

## Step 3: BM25 Keyword Search

The `<@>` operator returns a negative BM25 score. Scores are negated so that Postgres's default ascending `ORDER BY` returns the most relevant results first (a score of -15.3 is more relevant than -8.2):

```sql
SELECT title, content <@> 'database ranking' AS score
FROM documents
ORDER BY content <@> 'database ranking'
LIMIT 10;
```

You can combine BM25 ranking with standard `WHERE` clauses. The planner detects the `<@>` operator and uses the BM25 index automatically:

```sql
-- BM25 ranking with a filter
SELECT title, content <@> 'search' AS score
FROM documents
WHERE title ILIKE '%search%'
ORDER BY content <@> 'search'
LIMIT 10;
```

---

## Step 4: Vector Similarity Search

With embeddings populated and the StreamingDiskANN index in place, vector search uses the standard pgvector `<=>` operator for cosine distance:

```sql
-- $1 is the query embedding vector
SELECT title, embedding <=> $1 AS distance
FROM documents
ORDER BY embedding <=> $1
LIMIT 10;
```

---

## Step 5: Hybrid Search with Reciprocal Rank Fusion (RRF)

Reciprocal Rank Fusion combines results from multiple ranked lists by summing the reciprocal of each result's rank. It is simple, effective, and does not require score normalization:

```sql
WITH bm25_results AS (
  SELECT id, ROW_NUMBER() OVER (
    ORDER BY content <@> 'database optimization'
  ) AS rank
  FROM documents
  ORDER BY content <@> 'database optimization'
  LIMIT 20
),
vector_results AS (
  SELECT id, ROW_NUMBER() OVER (
    ORDER BY embedding <=> $1  -- $1 is the query embedding vector
  ) AS rank
  FROM documents
  ORDER BY embedding <=> $1
  LIMIT 20
)
SELECT
  d.id,
  d.title,
  COALESCE(1.0 / (60 + b.rank), 0)
    + COALESCE(1.0 / (60 + v.rank), 0) AS rrf_score
FROM documents d
LEFT JOIN bm25_results b ON d.id = b.id
LEFT JOIN vector_results v ON d.id = v.id
WHERE b.id IS NOT NULL OR v.id IS NOT NULL
ORDER BY rrf_score DESC
LIMIT 10;
```

**How RRF works:**

- The constant 60 is the standard smoothing parameter
- Each subquery retrieves the top 20 results from its respective index (BM25 or vector)
- Documents found by both searches get contributions from both ranks, pushing them higher
- The `COALESCE(..., 0)` handles documents that appear in only one result set

**Why this works for RAG:** Consider a RAG system searching technical documentation. A user asks about "error PG-1234 connection refused." BM25 finds documents containing the exact error code. Vector search finds documents about connection troubleshooting that use different terminology. RRF fuses both, and the document that both matches the error code and discusses the right fix ranks highest.

---

## Production Patterns

### Parallel index builds for large tables

```sql
SET max_parallel_maintenance_workers = 4;
SET maintenance_work_mem = '256MB';  -- minimum 64MB for parallel builds

CREATE INDEX ON large_table USING bm25(content)
  WITH (text_config = 'english');

-- pgvectorscale also supports parallel DiskANN builds
CREATE INDEX ON large_table
  USING diskann (embedding vector_cosine_ops);
```

### Indexing multiple columns

Each BM25 index covers a single text column. To search across multiple columns, create a generated column:

```sql
ALTER TABLE documents ADD COLUMN search_text text
  GENERATED ALWAYS AS (title || ' ' || content) STORED;

CREATE INDEX ON documents USING bm25(search_text)
  WITH (text_config = 'english');
```

### Phrase search workaround

pg_textsearch does not support native phrase queries in 1.0. Use a BM25 over-fetch with a post-filter:

```sql
SELECT * FROM (
  SELECT * FROM documents
  ORDER BY content <@> 'database system'
  LIMIT 100  -- over-fetch to compensate for post-filter
) sub
WHERE content ILIKE '%database system%'
LIMIT 10;
```

### Highlighting matched terms

Use Postgres's built-in `ts_headline()` for snippet generation:

```sql
SELECT title,
  ts_headline('english', content, to_tsquery('english', 'database')),
  content <@> 'database' AS score
FROM articles
ORDER BY content <@> 'database'
LIMIT 10;
```

### Tuning pgvectorscale accuracy

pgvectorscale's StreamingDiskANN index uses smart defaults. To fine-tune accuracy vs. speed at query time:

```sql
-- Higher values = more accurate, slightly slower
SET LOCAL diskann.query_rescore = 150;

SELECT * FROM documents
ORDER BY embedding <=> $1
LIMIT 10;
```

### Minimum relevance threshold

Filter out low-relevance BM25 results:

```sql
SELECT title, content <@> to_bm25query('database', 'docs_bm25_idx') AS score
FROM documents
WHERE content <@> to_bm25query('database', 'docs_bm25_idx') < -1.0
ORDER BY content <@> to_bm25query('database', 'docs_bm25_idx')
LIMIT 10;
```

### Compaction after bulk inserts

Sustained incremental inserts create multiple BM25 segments from repeated memtable spills. Consolidate for optimal query performance:

```sql
SELECT bm25_force_merge('docs_bm25_idx');
```

---

## Current Limitations

Things to be aware of in pg_textsearch 1.0:

- **No phrase queries**: The index stores term frequencies but not positions. Use the over-fetch + post-filter pattern shown above.
- **OR-only query semantics**: All query terms are implicitly OR'd. AND/OR/NOT operators are planned for a post-1.0 release.
- **No highlighting**: Use Postgres's `ts_headline()` on the result set.
- **Single column per index**: Use a generated column to combine multiple fields.
- **PL/pgSQL requires explicit index names**: Use `to_bm25query('query', 'index_name')` inside PL/pgSQL, DO blocks, or stored procedures.
- **shared_preload_libraries required**: Requires a server restart for self-hosted installations. Handled automatically on Tiger Cloud.

---

## What's Next

pg_textsearch 1.0 is the foundation. Boolean query operators (AND, OR, NOT), background compaction, and expression index support are planned for upcoming releases. For the full architecture and benchmark deep-dive, see [pg_textsearch 1.0: How We Built a BM25 Search Engine on Postgres Pages](link-to-part-1).

## Resources

- [pg_textsearch on GitHub](https://github.com/timescale/pg_textsearch)
- [pgvectorscale on GitHub](https://github.com/timescale/pgvectorscale)
- [pg_textsearch_demo](https://github.com/rajaraodv/pg_textsearch_demo) — working hybrid search demo with web UI
- [Tiger Cloud](https://www.tigerdata.com/search) — try it without any setup
- [Understanding DiskANN](https://www.tigerdata.com/blog/understanding-diskann)
- [It's 2026, Just Use Postgres](https://www.tigerdata.com/blog/its-2026-just-use-postgres)
- [You Don't Need Elasticsearch](https://www.tigerdata.com/blog/you-dont-need-elasticsearch-bm25-is-now-in-postgres)
