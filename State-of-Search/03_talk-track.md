# Speaker Talk Track: The State of Search

Target length: 50 minutes, including the 24-minute live demo sequence.

This is a spoken script, not prose to read word-for-word. The
indented blocks are suggested language; the code blocks are stage directions.

## Introduction — Erin Mikail Staples

Show the profile slide after the title slide.

> Hi, I’m Erin Mikail Staples. My pronouns are she and her. I’m a Staff
> Developer Experience Engineer at Tiger Data. I help developers make sense of
> complicated technology and get something useful running. My work connects
> developer tooling with education and community, from APIs and AI workflows
> to the docs and demos that make it all click.

> Outside of work, I’m a stand-up comedian and rescue dog mom living in
> Brooklyn by way of Reno. The comedy background is useful when a live demo
> develops opinions.

Keep this introduction to about one minute. The audience needs enough context
to understand Erin’s perspective without delaying the incident story.

## Opening — one box, five different questions

Put these queries on screen:

```text
PG_53300
conection pool exaustion
too many clients already
why does checkout keep losing database capacity
payments deploy saturated postgres max_connections
```

> These all fit in the same search box, but they are not the same problem. One
> is a lookup. One contains a typo. One depends on exact language. One is a
> paraphrase. The last one mixes domain terms, a deployment, and a failure
> mode. When someone asks us to “add search,” the first job is to find out
> which of these they mean.

> Today we will follow one fictional production incident through the search
> stack: relational indexes, fuzzy matching, full-text search, BM25, vectors,
> approximate nearest-neighbor indexes, hybrid retrieval, and finally
> Elasticsearch. This is not a tournament. It is a map of the tradeoffs.

Before naming the technologies, make the people and settings concrete:

- A support agent pastes an error code and needs the current account or
  incident record. That is exact and relational search.
- A customer misspells a product, person, or title. That is fuzzy text search.
- An engineer searches documentation or tickets using known technical words.
  That is lexical retrieval, often with full-text search or BM25.
- A knowledge worker or AI assistant asks a question using different words
  from the source. That is semantic retrieval.
- A shopper, support agent, or employee mixes exact names with natural
  language. That is usually a hybrid-search problem.

> The user of search is not always the owner of search. Customers, operators,
> analysts, employees, and AI applications care about useful results. Product,
> database, search-relevance, ML, and platform teams must build and operate the
> machinery. The right design has to work for both groups.

## Act I — PostgreSQL did not suddenly discover search

Show a simple timeline:

```text
Berkeley lineage ─ arrays and extensible types
       2002-ish   ─ contrib tsearch era
       2008       ─ full-text search enters PostgreSQL core
       2021       ─ pgvector 0.1.0
       2023       ─ pgvector HNSW
       2024       ─ pgvectorscale
       today      ─ BM25, disk-oriented ANN, hybrid retrieval, and dedicated engines
```

> The vector story did not begin with embeddings. PostgreSQL has long had
> general-purpose arrays and an extensible type and index system. You could
> store a list of numbers, but storage is not search: an array does not give us
> a vector distance type, operator classes, or an approximate nearest-neighbor
> index. The important foundation was PostgreSQL's extensibility, not an early
> secret vector database.

> PostgreSQL's modern lexical-search story began before the AI boom too. The
> early `tsearch` work appeared as contrib code in the early 2000s and was
> followed by `tsearch2`. PostgreSQL 8.3, released on February 4, 2008,
> integrated full-text search into core. From then on, `tsvector`, `tsquery`,
> dictionaries, ranking, Boolean operators, and phrase-aware queries were part
> of PostgreSQL itself—no search extension required.

> A `tsvector` is not just a bag of the original words. PostgreSQL parses text
> into normalized lexemes, can remove stop words, and records positions. A
> `tsquery` expresses normalized terms and their logical or phrase
> relationships. PostgreSQL could rank relevant documents long before an
> embedding API existed.

