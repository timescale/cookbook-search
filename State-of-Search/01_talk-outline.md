# Talk Outline: The State of Search in PostgreSQL

**Target length:** 50 minutes, including roughly 20 minutes of live demo

**Throughline:** One search box can hide several different retrieval problems.
Start by naming the problem, then choose the smallest system that solves it.

## Abstract

“Add search” sounds like one feature. In practice, it may mean exact lookup,
typo tolerance, linguistic retrieval, corpus-aware ranking, semantic
similarity, approximate nearest neighbors, hybrid relevance, or a separately
operated search cluster.

This talk follows one production incident through each interpretation. Using
the same synthetic incident memory and labeled questions, we compare ordinary
PostgreSQL indexes, `pg_trgm`, native full-text search, `pg_textsearch`,
pgvector, pgvectorscale, hybrid retrieval, and Elasticsearch. The point is not
to crown a winner. It is to build a repeatable decision process for relevance,
performance, and operational complexity—and to show where each approach is
used, who depends on it, and who has to operate it.

## Audience promise

By the end, attendees will be able to:

- Distinguish exact, fuzzy, lexical, semantic, and hybrid retrieval problems.
- Choose the simplest PostgreSQL search primitive that satisfies a query.
- Separate an embedding model, a distance function, and an ANN index.
- Evaluate the physical and operational tradeoffs of major PostgreSQL vector indexes.
- Combine lexical and semantic results without mixing incomparable raw scores.
- Place retrieval inside an evidence-first operator workflow rather than treating the search box as the whole product.
- Decide when PostgreSQL-native search is enough and when a dedicated search system earns its cost.
- Evaluate search quality with labels and exact baselines rather than a latency screenshot.

The full speaker wording, sources, and fact-check notes are in
[`03_talk-track.md`](./03_talk-track.md). The live-demo sequence and recovery
paths are in [`02_demo-plan.md`](./02_demo-plan.md).

## Narrative map

```text
What kind of question is this?
        │
        ├── Known identity or structured constraint ──> B-tree / JSONB / SQL
        ├── Misspelled or partial text ───────────────> pg_trgm
        ├── Known words and phrases ─────────────────> FTS / BM25
        ├── Same meaning, different words ───────────> vectors
        └── Exact language plus meaning ─────────────> hybrid retrieval

Then ask: can PostgreSQL meet the measured product and operational needs?
        ├── yes ──> keep search with the source of truth
        └── no ───> justify the boundary to a dedicated search system
```

### Who uses each layer—and where

| Search layer | Where it appears | Who uses it | Who usually owns it |
|---|---|---|---|
| Exact and relational | Orders, accounts, error codes, audit records, operational filters | Support, operators, analysts, application users | Application and database teams |
| Fuzzy text | Autocomplete, people and directory lookup, misspelled titles or identifiers | Customers, employees, support agents | Product and application teams |
| Full-text and BM25 | Documentation, help centers, tickets, policies, catalogs | Knowledge workers and people seeking the best textual match | Application, content-platform, and search-relevance teams |
| Semantic search | Paraphrased questions, related content, research, AI retrieval | Researchers, support agents, employees, AI assistants | ML, data, and application teams |
| ANN infrastructure | Large embedding collections with interactive latency requirements | Indirectly used by anyone using a semantic feature | Database, ML-platform, and infrastructure teams |
| Hybrid search | Ecommerce, enterprise knowledge, technical support, grounded AI answers | Customers, employees, agents, and AI applications | Search, ML, and application teams together |
| Dedicated search systems | Search-heavy products, large catalogs, log exploration, complex facets | Large external audiences and operational teams | A search or platform team that can own a second system |

Use this table throughout the talk to connect each index to a human need. The
query author, the product team, and the operating team may all be different.

## Act I — Diagnose the search box (0–6 minutes)

### Opening: five queries, five jobs (0–4)

Put these queries on screen:

