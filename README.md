# Tiger Data Search Cookbook

A collection of cookbooks, tutorials, and reference implementations showcasing the different search capabilities available within **Tiger Data** and **PostgreSQL**.

## What's Inside

Each folder contains a self-contained cookbook focused on a specific search approach, complete with example queries, schema setup, and explanations of when and why you'd reach for that technique.

| Cookbook | Description |
|---------|-------------|
| [Hybrid Search](./Hybrid-search/) | Combining BM25 keyword search with vector similarity search using pg_textsearch and pgvectorscale, fused with Reciprocal Rank Fusion (RRF) |

## Who This Is For

- Developers building search features on Tiger Data or PostgreSQL
- Teams evaluating which search approach fits their use case
- Anyone curious about what's possible with search in Postgres

## Prerequisites

Before diving into any cookbook, make sure you have the following:

- **PostgreSQL 17 or 18** — via [Tiger Cloud](https://console.cloud.timescale.com), [Docker](https://github.com/timescale/timescaledb-docker-ha), or a [local install](https://www.postgresql.org/download/)
- **Python 3.9+** — [python.org/downloads](https://www.python.org/downloads/)
- **A Python package manager** — we use [uv](https://docs.astral.sh/uv/) in the tutorials, but [pip](https://pip.pypa.io/) and [conda](https://docs.conda.io/) work too
- **An OpenAI API key** — for generating embeddings. Get one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

## Getting Started

1. **Clone this repository**

   ```bash
   git clone https://github.com/tigerdatadev/cookbook-search.git
   cd cookbook-search
   ```

2. **Set up your environment variables**

   Copy the example environment file and add your API key:

   ```bash
   cp .env.example .env
   ```

   Open `.env` and replace the placeholder with your actual OpenAI key:

   ```
   OPENAI_API_KEY=your-key-here
   ```

3. **Pick a cookbook and follow the tutorial**

   Each cookbook folder has its own README with step-by-step instructions. Start with the [Hybrid Search](./Hybrid-search/) cookbook:

   | File | What it does |
   |------|-------------|
   | [`Hybrid-search/README.md`](./Hybrid-search/README.md) | Full walkthrough — database setup, data loading, embeddings, search queries |
   | [`Hybrid-search/setup.sql`](./Hybrid-search/setup.sql) | One-command setup: creates extensions, table, sample data, and indexes |
   | [`Hybrid-search/embed.py`](./Hybrid-search/embed.py) | Generates embeddings for the sample data using OpenAI's API |
   | [`Hybrid-search/requirements.txt`](./Hybrid-search/requirements.txt) | Python dependencies for the embedding script |

## Contributing

Have a search pattern or technique you'd like to add? Open a PR! Each cookbook should include:

- A `README.md` with a step-by-step tutorial explaining the approach
- Example SQL or code demonstrating the technique
- Sample data or a script to generate it
- A `requirements.txt` if any Python dependencies are needed

## License

This repository is licensed under the [Apache License 2.0](./LICENSE). Sample data in the Hybrid Search cookbook uses transcripts from the [Conduit podcast](https://www.relay.fm/conduit) via [kjaymiller/conduit-transcripts](https://github.com/kjaymiller/conduit-transcripts) (MIT License, Jay Miller).
