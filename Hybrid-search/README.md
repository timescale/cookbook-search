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

### Option 2: Run PostgreSQL on Your Own Machine

If you prefer to run everything locally, you'll need to install the extensions yourself.

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