```text
PG_53300
conection pool exaustion
too many clients already
why does checkout keep losing database capacity
payments deploy saturated postgres max_connections
```

Ask the audience what “relevant” means for each query. Reveal the jobs one at a
time: exact lookup, typo tolerance, lexical retrieval, semantic retrieval, and
hybrid retrieval with relational context.

**Thesis:** Search is not a feature or an index type. It is a stack of retrieval
problems, and the first design decision is identifying which problem the user
actually has.

### Introduce the incident thread (4–6)

Briefly establish the fictional ecommerce incident: a deployment contributes
to exhausted PostgreSQL connections, checkout degrades, and the evidence is
spread across events, incident notes, runbooks, and remediation work.

Explain the comparison rule: every method sees the same corpus, metadata,
labels, and embedding model. The talk will judge both result quality and the
system required to produce it.

## Act II — PostgreSQL's search ladder (6–24 minutes)

### Exact and relational search: let PostgreSQL be PostgreSQL (6–10)

**Live query:** `PG_53300`

- Use a B-tree for equality, ranges, and ordered retrieval.
- Use JSONB or array GIN indexes for structured metadata when appropriate.
- Join the matched event directly to its deployment, incident, runbook, and remediation issue.
- Treat freshness, constraints, permissions, and transactional consistency as search features.

**Decision rule:** If the query has a precise identity or structured predicate,
do not replace certainty with a relevance model.

**Transition:** Exact lookup works when users know the identifier. They often do
not—and they also mistype it.

### Fuzzy text: typo tolerance is not semantics (10–13)

**Live query:** `conection pool exaustion`

Compare `pg_trgm` with native full-text search. Explain character trigrams,
similarity thresholds, and why they work well for misspellings, partial names,
titles, identifiers, and autocomplete.

**Boundary:** Character overlap can recover spelling variation, but two phrases
can mean the same thing while sharing few characters.

### Lexical retrieval: PostgreSQL already has a search engine (13–18)

**Live query:** `too many clients already`

Introduce `tsvector`, `tsquery`, language configurations, GIN, Boolean and
phrase operators, field weights, and `ts_rank_cd`.

**Decision rule:** Native full-text search is a strong default when users know
the vocabulary and the task is to find normalized words or phrases.

### Corpus-aware lexical ranking: BM25 and `pg_textsearch` (18–22)

Compare native FTS ordering with BM25 on the same query.

- Inverse document frequency rewards discriminating terms.
- Term-frequency saturation prevents repetition from winning forever.
- Document-length normalization lets short and long documents compete more fairly.
- Ranking is relative to a corpus; an absolute score is not product truth.

Name the operational cost of the added index: builds, segments or compaction,
writes, backups, version compatibility, and upgrades.

### Historical reset: this is evolution, not reinvention (22–24)

Use one compact timeline:

```text
PostgreSQL extensibility and arrays
        └── early-2000s tsearch work
              └── 2008: full-text search in PostgreSQL core
                    └── 2021: pgvector and IVFFlat
                          └── 2023: pgvector HNSW
                                └── 2024+: pgvectorscale, BM25, hybrid retrieval
```

Clarify that arrays could store numbers but did not supply embedding semantics
or ANN indexes. PostgreSQL's enduring advantage is its extensibility.

Attribute Timescale's reported 28× lower p95 latency and 16× higher throughput
to its own 50-million-vector, 768-dimensional benchmark at 99% recall. Present
it as a workload-specific result, not a universal guarantee.

**Transition:** Lexical systems improve how we search words. Embeddings change
the representation so we can search meaning.

## Act III — Semantic retrieval and physical index design (24–36 minutes)

### Search by meaning (24–29)

**Live query:** `why does checkout keep losing database capacity`

Embed the query with OpenAI `text-embedding-3-small` and start with exact
pgvector search. Keep three layers separate:

1. The embedding model creates the representation.
2. The distance function compares representations.
3. The index finds candidates efficiently.

