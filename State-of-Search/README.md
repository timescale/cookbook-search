# State of Search

One incident corpus, many retrieval strategies, and an honest answer to the
question: **when should search stay in PostgreSQL, and when does a dedicated
search system earn its place?**

This demo compares:

- Ordinary PostgreSQL lookup and filtering with B-tree, JSONB, and time indexes.
- Typo-tolerant matching with `pg_trgm`.
- PostgreSQL full-text search with `tsvector`, GIN, and `ts_rank_cd`.
- BM25 keyword ranking with `pg_textsearch`.
- Exact vector search with `pgvector`.
- Approximate vector search with pgvector IVFFlat and HNSW.
- StreamingDiskANN with `pgvectorscale`.
- Hybrid BM25 + HNSW retrieval with Reciprocal Rank Fusion (RRF).
- Elasticsearch BM25, kNN, and hybrid RRF as the dedicated-search-engine comparison.

The data is a synthetic incident memory for a fictional ecommerce platform. It
is generated deterministically by the included `generate_data.py` entrypoint,
`generator/` package, and committed `seed/` files. No source CSV is edited by
hand.

## The story

The talk follows a single incident through increasingly ambiguous questions:

1. `PG_53300` is an exact lookup problem.
2. `conection pool exaustion` is a typo-tolerance problem.
3. `too many clients already` is a lexical relevance problem.
4. `why does checkout keep losing database capacity` is a semantic problem.
5. `payments deploy saturated postgres max_connections` needs hybrid retrieval,
   time, metadata, and relational context.

Each technique is useful. None is the universal endpoint of search.

## Where these approaches show up

| Search approach | Common product context | Typical users | Typical owners |
|---|---|---|---|
| Exact and relational | Order IDs, account records, error codes, date and status filters | Operators, support teams, analysts, application users | Application and database teams |
| Fuzzy text | Misspelled names, partial titles, directory lookup, autocomplete | Customers, support agents, internal-tool users | Product and application teams |
| Full-text search | Documentation, tickets, policies, articles, case notes | Support, legal, operations, knowledge workers | Application and content-platform teams |
| BM25 ranking | Ranked documentation, catalogs, help centers, issue archives | People who expect the best textual match first | Search relevance and application teams |
| Semantic search | Paraphrased questions, concept discovery, related content, retrieval for AI assistants | Knowledge workers, researchers, support agents, AI applications | ML, data, and application teams |
| ANN vector indexes | Low-latency semantic retrieval over large embedding collections | Usually invisible infrastructure serving semantic features | Database, ML-platform, and infrastructure teams |
| Hybrid search | Product catalogs, technical support, enterprise knowledge, grounded AI answers | Customers, employees, support agents, AI assistants | Search, ML, and application teams together |
| Dedicated search engine | Search-heavy marketplaces, media libraries, log exploration, complex faceting and aggregations | Large external audiences and operational teams | A search or platform team prepared to operate a second system |

The person typing the query and the team operating retrieval are often
different. A useful search design must serve both: relevant results for the
user and an operational model the owning team can sustain.

## What is included

| Component | Purpose |
|---|---|
| Streamlit app | Compare available retrieval methods side by side. |
| Terminal demo | Run reliable scripted searches and presentation tours. |
| Evaluation harness | Measure hit-based Recall@k and client-observed latency over labeled questions. |
| PostgreSQL environment | Run the corpus and search extensions in a repeatable Docker Compose service. |
| Optional Elasticsearch service | Compare PostgreSQL retrieval with a dedicated search engine over the same data. |
| Reveal.js deck | Present the narrative, demos, speaker notes, and recovery cues. |

## Companion response workflow

The Streamlit app in this directory compares retrieval methods over the same
question. A separate Incident Search Reflex app shows where those methods land
in an operator-facing product: an on-call command center with an incident
queue, selected-incident context, an evidence search assistant, supporting
source records, and an exact-versus-PRISM search lab. The talk uses both
interfaces deliberately. Streamlit isolates retrieval behavior; Reflex
demonstrates the incident-response workflow around it. The companion app is
not included in this repository.

## Repository map

| Path | Purpose |
|---|---|
| `compose.yaml` | TimescaleDB/PostgreSQL, demo app, preparation job, and optional Elasticsearch. |
| `Dockerfile.db` | Selects the PostgreSQL 18 TimescaleDB image used by the demo. |
| `Dockerfile.app` | Packages the generator, loaders, embedding client, CLI, evaluator, and UI. |
| `generate_data.py` | Deterministic synthetic incident-corpus generator. |
| `generator/` | Generator helpers for services, incident families, and documents. |
| `seed/` | Versioned source material used by the deterministic generator. |
| `sql/` | Schema, relational/text/vector indexes, and reset script. |
| `app/prepare.py` | Generate, load, embed, index, verify, and optionally copy data to Elasticsearch. |
| `app/demo.py` | Reliable terminal-first live demo. |
| `app/ui.py` | Streamlit side-by-side search comparison. |
| `app/evaluate.py` | Recall-at-k evaluation using the labeled incident questions. |
| `slides/` | Reveal.js presentation deck, including the on-call workflow that applies the retrieval stack. |
| `00_tutorial.md` | Step-by-step tutorial and executable command script. |
| `01_talk-outline.md` | Narrative 50-minute talk outline. |
| `02_demo-plan.md` | Presenter runbook, timing, failure recovery, and backup path. |
| `03_talk-track.md` | Full speaker narrative, historical arc, transitions, claims, and citations. |

## Requirements

