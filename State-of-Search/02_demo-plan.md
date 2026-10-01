# Demo Plan and Presenter Runbook

This is the live sequence inside the 50-minute talk. Target runtime: 24
minutes. Keep the Streamlit comparison UI and Reflex command center open, with
a terminal ready as the reliable control surface.

## Preparation checklist

At least one day before presenting:

```bash
cd State-of-Search
docker compose build
docker compose up -d --wait db
docker compose run --rm prepare
docker compose up -d app
docker compose run --rm app python -m app.prepare doctor
docker compose run --rm app python -m app.evaluate --questions 10
```

For Elasticsearch:

```bash
docker compose --profile elastic up -d --wait elasticsearch
docker compose --profile elastic run --rm prepare python -m app.prepare elastic
```

Keep the first terminal in `State-of-Search/`. After the Incident Search setup
finishes, open a second terminal for the separately cloned companion on-call
repository, build the dashboard image, and wait for its services to become
healthy:

```bash
cd /path/to/Incident-search
docker compose --profile dashboard build dashboard
docker compose --profile dashboard up -d --wait
```

Verify the companion stack from the same second terminal:

```bash
docker compose --profile dashboard ps
```

The dashboard service should be running and healthy before you open
<http://127.0.0.1:3000>. If it is not, inspect it with
`docker compose --profile dashboard logs dashboard` before rehearsing.

Before walking on stage, complete these checks in order:

1. Confirm Docker has enough memory for both projects and is not waiting for an
   update or restart.
2. In the `State-of-Search/` terminal, confirm `doctor` reports the expected
   `bm25`, `hnsw`, `ivfflat`, and `diskann` access methods:

   ```bash
   docker compose run --rm app python -m app.prepare doctor
   ```

3. Open <http://127.0.0.1:8501>, submit the default query, and confirm that the
   expected comparison columns contain results.
4. In the companion app at <http://127.0.0.1:3000>, select the database-pool or
   payment-related incident that you will use in Scene 6. Leave that incident
   open so the demo starts from known state.
5. In the `State-of-Search/` terminal, run the complete tour once to populate
   query-embedding and database caches:

   ```bash
   docker compose run --rm app python -m app.demo tour
   ```

6. Confirm that `results/evaluation.csv` exists and save a screenshot of the
   comparison UI or evaluation output as a no-network backup.
7. Disable desktop and phone notifications. Close unrelated browser tabs and
   terminals, especially any terminal displaying `.env`, an OpenAI API key, or
   other credentials.

## Scene 1 — exact beats clever (2 minutes)

Command:

```bash
docker compose run --rm app python -m app.demo search exact PG_53300
```

Say:

> This is a database lookup wearing a search-box costume. A semantic model
> would add cost and ambiguity to a question PostgreSQL can answer exactly.

Show the error-code index and connect the matching event to its incident.

## Scene 2 — tolerate human input (2 minutes)

```bash
docker compose run --rm app python -m app.demo compare \
  "conection pool exaustion" trigram fts
```

Point out that trigrams recover spelling variation while language-aware FTS may
not. Clarify that fuzzy spelling and semantic similarity are different jobs.

## Scene 3 — lexical ranking (3 minutes)

```bash
docker compose run --rm app python -m app.demo compare \
  "too many clients already" fts bm25
```

Explain the result ordering, not merely whether rows matched. BM25 reasons
about the corpus; native FTS provides rich PostgreSQL linguistic controls.

## Scene 4 — vector indexes are physical designs (5 minutes)

```bash
docker compose run --rm app python -m app.demo compare \
  "why does checkout keep losing database capacity" \
  vector_exact hnsw ivfflat diskann
```

Anchor every approximate result to exact search. Do not call overlap “accuracy”;
it is top-k agreement with the exact nearest-neighbor result for one query.

If using the sample profile, say explicitly that the corpus is too small for
performance conclusions. Focus on the mechanics and knobs.

## Scene 5 — hybrid is the product answer (3 minutes)

```bash
docker compose run --rm app python -m app.demo search hybrid \
  "payments deploy saturated postgres max_connections"
```

Explain that the query mixes a concept, an exact subsystem, a technical token,
and a relational event. BM25 and vectors retrieve candidates; RRF fuses ranks;
SQL connects evidence.

## Scene 6 — retrieval inside the on-call workflow (3 minutes)

Open <http://127.0.0.1:3000>. Keep the navigation deliberate:

1. Start with the incident queue and urgent-signal total.
2. Select the database-pool or payment-related incident.
3. Correlate the event rhythm with the linked deployment.
4. Generate the AI status brief and identify its supporting records.
5. Jump to Evidence search for the question used in Scene 5.

Say that the Streamlit UI isolates retrieval methods while the Reflex app
shows the responder's real sequence: scope the incident, inspect chronology,
check changes and runbooks, then search when it can resolve uncertainty.

## Scene 7 — where Elasticsearch fits (4 minutes)

```bash
docker compose --profile elastic run --rm app python -m app.demo compare \
  "payments deploy saturated postgres max_connections" \
  bm25 hybrid elastic_bm25 elastic_hybrid
```

Use this decision frame:

```text
Postgres source row
  ├── native indexes: fresh, relational, transactionally governed
  └── sync pipeline ──> Elasticsearch document: denormalized, independently scaled
```

Discuss mapping, refresh, reconciliation, permissions, backups, and operations.
The demo runs Elasticsearch BM25 and kNN separately and fuses their positions
in the Python client, avoiding a dependency on the licensed native RRF
retriever.
Avoid presenting a local single-node latency comparison as a product benchmark.

## Scene 8 — finish with evidence (2 minutes)

```bash
docker compose run --rm app python -m app.evaluate --questions 10
```

Show recall by query kind. The closing point is that different queries reward
different retrieval paths and that a hybrid system must be evaluated against
real judgments.

## Failure handling

| Failure | Recovery |
|---|---|
| OpenAI unavailable | Prepared row and query embeddings remain cached. Use rehearsed queries. |
| Elasticsearch unavailable | Skip Scene 7 live calls and use the architecture diagram plus saved results. |
| Optional extension absent | `doctor` identifies it; omit only that method and explain the packaging boundary. |
| Browser UI fails | Run every scene through `app.demo`; it is the canonical path. |
| Reflex dashboard fails | Continue with the Streamlit comparison and explain the response workflow from the deck slide. |
| Cold query is slow | Narrate the storage/cache effect; never replace the number with an unstated warm result. |
| Results differ after extension update | Show pinned versions and exact baseline; do not claim the previous output. |

## Claims discipline

- Say “on this machine, with this corpus and these settings.”
- Separate embedding latency from database retrieval latency.
- Separate nearest-neighbor overlap from labeled-answer recall.
- Record cold versus warm cache state.
- Never compare one PostgreSQL container with one Elasticsearch node as if it
  establishes universal scalability.

## Backup close

If all live systems fail:

> Search is a ladder. Exact relational lookup, fuzzy characters, lexical
> relevance, semantic vectors, approximate indexes, and hybrid fusion each
> solve a different problem. PostgreSQL now covers far more of that ladder than
> many teams assume. Elasticsearch remains compelling when search-specific
> features and independent scale repay the cost of a second data system. The
> right answer comes from labeled relevance, operational constraints, and an
> exact baseline—not from picking the newest index name.
