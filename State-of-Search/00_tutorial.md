# Tutorial: Build the State of Search Demo

This tutorial is both a learning path and an executable preparation script. It
starts with ordinary PostgreSQL search, adds modern lexical and semantic
indexes, combines them, and finally asks whether Elasticsearch should become a
second retrieval system.

## 1. Configure the environment

```bash
cd State-of-Search
cp .env.example .env
```

Set these values in `.env`:

```dotenv
OPENAI_API_KEY=your-key-here
DATASET_PROFILE=sample
```

`sample` is intentionally small. Switch to `demo` after completing the
tutorial, and use `benchmark` only when you have budgeted preparation time and
embedding API usage.

## 2. Build and start TimescaleDB

```bash
docker compose build db app
docker compose up -d --wait db
```

The database image is PostgreSQL 18 with TimescaleDB and the public search
extensions used by the demo.

Check the server before loading data:

```bash
docker compose run --rm app python -m app.prepare setup
docker compose run --rm app python -m app.prepare doctor
```

Expected search access methods include `bm25`, `hnsw`, `ivfflat`, and
`diskann`. If an optional public extension is absent, `doctor` exposes the gap
and the corresponding demo method remains disabled.

## 3. Generate and load the incident corpus

```bash
docker compose run --rm app python -m app.prepare generate
docker compose run --rm app python -m app.prepare load
```

The generator produces events, deployments, runbooks, postmortems, issues, and
100 labeled questions from deterministic seed files. The loader creates one
retrieval corpus from events and documents while keeping source tables for
relational investigation.

Inspect the corpus:

```bash
docker compose exec db psql -U postgres -d state_of_search -P pager=off -c \
  "SELECT source_kind, count(*) FROM search_items GROUP BY source_kind ORDER BY source_kind"
```

## 4. Begin with exact and relational search

An error code should not need embeddings:

```bash
docker compose exec db psql -U postgres -d state_of_search -P pager=off -c \
  "EXPLAIN (ANALYZE, BUFFERS) SELECT id, service, incident_id, content FROM search_items WHERE error_code = 'PG_53300'"
```

Use B-tree indexes for exact values, identifiers, ranges, ordering, and highly
selective filters. Use JSONB GIN indexes when the searchable attributes live in
metadata. These tools are cheap, precise, transactional, and often overlooked
when teams jump directly to “AI search.”

## 5. Add typo tolerance with pg_trgm

The load step has already built the relational and lexical indexes. Try the
misspelled query:

```bash
docker compose run --rm app python -m app.demo search trigram "conection pool exaustion"
```

Trigrams compare overlapping three-character sequences. They are useful for
misspelled names, partial identifiers, autocomplete candidates, `LIKE`, and
`ILIKE`. They do not understand semantic equivalence.

## 6. Compare PostgreSQL full-text search and BM25

```bash
docker compose run --rm app python -m app.demo compare \
  "too many clients already" fts bm25
```

Native full-text search provides tokenization, dictionaries, stemming, phrase
operators, highlighting, and `ts_rank`/`ts_rank_cd`. `pg_textsearch` adds BM25,
which uses corpus frequency, term-frequency saturation, and document-length
normalization. BM25 is attractive when ranking quality matters more than simply
finding rows containing normalized terms.

## 7. Create OpenAI embeddings

```bash
docker compose run --rm app python -m app.prepare embed
```

The script sends `title + content` to OpenAI in batches, stores each returned
vector in pgvector format, and copies it into thin method tables for
deterministic ANN selection. Completed rows are skipped, so an interrupted
embedding run can continue. The full `load` step resets the corpus.

The implementation uses `text-embedding-3-small`, whose default output has
1,536 dimensions according to the official
[OpenAI embeddings documentation](https://developers.openai.com/api/docs/guides/embeddings).

Rebuild all indexes after embeddings exist:

```bash
docker compose run --rm app python -m app.prepare index
docker compose run --rm app python -m app.prepare doctor
```

## 8. Establish exact vector ground truth

```bash
docker compose run --rm app python -m app.demo search vector_exact \
  "why does checkout keep losing database capacity"
```

Exact vector search scores every eligible row. It has perfect nearest-neighbor
recall and is the baseline for evaluating approximate indexes. It can also be
the correct production plan for small or strongly prefiltered corpora.

## 9. Compare ANN index designs

```bash
docker compose run --rm app python -m app.demo compare \
  "why does checkout keep losing database capacity" \
  vector_exact hnsw ivfflat diskann
```

- **IVFFlat** clusters vectors into lists and searches selected lists. It has a
  training/build dependency and exposes a probes-versus-recall tradeoff.
- **HNSW** traverses a proximity graph. It commonly provides a strong
  speed/recall tradeoff but costs build time and memory.
- **StreamingDiskANN** is pgvectorscale's disk-oriented graph approach with
  compressed storage and rescoring controls.

Do not read too much into sample-profile timings. Repeat the comparison with
`DATASET_PROFILE=demo`, and use exact overlap plus the labeled questions rather
than latency alone.

## 10. Fuse keyword and semantic ranks

```bash
docker compose run --rm app python -m app.demo search hybrid \
  "payments deploy saturated postgres max_connections"
```

The hybrid query retrieves forty BM25 and forty HNSW candidates, converts
their positions into `1 / (60 + rank)`, sums scores for duplicate rows, and
returns the ten highest fused scores. RRF avoids pretending BM25 and cosine
scores live on the same numeric scale.

In a production query, apply authorization, tenant, time, service, region, and
status rules deliberately. Whether filters run before, during, or after ANN
candidate generation can materially change both latency and recall.

## 11. Run the guided demo

```bash
docker compose run --rm app python -m app.demo tour
docker compose up -d app
```

Open <http://127.0.0.1:8501>. The UI shows only methods verified as available in
the running environment.

This Streamlit page is the method-comparison surface. A separate companion
Reflex app presents the same incident domain as an operator workflow on port
3000. It places the incident queue, chronology, linked changes, runbooks,
status brief, and source-backed evidence search around the retrieval layer.
The companion application is not included in this repository.

## 12. Add Elasticsearch

```bash
docker compose --profile elastic up -d --wait elasticsearch
docker compose --profile elastic run --rm prepare python -m app.prepare elastic
```

Then compare PostgreSQL and Elasticsearch over the same rows and embeddings:

```bash
docker compose --profile elastic run --rm app python -m app.demo compare \
  "payments deploy saturated postgres max_connections" \
  bm25 hybrid elastic_bm25 elastic_hybrid
```

Elasticsearch offers a search-focused Query DSL, analyzers, aggregations,
approximate kNN, and hybrid retrieval. The tradeoff is architectural: data must
be copied from the transactional source, mapped, refreshed, reconciled,
secured, backed up, and upgraded as a second system.

## 13. Evaluate relevance

Start small because semantic queries create and cache query embeddings:

```bash
docker compose run --rm app python -m app.evaluate --questions 10
```

Then run all labeled questions:

```bash
docker compose run --rm app python -m app.evaluate
```

The evaluator reports whether the expected incident family appears in the top
ten and summarizes Recall@10 and mean client-observed latency by query kind.
Future drafts can add MRR, NDCG, repeated latency trials, index build time,
index size, and filtered-recall experiments.

## 14. Reset safely

Stop containers without deleting data:

```bash
docker compose --profile elastic down
```

Delete the demo volumes only when you deliberately want to remove the prepared
database and Elasticsearch index:

```bash
docker compose --profile elastic down --volumes
```

The generated Docker volume and API-created embeddings are not recoverable
after the volume is deleted; they can be regenerated from the committed seeds.
