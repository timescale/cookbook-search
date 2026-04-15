# Hybrid Search

This cookbook demonstrates how to combine multiple search strategies in PostgreSQL for more relevant results — for example, pairing full-text search with vector similarity search.

## Overview

Hybrid search blends the strengths of different retrieval methods:

- **Full-text search** excels at exact keyword matching and linguistic features (stemming, ranking)
- **Vector similarity search** captures semantic meaning, finding results that are conceptually related even without keyword overlap

By combining them, you get results that are both keyword-accurate and semantically relevant.

## Getting Started

Before you can run the examples in this cookbook, you need a PostgreSQL database with a few extensions installed. There are two ways to do this — pick whichever fits your setup.

### What You'll Need

- **PostgreSQL 17 or 18** — This is the database itself. If you don't have it installed yet, you can download it from [postgresql.org](https://www.postgresql.org/download/) or use Tiger Cloud (see Option 1 below).
- **pg_textsearch** — A PostgreSQL extension that powers keyword search (also called BM25 search). Think of it like the search bar on a website: you type words, and it finds matching results.
- **pgvectorscale** — A PostgreSQL extension that powers vector search (also called semantic search). This finds results based on *meaning*, not just exact word matches. It depends on another extension called **pgvector**, which will be installed automatically.

### Option 1: Use Tiger Cloud (recommended for beginners)

This is the fastest way to get started — no installation required.

Tiger Cloud services running PostgreSQL 17+ already have pg_textsearch and pgvectorscale installed and ready to use. You just need to:

