# Tiger Data Search Cookbook

Practical tutorials and demos for building search with Tiger Data and
PostgreSQL. Each project explains the retrieval techniques it uses, includes
runnable examples, and documents where PostgreSQL-native search fits compared
with a dedicated search engine.

## Projects

| Project | Best for | What it covers |
|---|---|---|
| [Hybrid Search](./Hybrid-search/) | A focused, beginner-friendly tutorial | BM25 keyword search, vector similarity, and Reciprocal Rank Fusion (RRF) with `pg_textsearch` and `pgvectorscale`. |
| [State of Search](./State-of-Search/) | An advanced demo, presentation, and evaluation harness | Exact lookup, fuzzy matching, PostgreSQL full-text search, BM25, exact and approximate vector search, hybrid retrieval, and an optional Elasticsearch comparison. |

## Choose a starting point

### Hybrid Search

Choose this project if you want the shortest path to a working hybrid-search
example. It includes a small attributed dataset, one SQL setup file, and one
Python embedding script.

Start with the [Hybrid Search tutorial](./Hybrid-search/README.md).

### State of Search

Choose this project if you want to compare retrieval methods over the same
incident corpus, run a Streamlit demo, or present the accompanying Reveal.js
deck. It includes Docker Compose services, data preparation and evaluation
commands, SQL indexes, a terminal demo, a web interface, and speaker material.

Start with the [State of Search guide](./State-of-Search/README.md). The project
is self-contained, including its deterministic data generator and seed files.

## Requirements

Requirements vary by project:

| Requirement | Hybrid Search | State of Search |
|---|---:|---:|
| PostgreSQL with the documented search extensions | Required | Provided by Docker Compose |
| Docker | Optional | Required for the full demo |
| Python | 3.9+ | 3.11+ inside the app image |
| Node.js | Not required | 20.19.x or 22.12+ for the slides |
| OpenAI API key | Required for embeddings | Required for semantic-search preparation and uncached query embeddings |
| Elasticsearch | Not required | Optional Compose profile |

Tiger Cloud can provide a hosted PostgreSQL service with the required
extensions. The local instructions use Docker and the
[`timescaledb-ha`](https://github.com/timescale/timescaledb-docker-ha) image.

## Repository layout

```text
cookbook-search/
├── Hybrid-search/       # Focused hybrid-search tutorial
├── State-of-Search/     # Multi-method demo, evaluation harness, and slides
├── CLAUDE.md            # Repository guidance for AI coding tools
├── LICENSE              # Apache License 2.0
└── README.md            # Repository overview
```

Every project has its own README and environment template. Keep secrets in a
local `.env` file; `.env` files are ignored by Git, while `.env.example` files
document the required variables.

## Quick start

Clone the repository, then follow the guide for the project you selected:

```bash
git clone https://github.com/timescale/cookbook-search.git
cd cookbook-search
```

For Hybrid Search:

```bash
cd Hybrid-search
cp .env.example .env
```

For the State of Search presentation:

```bash
cd State-of-Search
nvm use # optional; uses .nvmrc
npm install
npm run dev
```

See the project README before adding credentials or starting services:

- [Hybrid Search setup and walkthrough](./Hybrid-search/README.md)
- [State of Search setup, demo, evaluation, and presentation](./State-of-Search/README.md)

## Contributing

Keep each cookbook self-contained and include:

- A step-by-step README with prerequisites, setup, verification, limitations,
  and cleanup guidance.
- Runnable SQL or application code.
- Sample data or a deterministic generation script with source attribution.
- An `.env.example` file for required configuration, with no real credentials.
- A dependency manifest and lockfile when the ecosystem supports one.

Before opening a pull request, run the relevant build, syntax, and link checks
documented by the project.

## License

This repository is licensed under the [Apache License 2.0](./LICENSE). The
Hybrid Search sample data uses transcripts from the
[Conduit podcast](https://www.relay.fm/conduit), sourced from
[`kjaymiller/conduit-transcripts`](https://github.com/kjaymiller/conduit-transcripts)
under the MIT License.