- Docker Desktop or another Docker engine with Compose and BuildKit.
- Node.js 20.19.x, or 22.12 and newer (Node 22 is recommended).
- An OpenAI API key for semantic-search preparation and uncached query vectors.
- About 4 GB of Docker memory for the PostgreSQL-only sample; use at least 6 GB
  when adding Elasticsearch.

The demo uses OpenAI `text-embedding-3-small` at its default 1,536 dimensions.
The same `vector(1536)` representation is used by pgvector, pgvectorscale, and
the Elasticsearch comparison. See the official
[OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings).

## Quick start

### 1. Configure the environment

From `State-of-Search/`:

```bash
cp .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY`. The default `sample` dataset creates
5,000 events and is the quickest way to verify the workflow.

### 2. Build and prepare the demo

Build the images and prepare the sample corpus:

```bash
docker compose build
docker compose up -d --wait db
docker compose run --rm prepare
docker compose up -d app
```

The preparation job resets the generated corpus and makes billable OpenAI
embedding requests. Normal query embeddings are cached in PostgreSQL.

### 3. Open or verify the demo

Open <http://127.0.0.1:8501>, run the terminal tour, or inspect the environment:

```bash
docker compose run --rm app python -m app.demo tour
docker compose run --rm app python -m app.prepare doctor
```

`doctor` reports PostgreSQL and extension versions, available index access
methods, and corpus and embedding counts. An extension-specific method is
reported as unavailable when its access method is absent; the demo does not
silently substitute another index.

## Run the presentation

From this directory, install the JavaScript dependencies once and start the
Reveal.js deck:

```bash
nvm use # optional; reads the included .nvmrc when nvm is installed
npm install
npm run dev
```

Open the local URL printed by Vite (normally <http://127.0.0.1:5173>). Press
`S` for speaker view and `Esc` for the slide overview. Use `npm run build` to
verify a production build, or `npm run preview` to serve that build locally.

## Dataset profiles

Set `DATASET_PROFILE` in `.env` before preparation:

| Profile | Events | Purpose |
|---|---:|---|
| `sample` | 5,000 | Fast first run and tutorial. ANN timing is not meaningful at this size. |
| `demo` | 50,000 | Live talk and basic recall/latency comparisons. |
| `benchmark` | 250,000 | More realistic index behavior; needs more time, disk, memory, and API usage. |

The generator always includes all 20 incident families. The benchmark profile
uses the original 62-incident shape; the smaller profiles use one incident per
family.

## Verify the environment

```bash
docker compose run --rm app python -m app.prepare doctor
```

The target image contains TimescaleDB, pgvector, pgvectorscale, and
pg_textsearch. These projects move at different speeds, so extension
compatibility on PostgreSQL 18 is an explicit first-run gate rather than an
assumption hidden in the presentation.

## Add Elasticsearch

Elasticsearch is optional because it materially increases startup time and
memory use:

```bash
docker compose --profile elastic up -d --wait db elasticsearch
docker compose --profile elastic run --rm prepare python -m app.prepare elastic
docker compose up -d app
```

The Elasticsearch index receives the same text, metadata, incident-family
labels, and OpenAI vectors as PostgreSQL. It is a comparison of retrieval
systems, not a comparison of different corpora or embedding models.

Elasticsearch 9.5.4 is pinned for reproducibility. This local configuration
disables security and is **not** a production deployment.

## Useful commands

```bash
# One method
docker compose run --rm app python -m app.demo search bm25 "too many clients already"

# Side-by-side methods
docker compose run --rm app python -m app.demo compare \
  "why does checkout keep losing database capacity" \
  vector_exact hnsw ivfflat diskann

# Short evaluation rehearsal
docker compose run --rm app python -m app.evaluate --questions 10

# Complete labeled-family evaluation
docker compose run --rm app python -m app.evaluate

# Rebuild only indexes after changing SQL
docker compose run --rm app python -m app.prepare index
```

Evaluation writes `results/evaluation.csv` and reports hit-based Recall@10 by
query kind. This is a teaching harness, not a publication-quality benchmark:
run repeated warm and cold trials, record hardware, pin every version, and
separate embedding time from retrieval time before publishing performance
claims.

## Stop and clean up

Stop the services while keeping generated Docker volumes:

```bash
docker compose down
```

To also remove the generated PostgreSQL, Elasticsearch, and corpus volumes:

```bash
docker compose down --volumes
```

The second command permanently removes the local demo data stored in those
volumes. It does not delete source files or the local `.env` file.

## PostgreSQL or Elasticsearch?

Start with PostgreSQL-native search when PostgreSQL is the system of record,
fresh transactional data matters, results require joins or row-level rules,
and one operational system can meet relevance and latency goals.

Evaluate Elasticsearch when search is itself a primary product surface and the
workload benefits from a mature analyzer ecosystem, autocomplete and fuzzy
search features, search-time aggregations, independent scaling, shards and
replicas, or a team already operating Elastic successfully.

Using both is common, but it creates a second copy of the data. The demo makes
that cost visible: ingestion, mappings, refresh delay, reconciliation,
authorization duplication, backups, upgrades, and another failure domain.

## Current limitations

- The sample profile is for functionality, not ANN benchmarking.
- Client-observed timings include database round trips and Python processing.
- ANN indexes use teaching defaults. Production tuning depends on corpus size,
  recall targets, filters, update rate, storage, and memory.
- Elasticsearch is a single-node local comparison without production security,
  replicas, or shard planning.
- The evaluation uses incident-family hits, not graded relevance or NDCG.

## Read next

Follow [`00_tutorial.md`](./00_tutorial.md), rehearse with
[`02_demo-plan.md`](./02_demo-plan.md), and use
[`03_talk-track.md`](./03_talk-track.md) for the complete speaker narrative.