Exact vector search is the recall baseline and may be the production answer for
a small or heavily filtered corpus.

### ANN is a resource and operations choice (29–36)

Compare exact search with IVFFlat, HNSW, and StreamingDiskANN.

| Index | Physical shape | Begin evaluation when |
|---|---|---|
| IVFFlat | Trained clustered lists | Build simplicity and modest memory matter; data is relatively stable. |
| HNSW | Navigable proximity graph | A mature speed–recall tradeoff is worth graph build time and memory. |
| StreamingDiskANN | Disk-oriented graph with compressed vectors | Storage-aware graph search and filtered-search features fit the workload. |

For every index, ask about recall target, filter selectivity, update rate, build
window, memory, storage latency, vacuum behavior, replication, backup, and
upgrade path.

**Guardrail:** The sample corpus proves that the system is wired correctly; it
does not establish performance. Every ANN claim needs representative data,
hardware, concurrency, cache state, tuning parameters, and an exact baseline.

## Act IV — Apply retrieval, then choose the system boundary (36–47 minutes)

### Hybrid retrieval is the practical center (36–40)

**Live query:** `payments deploy saturated postgres max_connections`

Show why neither lexical nor semantic retrieval is sufficient alone:

- BM25 recognizes exact technical terms such as `postgres` and `max_connections`.
- Semantic retrieval recognizes the paraphrased failure mode.
- Reciprocal Rank Fusion combines rank positions without pretending BM25 and cosine scores share units.
- SQL applies time, service, region, severity, tenant, and permission constraints, then joins supporting evidence.

**Decision rule:** Retrieval produces candidates; product constraints and
relational evidence determine whether the result is useful and trustworthy.

### The on-call workflow around retrieval (40–43)

Open the companion Reflex command center from `Incident-search/`. Select an
incident before opening Evidence search. Show how the responder moves from the
urgent-signal count and affected services to event rhythm, linked changes,
recent signals, runbook context, and a cited status brief.

Explain why this order matters: retrieval supports a decision. The operator
still needs scope, chronology, source records, and the smallest safe next
check. The dashboard keeps the historical-data label visible so the demo never
masquerades as live production state.

**Decision rule:** Design the interface around the user's next decision, then
place search where it reduces uncertainty.

### When should search leave PostgreSQL? (43–47)

Introduce Elasticsearch as a dedicated retrieval system, not another
PostgreSQL access method.

```text
PostgreSQL source of truth
  ├── native retrieval: current, relational, transactionally governed
  └── change pipeline ──> Elasticsearch projection
                           analyzers, search features, independent scale
```

Prefer PostgreSQL-native search when data freshness, joins, row-level rules,
transactional semantics, and one operational system dominate—and measured
relevance and latency are adequate.

Evaluate Elasticsearch when search is a primary product surface, analyzers and
search-specific features are central, query capacity must scale independently,
documents can be denormalized, and the team can own ingestion lag and another
distributed system.

If showing both systems, discuss synchronization, refresh delay,
reconciliation, authorization, backups, and failure recovery before comparing
latency.

**Decision rule:** Add a second system only when its search-specific value pays
the consistency and ownership tax.

## Act V — Measure, decide, and close (47–50 minutes)

Run the labeled-question evaluation and summarize results by query kind.
Distinguish clearly among:

- Labeled-answer recall: did the system retrieve a relevant incident family?
- ANN overlap: did an approximate index reproduce exact nearest neighbors?
- Latency: how long did retrieval take under stated conditions?
- Operational fitness: can the team build, update, recover, and evolve it?

Close with four rules:

1. Name the retrieval problem before choosing the technology.
2. Start with the simplest primitive that answers the query.
3. Keep an exact baseline and evaluate with representative labels and filters.
4. Cross a system boundary only when the measured benefit pays for it.

Final line:

> The state of search is not that PostgreSQL replaces every search engine. It
> is that PostgreSQL now covers enough of the search stack that we can place
> the boundary from evidence instead of habit.
