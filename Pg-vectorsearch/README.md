# Semantic Incident Search with pg_vectorsearch on Tiger Cloud

Build a PostgreSQL-native semantic search workflow with `pg_vectorsearch` and
its PRISM approximate nearest-neighbor index, hosted entirely in Tiger Cloud.

## Overview

This cookbook loads 1,200 deterministic events from a fictional e-commerce
platform, generates embeddings with OpenAI, and searches them with cosine
distance. The database, vector type, and PRISM index run in Tiger Cloud; you do
not need Docker or a local PostgreSQL extension build.

The example is adapted from the in-progress `Incident-search` tutorial's
synthetic *tigerlily* SRE dataset. By the end, you will have a reproducible
dataset, a `vec32(1536)` embedding column, a PRISM index, and a Python search
command that can inspect its PostgreSQL query plan.

PRISM is an IVF-style approximate nearest-neighbor (ANN) index. It groups
similar vectors into partitions, scans the most promising partitions, and
reranks candidates against full-precision vectors. This makes it possible to
search for meaning—such as “database connections are exhausted”—even when the
stored event uses different wording.

## Getting Started

### What You'll Need

- **A Tiger Cloud account** — [sign up or log in](https://console.cloud.timescale.com/) and create a PostgreSQL 18 service where `pg_vectorsearch` is available.
- **PostgreSQL 18 with pg_vectorsearch** — the extension currently requires PostgreSQL 18 or later and is alpha software. The verification below checks availability before changing the database.
- **Python 3.10+** — runs the data loader, embedding script, and search CLI. Download it from [python.org](https://www.python.org/downloads/).
- **psql** — runs the SQL files against Tiger Cloud. Install it from the [PostgreSQL downloads page](https://www.postgresql.org/download/), or use Tiger Cloud's SQL editor for SQL-only steps.
- **An OpenAI API key** — generates 1,536-dimensional embeddings with `text-embedding-3-small`. Create one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
- **uv** — this tutorial uses [uv](https://docs.astral.sh/uv/) to manage Python packages. [pip](https://pip.pypa.io/) and [conda](https://docs.conda.io/) also work.

### Option 1: Create a Tiger Cloud service (recommended)

1. Open the [Tiger Cloud console](https://console.cloud.timescale.com/).
2. Create a PostgreSQL 18 service that includes `pg_vectorsearch`.
3. When the service is running, copy its connection string and save the
   password shown by the console. The connection string should use TLS with
   `sslmode=require`.

**Check that pg_vectorsearch is available** — replace the example URL with the
connection string from Tiger Cloud:

```bash
psql "postgresql://tsdbadmin:YOUR_PASSWORD@YOUR_HOST:5432/tsdb?sslmode=require" \
  -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'pg_vectorsearch';"
```

You should see one row named `pg_vectorsearch`. If the query returns no rows,
that service does not have the extension installed; use a PostgreSQL 18 Tiger
Cloud service where it is available or contact Tiger Data support before
continuing.

### Option 2: Use an existing Tiger Cloud service

An existing service works when it runs PostgreSQL 18 or later and lists
`pg_vectorsearch` in `pg_available_extensions`. The cookbook creates its own
`incident_events` table and does not alter other application tables.

**Check the server and extension** — run both checks before using an existing
service:

```bash
psql "$DATABASE_URL" -c "SHOW server_version;"
psql "$DATABASE_URL" \
  -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'pg_vectorsearch';"
```

The first command should report PostgreSQL 18 or later, and the second should
return one extension row. You are now ready to configure the local scripts.

## Step 1: Configure the Connection

Keep credentials in a local `.env` file. The repository ignores `.env`, while
`.env.example` documents every required setting.

**Create your local configuration** — copy the template:

```bash
cd Pg-vectorsearch
cp .env.example .env
```

The command creates `Pg-vectorsearch/.env`. Open it in your editor and replace
both placeholders.

**Set the Tiger Cloud and OpenAI credentials** — keep TLS enabled in the
connection string:

```dotenv
DATABASE_URL=postgresql://tsdbadmin:your-password@your-host:5432/tsdb?sslmode=require
OPENAI_API_KEY=your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Do not commit this file or paste its contents into logs or screenshots.

**Verify the saved connection** — load `.env` in your shell without printing
its values, then ask PostgreSQL for the current user and database:

```bash
set -a
source .env
set +a
psql "$DATABASE_URL" -c "SELECT current_user, current_database();"
```

You should see your Tiger Cloud role (normally `tsdbadmin`) and database. With
the secure connection working, the next step installs the local Python tools.

## Step 2: Install the Python Dependencies

uv creates an isolated `.venv` and installs the three packages listed in
`requirements.txt`. You do not need to activate the environment when using
`uv run`.

**Create the environment** — install the pinned dependency ranges:

```bash
uv venv
uv pip install -r requirements.txt
```

You should see uv complete without dependency errors.

**Verify imports** — make sure every runtime package is available:

```bash
uv run python -c "import openai, psycopg, dotenv; print('Python dependencies ready')"
```

The command should print `Python dependencies ready`. Next, create the vector
type and table in Tiger Cloud.

## Step 3: Create the Extension and Table

`pg_vectorsearch` supplies the native `vec32` type and the PRISM index access
method. This example uses `vec32(1536)` because
`text-embedding-3-small` returns exactly 1,536 floating-point values.

**Run the idempotent schema setup** — create the extension and table:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f setup.sql
```

You should see `CREATE EXTENSION`, `CREATE TABLE`, and `ALTER TABLE` on the first
run. `NOTICE` messages saying objects already exist are safe on later runs.

**Verify the installed version and vector column** — inspect the extension and
schema:

```bash
psql "$DATABASE_URL" -P pager=off -c "
SELECT pg_vectorsearch_version();
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'incident_events' AND column_name = 'embedding';"
```

The first result reports the installed extension version. The second identifies
the embedding column as `vec32`. Now the table is ready for sample events.

## Step 4: Generate and Load Incident Events

The sample models logs from the fictional *tigerlily* e-commerce platform. It
contains ten incident families—including database pool exhaustion, expired TLS
certificates, worker OOMs, and Kafka lag—mixed with routine operational noise.
No real people, customers, or vendors appear in the data.
The generator and its output are provided under this repository's Apache 2.0
license.

`generate_data.py` uses a fixed random seed, so the same row count always
produces the same records. `load.py` generates the rows in memory and sends
them directly to Tiger Cloud.

**Load the default sample** — create 1,200 events:

```bash
uv run python load.py
```

On the first run, you should see `Done! Loaded 1,200 events.` Repeating the
command preserves the existing rows and explains how to replace them.

**Check the data distribution** — confirm the total and incident counts:

```bash
psql "$DATABASE_URL" -P pager=off -c "
SELECT count(*) AS total_events,
       count(*) FILTER (WHERE incident_id IS NOT NULL) AS incident_events,
       count(DISTINCT incident_family) AS incident_families
FROM incident_events;"
```

The expected result is 1,200 total events, 50 incident events, and 10 incident
families. The vectors are still empty, so the next step gives every event a
semantic representation.

## Step 5: Generate Embeddings

An embedding is a numeric representation of text. Similar meanings land near
one another in vector space, which lets a query about “workers running out of
memory” find an event containing `OOMKilled` even when the words do not match.

The script sends event text to OpenAI in batches and stores the result as
`vec32`. It skips rows that already have an embedding, so interrupted runs can
resume without paying to embed completed rows again.

**Embed every event** — this makes billable OpenAI API calls:

```bash
uv run python embed.py
```

Progress is printed after each batch, ending with
`Done! Added 1,200 embeddings.` The exact API cost depends on current OpenAI
pricing and the generated text length.

**Verify vector coverage and dimensions** — all rows should be populated:

```bash
psql "$DATABASE_URL" -P pager=off -c "
SELECT count(*) AS events,
       count(embedding) AS embedded_events,
       min(vec32_dims(embedding)) AS dimensions
FROM incident_events;"
```

You should see 1,200 events, 1,200 embedded events, and 1,536 dimensions. With
vectors loaded, PRISM can train partitions from the actual data distribution.

## Step 6: Build the PRISM Index

PRISM is a partitioned ANN index. Unlike an exact scan, it searches selected
vector partitions and reranks the strongest candidates, trading a small amount
of recall for much less work at large scale. Build it after loading embeddings
because its automatic sizing uses the table's row count.

**Create every search index** — add filter, full-text, and PRISM indexes:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f indexes.sql
```

You should see four `CREATE INDEX` results on the first run.

**Verify the PRISM access method** — inspect the catalog directly:

```bash
psql "$DATABASE_URL" -P pager=off -c "
SELECT c.relname AS index_name, a.amname AS access_method
FROM pg_class AS c
JOIN pg_am AS a ON a.oid = c.relam
WHERE c.relname = 'incident_events_embedding_prism_idx';"
```

The result should list `incident_events_embedding_prism_idx` with access method
`prism`. The sample is intentionally small, so PostgreSQL may still choose a
sequential scan for some queries; at larger sizes the index becomes the cheaper
plan.

**What PRISM is good at:** large embedding collections where HNSW's graph size,
memory use, or build time is a constraint.

**Where it falls short:** this alpha release still needs manual maintenance
after heavy churn, and tiny tables may be faster to scan exactly.

The index is ready, so you can now search the sample in plain language.

## Step 7: Search by Meaning

`search.py` embeds your question with the same model used for stored events,
then orders rows with cosine distance (`<=>`). It prints cosine similarity,
incident metadata, and the matched content.

**Search for a database incident** — use wording that differs from the stored
events:

```bash
uv run python search.py "why are checkout database connections exhausted?"
```

The leading results should mention checkout timeouts, `max_connections`, or
`SQLSTATE 53300` and identify the `db_pool_exhaustion` family.

**Search within one service** — combine vector ranking with a PostgreSQL filter:

```bash
uv run python search.py "certificate renewal failed" --service edge-proxy
```

The best matches should identify `tls_cert_expiry` and the blocked ACME
challenge path. Keeping vectors next to metadata is useful because filters,
joins, and similarity ranking all stay in one SQL query.

**Inspect the plan** — ask PostgreSQL to execute and explain the vector query:

```bash
uv run python search.py "worker pods keep running out of memory" --explain
```

Look for `incident_events_embedding_prism_idx` in the plan. If PostgreSQL picks
a sequential scan on this 1,200-row table, that is a cost-based choice rather
than a missing index; the catalog check in Step 6 confirms the index exists.

**What semantic search is good at:** matching concepts expressed with different
vocabulary and retrieving related symptoms from noisy operational text.

**Where it falls short:** exact identifiers can be diluted by semantic ranking,
and a result's similarity does not prove that it caused an incident. The next
step uses PostgreSQL full-text search for literal evidence.

## Step 8: Compare Exact Keyword Search

Full-text search is a useful complement to vector search for error codes,
identifiers, and exact phrases. The generated `content_tsv` column and GIN
index are maintained automatically by PostgreSQL.

**Find an exact SQLSTATE** — query the stored text without an embedding API
call:

```bash
psql "$DATABASE_URL" -P pager=off -c "
SELECT occurred_at, service, incident_id, content
FROM incident_events
WHERE content_tsv @@ websearch_to_tsquery('english', 'SQLSTATE 53300');"
```

You should see the database pool exhaustion event containing `SQLSTATE 53300`.
Keyword search is precise here, but a phrase such as “database capacity ran
out” may not match; semantic search handles that paraphrase.

**Find Kubernetes terminology** — search for the literal failure modes:

```bash
psql "$DATABASE_URL" -P pager=off -c "
SELECT service, incident_id, content
FROM incident_events
WHERE content_tsv @@ websearch_to_tsquery('english', 'OOMKilled OR CrashLoopBackOff');"
```

The result should point to the embedding worker incident. You now have both
semantic and exact retrieval paths over the same Tiger Cloud table.

## Step 9: Tune Recall and Inspect PRISM

`prism.nprobe` controls how many nearby partitions a query scans. Its default
value of `0` selects an automatic setting targeting roughly 0.95 recall@10.
Increasing it can improve recall at the cost of latency; lowering it can favor
throughput.

**Run one higher-recall query** — set `nprobe` only for this transaction:

```bash
uv run python search.py "what blocked inventory writes?" --nprobe 40 --explain
```

The results should identify the `migration_lock` family. The query plan reports
how PostgreSQL executed the request.

**Inspect resolved index settings** — see the values PRISM chose at build time:

```bash
psql "$DATABASE_URL" -P pager=off \
  -c "SELECT * FROM prism_index_settings('incident_events_embedding_prism_idx');"
```

You should see settings including the vector dimension, cosine metric, number
of lists, and effective `nprobe`. Keep the automatic defaults until recall and
latency measurements justify a change.

## Going Further

The tutorial above covers the core pattern. These recipes extend it without
changing the basic Tiger Cloud architecture.

### Load a Larger Deterministic Sample

A larger table makes the planner's index choice and PRISM's behavior easier to
observe. Replacing data also clears embeddings, so repeat Steps 5 and 6 after
loading.

**Replace the sample with 10,000 rows** — generate a larger dataset with the
same seed:

```bash
uv run python load.py --rows 10000 --truncate
uv run python embed.py
psql "$DATABASE_URL" -c "REINDEX INDEX incident_events_embedding_prism_idx;"
```

The loader reports 10,000 rows, the embedder fills every vector, and `REINDEX`
rebuilds PRISM from the new distribution.

### Generate a Reviewable CSV

The loader does not need a local data file, but the generator can write one for
inspection or modification.

**Export generated events** — create a Git-ignored CSV:

```bash
uv run python generate_data.py --rows 1200 --output sample_data/events.csv
```

The command reports the output path and row count. Repeating it with the same
arguments produces the same logical records.

### Maintain a Growing Index

PRISM accepts inserts and updates, but heavy ingestion can make partitions
uneven. Rebalance oversized lists in place, or use `REINDEX` when you want a
complete rebuild.

**Rebalance the cookbook index** — run the maintenance procedure after a large
append:

```bash
psql "$DATABASE_URL" \
  -c "CALL prism_rebalance('incident_events_embedding_prism_idx');"
```

PostgreSQL should report `CALL`. Measure recall before and after maintenance on
your own workload rather than scheduling it blindly.

### Start Over Without Deleting the Cloud Service

Dropping the cookbook table removes its data and indexes while leaving the
Tiger Cloud service and extension available for other databases.

**Remove cookbook data** — this is destructive and cannot be undone without a
backup:

```sql
DROP TABLE IF EXISTS incident_events;
```

PostgreSQL should report `DROP TABLE`. Run `setup.sql`, `load.py`, `embed.py`,
and `indexes.sql` to recreate the example.

## Current Limitations

- **Alpha extension:** `pg_vectorsearch` is intended for testing, not production. Upgrades between prereleases may require recreating the extension and indexes.
- **PostgreSQL version:** the extension requires PostgreSQL 18 or later.
- **Small demonstration dataset:** 1,200 rows teach the workflow but do not represent large-scale benchmark performance; the planner may prefer a sequential scan.
- **Manual maintenance under churn:** inserts, updates, and deletes work, but heavy changes can require `prism_rebalance` or `REINDEX`.
- **OpenAI dependency:** embedding and query generation require network access, an API key, and incur usage charges.
- **Post-filter behavior:** selective `WHERE` filters are applied after ANN candidates are produced and can return fewer rows than requested when vector proximity and the filter are poorly correlated.

## What's Next

- **Measure recall** — generate exact nearest-neighbor ground truth and compare it with several `prism.nprobe` values.
- **Expand the dataset** — add incident families and routine templates to `generate_data.py`, then regenerate and re-embed the sample.
- **Add hybrid ranking** — combine semantic results with PostgreSQL full-text scores using Reciprocal Rank Fusion.
- **Integrate an application** — call the parameterized query in `search.py` from an API, support tool, or incident-response interface.
- **Use existing pgvector data** — install `pg_vectorsearch` beside `vector` and build PRISM directly on compatible `vector` or `halfvec` columns without rewriting them.

## Resources

- [pg_vectorsearch on GitHub](https://github.com/timescale/pg_vectorsearch) — extension source, SQL usage, status, and build documentation.
- [pg_vectorsearch tuning guide](https://github.com/timescale/pg_vectorsearch/blob/main/docs/tuning.md) — `nprobe`, index parameters, query behavior, and inspection functions.
- [Announcing pg_vectorsearch](https://www.tigerdata.com/blog/announcing-pg_vectorsearch-scalable-open-source-vector-search-postgresql) — PRISM design, benchmark context, and current limitations.
- [Tiger Cloud](https://www.tigerdata.com/cloud) — managed PostgreSQL for the database used by this cookbook.
- [Tiger Cloud connection details](https://www.tigerdata.com/docs/use-timescale/latest/integrations/find-connection-details) — where to find the host, port, database, user, and password.
- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings) — embedding concepts and API usage.