Sources for the slide: [PostgreSQL 8.3 release notes](https://www.postgresql.org/docs/8.3/release-8-3.html),
[PostgreSQL full-text search documentation](https://www.postgresql.org/docs/current/textsearch.html),
and [PostgreSQL arrays](https://www.postgresql.org/docs/current/arrays.html).

> Then the representation changed. Andrew Kane released pgvector 0.1.0 on
> April 20, 2021. Its early approximate index was IVFFlat: partition vectors
> into lists, inspect a subset at query time, and trade recall for speed.

> pgvector 0.5.0 added HNSW on August 28, 2023. You will sometimes hear this
> described as a September 2023 event, but the project changelog dates the
> release to August 28. HNSW usually offers a stronger speed–recall tradeoff
> than IVFFlat, while demanding more memory and taking longer to build. That is
> a recurring theme today: the logical query can stay the same while the
> physical index changes the resource bill.

Source for the slide: [pgvector changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md).

> In June 2024, Timescale introduced pgvectorscale as a layer alongside
> pgvector. Its headline ideas were StreamingDiskANN, a disk-oriented graph
> derived from Microsoft's DiskANN research, and Statistical Binary
> Quantization. It shifted the question from “can Postgres do vector search?”
> toward “which storage and compression design should Postgres use at this
> scale?”

> Timescale reported 28-times lower p95 latency and 16-times higher query
> throughput than Pinecone at 99 percent recall. Keep the attribution and the
> workload attached to that sentence: it was Timescale's benchmark over 50
> million 768-dimensional Cohere embeddings against Pinecone's s1 index. It is
> evidence that deserved attention, not a universal result for every corpus,
> machine, filter, or service tier.

Sources for the slide: [Timescale's June 2024 changelog](https://docs.timescale.com/about/latest/changelog/)
and [benchmark write-up](https://www.timescale.com/newsroom/postgresql-is-now-faster-than-pinecone-75-cheaper-with-new-open-source).

> That history brings us to the current landscape. Native full-text search
> handles mature lexical retrieval. pgvector supplies vector types, exact
> distance, IVFFlat, and HNSW. pgvectorscale adds a disk-conscious ANN option.
> pg_textsearch brings BM25 ranking into PostgreSQL. Hybrid systems combine lexical and semantic
> candidates, and ordinary SQL still applies permissions, time, service,
> tenant, and relational context.

> PostgreSQL did not become the right answer to every search problem. It became
> capable enough that the boundary deserves to be measured instead of assumed.

## Act II — climb the retrieval ladder

### Exact and relational search

Run:

```bash
docker compose run --rm app python -m app.demo search exact PG_53300
```

> `PG_53300` has a precise identity. A B-tree lookup is cheap, deterministic,
> and current in the same transaction as the source row. An embedding would add
> cost and ambiguity. The best search system is sometimes an ordinary index.

> PostgreSQL also lets the result stay relational. From this event we can join
> to the deployment, incident, runbook, owning service, and remediation issue.
> Freshness, constraints, permissions, and joins are relevance features even
> though benchmark charts rarely label them that way.

### Typo tolerance with pg_trgm

Run:

```bash
docker compose run --rm app python -m app.demo compare \
  "conection pool exaustion" trigram fts
```

> Character trigrams are excellent for misspellings, partial names, titles,
> identifiers, and autocomplete. They do not understand meaning. Two phrases
> can describe the same failure while sharing almost no character sequence.
> Fuzzy matching and semantic retrieval are separate tools.

### Native FTS and BM25

Run:

```bash
docker compose run --rm app python -m app.demo compare \
  "too many clients already" fts bm25
```

> Native full-text search gives us linguistic normalization, dictionaries,
> phrase operators, field weighting, and GIN indexing. It remains a strong
> default when users know the vocabulary and the product needs PostgreSQL's
> control over parsing and query construction.

> BM25 adds a corpus-aware ranking model. Rare terms matter more, repeating a
> term eventually stops helping, and long documents are normalized. Here
> `pg_textsearch` keeps that ranking inside PostgreSQL. The cost is another
> extension and another index lifecycle: builds, write behavior, compaction,
> backups, compatibility, and upgrades all belong in the decision.

## Act III — vectors change the representation, not the obligations

> For this demo, OpenAI's `text-embedding-3-small` maps each document and query
> into a 1,536-dimensional vector. The same model and dimensions are used for
> every database method and for Elasticsearch, so we compare retrieval rather
> than representations.

> Keep three layers separate. The embedding model creates the representation.
> The distance function compares representations. The index chooses candidate
> vectors efficiently. Switching from HNSW to DiskANN does not produce a new
> embedding, and changing the embedding model is not an index-tuning exercise.

Run:

```bash
docker compose run --rm app python -m app.demo compare \
  "why does checkout keep losing database capacity" \
  vector_exact hnsw ivfflat diskann
```

Talk through the methods:

- Exact pgvector search scans all eligible vectors. It is the recall baseline
  and can be the production answer for a small or highly filtered corpus.
- IVFFlat has a comparatively simple, fast build but depends on representative
  training data and probe tuning. It fits relatively stable data and moderate
  recall targets.
- HNSW is a mature in-memory graph with a strong speed–recall curve. It pays in
  graph build time, memory, and write amplification.
- StreamingDiskANN from pgvectorscale uses storage-aware graph traversal and
  quantization to target larger-than-memory workloads.

> The sample corpus proves wiring, not performance. At 5,390 rows the exact
> scan may win. The useful comparison is recall at a latency and resource
> budget on representative data. Every ANN claim needs its corpus size,
> dimensions, filters, update rate, hardware, cache state, build parameters,
> concurrency, and exact baseline.

## Act IV — hybrid search is the practical center

Run:

```bash
docker compose run --rm app python -m app.demo search hybrid \
  "payments deploy saturated postgres max_connections"
```

> This query contains exact technical tokens and a paraphrased causal story.
> BM25 recognizes `postgres` and `max_connections`; vector search can recognize
> the idea of exhausted database capacity. Reciprocal Rank Fusion combines
> their rank positions instead of pretending that a BM25 score and a cosine
> similarity have the same units.

> Retrieval produces candidates. SQL still has the final say: filter by time,
> region, tenant, severity, permissions, or service; then join to the evidence
> that lets a human trust the result. That combination is why keeping search
> near the source of truth can be compelling.

## Act V — retrieval inside the response workflow

Open the companion Reflex command center at <http://127.0.0.1:3000>.

> The comparison UI answers a technical question: how did each retrieval
> method rank the same evidence? The on-call interface answers a product
> question: what does the responder need next?

> We begin with the incident queue, urgent-signal count, and affected services.
> The selected incident keeps chronology beside the deployment that may matter,
> recent event records, and the relevant runbook. The status brief cites its
> supporting events. Evidence search sits inside that workflow rather than
> pretending the search box is the workflow.

Select the database-pool or payment-related incident. Compare its event rhythm
with the linked deployment, generate the status brief, and then ask:

```text
What changed before payments started timing out?
```

> This ordering matters. Retrieval produces candidates and a language model
> can summarize them, but the responder still needs scope, time, provenance,
> and a safe next check. The application should make those constraints visible.

Clarify that the command center shows a historical synthetic dataset. Its
timestamp is the latest record in the corpus, not live production state.

## Act VI — where Elasticsearch fits

Show this boundary:

```text
PostgreSQL source of truth
  ├── native retrieval: immediate, relational, transactionally governed
  └── change pipeline ──> Elasticsearch projection
                           analyzers, search features, independent scale
```

Optionally run:

```bash
docker compose --profile elastic run --rm app python -m app.demo compare \
  "payments deploy saturated postgres max_connections" \
  bm25 hybrid elastic_bm25 elastic_hybrid
```

The local demo runs Elasticsearch BM25 and kNN separately, then performs RRF
over their rank positions in the Python client. This keeps the comparison
available without relying on Elasticsearch's licensed native RRF retriever.

> Elasticsearch fits when search is a product in its own right: many tailored
> analyzers, autocomplete and highlighting, search-specific aggregations,
> independent query scaling, shard and replica controls, or an organization
> that already operates Elastic well. Its Query DSL and search ecosystem are
> the point—not merely that it also supports BM25 and kNN.

> It introduces a system boundary. Data must be denormalized and synchronized.
> Refresh creates visibility lag. Mappings and analyzers must evolve. Deletes,
> authorization, reconciliation, backups, upgrades, and failures now span two
> systems. Do not compare a local single-node Elasticsearch container to a
> local PostgreSQL container and call the result a scalability verdict.

> Stay in PostgreSQL when transactional freshness, joins, row-level controls,
> simpler operations, and adequate measured relevance dominate. Add
> Elasticsearch when its search-specific capability and independent scale pay
> the consistency and ownership tax. Running both is common; it is not free.

Sources for the slide: [Elasticsearch hybrid search](https://www.elastic.co/docs/solutions/search/hybrid-search),
[kNN search](https://www.elastic.co/docs/solutions/search/vector/knn), and
[Query DSL](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html).

## Close — choose from evidence

Run:

```bash
docker compose run --rm app python -m app.evaluate --questions 10
```

> Search quality is not a latency screenshot and it is not the result that
> looked best during development. We need labeled questions, recall and ranking
> metrics, representative filters, cold and warm runs, and operational costs.

Move to the summary slide and recap the four decisions:

> First, match the retrieval method to the question. Use exact and relational
> search when the query already has an identity.

> Second, add fuzzy, lexical, semantic, or hybrid retrieval only when the
> question requires it.

> Third, keep an exact baseline and a recall target when you evaluate an
> approximate index. A fast query has little value when it quietly returns the
> wrong neighborhood.

> Finally, add a second system when its product value pays for the consistency
> and ownership boundary it creates.

Final line:

> The state of search is not that PostgreSQL replaces every search engine. It
> is that PostgreSQL now covers enough of the search stack that we can place
> the boundary from evidence instead of habit.

## Play with it yourself

Show the repository slide and point to the repository link, demo link, and QR
code.

> If you want to run these comparisons yourself, the repository includes the
> incident corpus, database setup, retrieval implementations, demo commands,
> and evaluation harness. You can ask the same questions, change the corpus
> size, tune the indexes, and see where the tradeoffs move on your hardware.

The repository is available at `tsdb.co/pgsummit`. The live demo and QR code
point to `tsdb.co/7r1y5at2`. Test the QR code from a phone at the venue before
presenting.
Leave the contact details on screen during questions: `erin@tigerdata.com` and
`github.com/erinmikailstaples`.

Final line:

> Thank you. May your recall be high and your demo containers already warm.

## Presenter fact-check notes

- PostgreSQL 8.3 was released February 4, 2008 and integrated full-text search
  into core.
- pgvector 0.1.0 is dated April 20, 2021 in the project changelog.
- pgvector 0.5.0 is dated August 28, 2023—not September—in that changelog.
- pgvectorscale was announced June 11, 2024.
- Always describe the 28×/16× result as a Timescale benchmark and retain its
  50-million-vector, 768-dimension, 99%-recall context.
- Do not describe PostgreSQL arrays as vector search. They could store numeric
  values; they did not supply embedding semantics or ANN indexing.
- `text-embedding-3-small` defaults to 1,536 dimensions. See the
  [official model page](https://developers.openai.com/api/docs/models/text-embedding-3-small).