1. Sign up or log in at the [Tiger Cloud console](https://console.cloud.timescale.com)
2. Create a new service (or use an existing one running Postgres 17+)
3. Open the SQL editor in the console

That's it — you can skip ahead to the next section.

### Option 2: Use Docker (recommended for local development)

If you want to run everything locally without installing PostgreSQL or extensions by hand, use the [`timescaledb-docker-ha`](https://github.com/timescale/timescaledb-docker-ha) image. It ships with PostgreSQL, TimescaleDB, pgvector, pgvectorscale, and pg_textsearch pre-installed.

**Step 1: Pull and run the container**

```bash
docker run -d --name hybrid-search \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  timescale/timescaledb-ha:pg17
```

This starts a PostgreSQL 17 instance on port 5432. Change the password to something more secure if you plan to keep this running.

> **Apple Silicon note:** The image supports `arm64`, so it runs natively on M-series Macs — no Rosetta needed.

**Step 2: Connect to your database**

```bash
psql -h localhost -U postgres
```

Enter the password you set in Step 1 when prompted.

**Step 3: Create the extensions**

```sql
-- Install keyword search (BM25)
CREATE EXTENSION pg_textsearch;

-- Install vector search (this automatically installs pgvector too)
CREATE EXTENSION vectorscale CASCADE;
```

You should see `CREATE EXTENSION` printed after each command — that means it worked. You're all set!

> **Tip:** `shared_preload_libraries` is already configured in the Docker image, so there's no need to edit `postgresql.conf` or restart the server.

### Option 3: Run PostgreSQL on Your Own Machine (manual install)

If you prefer to run everything locally without Docker, you'll need to install the extensions yourself.

**Step 1: Download the extensions**

Download the pre-built packages from GitHub:
- pg_textsearch: [GitHub Releases](https://github.com/timescale/pg_textsearch/releases)
- pgvectorscale: [GitHub Releases](https://github.com/timescale/pgvectorscale/releases)

Follow the installation instructions included with each release for your operating system.

**Step 2: Update your PostgreSQL configuration**

pg_textsearch needs to be loaded when PostgreSQL starts up. Open your `postgresql.conf` file and add (or update) this line:

```
shared_preload_libraries = 'pg_textsearch'
```

> **Where is postgresql.conf?** The location varies by OS. You can find it by running `SHOW config_file;` in a SQL session, or check common locations like `/etc/postgresql/17/main/` (Linux) or `/usr/local/var/postgresql@17/` (macOS with Homebrew).

After saving the file, **restart PostgreSQL** for the change to take effect.

**Step 3: Create the extensions in your database**

Connect to your database and run:

```sql
-- Install keyword search (BM25)
CREATE EXTENSION pg_textsearch;

-- Install vector search (this automatically installs pgvector too)
CREATE EXTENSION vectorscale CASCADE;
```

You should see `CREATE EXTENSION` printed after each command — that means it worked. You're all set!

---

## Step 1: Create a Table with Text and Embeddings

This cookbook uses episode data from [Conduit](https://www.relay.fm/conduit), a productivity podcast by Jay Miller and Kathy Campbell on Relay FM. Transcripts are from the [conduit-transcripts](https://github.com/kjaymiller/conduit-transcripts) repo (MIT License, Jay Miller).

```sql
CREATE TABLE episodes (
  id bigserial PRIMARY KEY,
  title text,
  description text,
  pub_date date,
  url text,
  embedding vector(1536)  -- e.g. OpenAI text-embedding-3-small
);
```

Insert some sample data:

```sql
INSERT INTO episodes (title, description, pub_date, url) VALUES
  ('1: Our Systems: The Unicorn & Silk Sonic Methods',
   'For most people, productivity starts with their system. Jay and Kathy talk about their own brand of productivity and what their personal systems look like.',
   '2021-07-15', 'https://www.relay.fm/conduit/1'),
  ('5: Sustained Progress: Over Being Overwhelmed',
   'Millennial Falcon wants to know how to make SUSTAINED progress on projects that feel more like a marathon, not a sprint. Kathy just made a big move and gives us some of the tips that she used to make this challenge a bit more manageable.',
   '2021-09-09', 'https://www.relay.fm/conduit/5'),
  ('13: Happiness First, Productivity Second',
   'Kathy has lots to be thankful for, Jay is unfortunately unwell, but Rosemary was on standby! Time to review the end of the year and how you finish things or let them go, before getting started on the next new adventure.',
   '2021-12-30', 'https://www.relay.fm/conduit/13'),
  ('19: Eating the Devil''s Spaghetti: Combating Imposter Syndrome',
   'How do we learn to shut up and take the compliment? How about with a fresh bowl of imp-pasta!',
   '2022-03-24', 'https://www.relay.fm/conduit/19'),
  ('48: Long Projects: Remove the Concept of Time',
   'We''ve got a longer than usual period between our next live recording so we''re taking the time to think about some longer connections. Tune in to hear how we''re going about it and longer projects in general.',
   '2023-05-04', 'https://www.relay.fm/conduit/48'),
  ('57: I Need Help to Get the Help',
   'Kathy and Jay need help to meet the demands of those around them. They need help getting help!',
   '2023-09-07', 'https://www.relay.fm/conduit/57'),
  ('61: The Conduit Burnout Candle',
   'Kathy and Jay are feeling the burn(out) well maybe the steps before the burnout. We''ve taken blowtorches to our candles and now we''re telling you the warning signs we see that this next season might be a little tough.',
   '2023-11-02', 'https://www.relay.fm/conduit/61'),
  ('81: Brett''s Mental Health (and Tech) Corner',
   'Kathy is still on a secret mission so Jay is joined by Brett Terpstra the Internet''s mad scientist to talk mental health''s link to productivity.',
   '2024-08-08', 'https://www.relay.fm/conduit/81'),
  ('100: It''s Episode 100!!',
   'Grab your tissues, it''s our most guest filled episode ever. We also discuss what Conduit is, what it means to us, and how it has affected our lives.',
   '2025-05-01', 'https://www.relay.fm/conduit/100'),
  ('107: Bored as a Benefit',
   'Jay and Kathy explore the idea that boredom isn''t the enemy of productivity — it might actually be the secret ingredient.',
   '2025-08-07', 'https://www.relay.fm/conduit/107'),
  ('115: Productivity Inside Systems You Don''t Control',
   'Kathy is joined by the Nameless of the Show, Nameless, to talk about how to be productive when the system is one you don''t control.',
   '2025-11-21', 'https://www.relay.fm/conduit/115'),
  ('117: The Year to be Selfish',
   'Kathy and Jay discuss end-of-year planning. Kathy''s 2026 theme: "The Year to Be Selfish." Jay commits to boundaries and self-preservation. They cover nonprofit transitions and preparing for the annual systems check.',
   '2025-12-18', 'https://www.relay.fm/conduit/117');
```

In a real application, you would also populate the `embedding` column with vectors from an embedding model. See Raja Rao's [pg_textsearch_demo](https://github.com/rajaraodv/pg_textsearch_demo) for a working example with OpenAI embeddings.

---

## Step 2: Create Indexes

```sql
-- BM25 index for keyword search
CREATE INDEX episodes_bm25_idx ON episodes
  USING bm25(description) WITH (text_config = 'english');

-- StreamingDiskANN index for vector similarity search
CREATE INDEX episodes_embedding_idx ON episodes
  USING diskann (embedding vector_cosine_ops);
```

The `USING bm25` syntax creates a pg_textsearch BM25 index with English stemming and stopword removal.

The `USING diskann` syntax creates a pgvectorscale StreamingDiskANN index, which stores the graph on disk rather than requiring the entire index to fit in RAM. This is the key advantage over pgvector's built-in HNSW index for large embedding collections.

---

## Step 3: BM25 Keyword Search

The `<@>` operator returns a negative BM25 score. Scores are negated so that Postgres's default ascending `ORDER BY` returns the most relevant results first (a score of -15.3 is more relevant than -8.2):

```sql
SELECT title, description <@> 'burnout productivity' AS score
FROM episodes
ORDER BY description <@> 'burnout productivity'
LIMIT 10;
```

You can combine BM25 ranking with standard `WHERE` clauses. The planner detects the `<@>` operator and uses the BM25 index automatically:

```sql
-- BM25 ranking with a filter
SELECT title, description <@> 'help' AS score
FROM episodes
WHERE pub_date >= '2023-01-01'
ORDER BY description <@> 'help'
LIMIT 10;
```

---

## Step 4: Vector Similarity Search

With embeddings populated and the StreamingDiskANN index in place, vector search uses the standard pgvector `<=>` operator for cosine distance:

```sql
-- $1 is the query embedding vector
SELECT title, embedding <=> $1 AS distance
FROM episodes
ORDER BY embedding <=> $1
LIMIT 10;
```

---

## Step 5: Hybrid Search with Reciprocal Rank Fusion (RRF)

Reciprocal Rank Fusion combines results from multiple ranked lists by summing the reciprocal of each result's rank. It is simple, effective, and does not require score normalization:

```sql
WITH bm25_results AS (
  SELECT id, ROW_NUMBER() OVER (
    ORDER BY description <@> 'mental health boundaries'
  ) AS rank
  FROM episodes
  ORDER BY description <@> 'mental health boundaries'
  LIMIT 20
),
vector_results AS (
  SELECT id, ROW_NUMBER() OVER (
    ORDER BY embedding <=> $1  -- $1 is the query embedding vector
  ) AS rank
  FROM episodes
  ORDER BY embedding <=> $1
  LIMIT 20
)
SELECT
  d.id,
  d.title,
  COALESCE(1.0 / (60 + b.rank), 0)
    + COALESCE(1.0 / (60 + v.rank), 0) AS rrf_score
FROM episodes d
LEFT JOIN bm25_results b ON d.id = b.id
LEFT JOIN vector_results v ON d.id = v.id
WHERE b.id IS NOT NULL OR v.id IS NOT NULL
ORDER BY rrf_score DESC
LIMIT 10;
```

**How RRF works:**

- The constant 60 is the standard smoothing parameter
- Each subquery retrieves the top 20 results from its respective index (BM25 or vector)
- Episodes found by both searches get contributions from both ranks, pushing them higher
- The `COALESCE(..., 0)` handles documents that appear in only one result set

**Why this works for RAG:** Consider a RAG system searching a podcast archive. A user asks "how do I deal with feeling like a fraud at work?" BM25 finds the episode titled "Eating the Devil's Spaghetti: Combating Imposter Syndrome" because it matches "imposter" after stemming. Vector search finds episodes about burnout, boundaries, and mental health that are semantically related but use different words. RRF fuses both, surfacing the imposter syndrome episode at the top while also ranking related episodes about self-doubt and mental health higher.

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
ALTER TABLE episodes ADD COLUMN search_text text
  GENERATED ALWAYS AS (title || ' ' || description) STORED;

CREATE INDEX ON episodes USING bm25(search_text)
  WITH (text_config = 'english');
```

### Phrase search workaround

pg_textsearch does not support native phrase queries in 1.0. Use a BM25 over-fetch with a post-filter:

```sql
SELECT * FROM (
  SELECT * FROM episodes
  ORDER BY description <@> 'year end planning'
  LIMIT 100  -- over-fetch to compensate for post-filter
) sub
WHERE description ILIKE '%end-of-year%'
LIMIT 10;
```

### Highlighting matched terms

Use Postgres's built-in `ts_headline()` for snippet generation:

```sql
SELECT title,
  ts_headline('english', description, to_tsquery('english', 'productivity')),
  description <@> 'productivity' AS score
FROM episodes
ORDER BY description <@> 'productivity'
LIMIT 10;
```

### Tuning pgvectorscale accuracy

pgvectorscale's StreamingDiskANN index uses smart defaults. To fine-tune accuracy vs. speed at query time:

```sql
-- Higher values = more accurate, slightly slower
SET LOCAL diskann.query_rescore = 150;

SELECT * FROM episodes
ORDER BY embedding <=> $1
LIMIT 10;
```

### Minimum relevance threshold

Filter out low-relevance BM25 results:

```sql
SELECT title, description <@> to_bm25query('burnout', 'episodes_bm25_idx') AS score
FROM episodes
WHERE description <@> to_bm25query('burnout', 'episodes_bm25_idx') < -1.0
ORDER BY description <@> to_bm25query('burnout', 'episodes_bm25_idx')
LIMIT 10;
```

### Compaction after bulk inserts

Sustained incremental inserts create multiple BM25 segments from repeated memtable spills. Consolidate for optimal query performance:

```sql
SELECT bm25_force_merge('episodes_bm25_idx');
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
