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
- **Python 3.9+** — We'll be using a Python script to generate embeddings for each episode using OpenAI's API. Download Python from [python.org](https://www.python.org/downloads/) if you don't have it installed.
- **An OpenAI API key** — Needed to generate embeddings with `text-embedding-3-small`. Get one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
- **A Python package manager** — We'll be using [uv](https://docs.astral.sh/uv/) as the package manager for this tutorial, but feel free to use your package manager of choice. [pip](https://pip.pypa.io/) and [conda](https://docs.conda.io/) will also work here.

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

pg_textsearch needs to be loaded when PostgreSQL starts up. This requires a one-time change to your `postgresql.conf` file and a server restart.

**2a. Find your `postgresql.conf` file**

The location depends on how PostgreSQL was installed. Run this in a SQL session (e.g. `psql`) to get the exact path:

```sql
SHOW config_file;
```

Common locations by platform:

| Platform | Typical path |
|---|---|
| Linux (apt/deb) | `/etc/postgresql/17/main/postgresql.conf` |
| Linux (yum/rpm) | `/var/lib/pgsql/17/data/postgresql.conf` |
| macOS (Homebrew) | `/usr/local/var/postgresql@17/postgresql.conf` or `/opt/homebrew/var/postgresql@17/postgresql.conf` |
| macOS (Postgres.app) | `~/Library/Application Support/Postgres/var-17/postgresql.conf` |
| macOS (EDB installer) | `/Library/PostgreSQL/17/data/postgresql.conf` |
| Windows (EDB installer) | `C:\Program Files\PostgreSQL\17\data\postgresql.conf` |

> **Tip:** Replace `17` with `18` in any of the paths above if you're running PostgreSQL 18.

**2b. Edit the file**

Open `postgresql.conf` in a text editor and find the `shared_preload_libraries` line. It may be commented out (starting with `#`):

```
#shared_preload_libraries = ''    # (change requires restart)
```

Update it to:

```
shared_preload_libraries = 'pg_textsearch'
```

If `shared_preload_libraries` already has other extensions listed, add `pg_textsearch` to the comma-separated list:

```
shared_preload_libraries = 'existing_extension,pg_textsearch'
```

> **Note:** Editing this file may require elevated permissions. Use `sudo` on Linux/macOS, or run your editor as Administrator on Windows.

**2c. Restart PostgreSQL**

The `shared_preload_libraries` setting only takes effect on server start, so a restart is required (a reload is not enough).

Linux (systemd):
```bash
sudo systemctl restart postgresql
```

macOS (Homebrew):
```bash
brew services restart postgresql@17
```

macOS (EDB installer):
```bash
sudo -u postgres /Library/PostgreSQL/17/bin/pg_ctl restart -D /Library/PostgreSQL/17/data
```

Windows (Command Prompt as Administrator):
```cmd
net stop postgresql-x64-17 && net start postgresql-x64-17
```

**2d. Verify it loaded**

Reconnect to your database and confirm pg_textsearch is in the preloaded libraries:

```sql
SHOW shared_preload_libraries;
```

You should see `pg_textsearch` in the output. If it's not there, double-check that you edited the correct `postgresql.conf` (re-run `SHOW config_file;` to confirm) and that you fully restarted (not just reloaded) the server.

**Step 3: Create the extensions in your database**

**3a. Connect to your database**

Use `psql` or any SQL client to connect. If you're running PostgreSQL locally with the default settings:

```bash
psql -h localhost -U postgres
```

You'll be prompted for the password you set during PostgreSQL installation.

> **Tip:** If you're connecting to a specific database (not the default `postgres` database), add `-d your_database_name` to the command.

**3b. Install the keyword search extension (pg_textsearch)**

```sql
CREATE EXTENSION pg_textsearch;
```

You should see:

```
CREATE EXTENSION
```

If you get `ERROR: extension "pg_textsearch" is not available` or similar, the extension files weren't installed correctly in Step 1. Double-check that you downloaded the right package for your PostgreSQL version and OS, and that the files are in PostgreSQL's extension directory.

If you get `ERROR: pg_textsearch must be loaded via shared_preload_libraries`, go back to Step 2 and make sure you updated `postgresql.conf` and restarted the server.

**3c. Install the vector search extension (pgvectorscale)**

```sql
CREATE EXTENSION vectorscale CASCADE;
```

The `CASCADE` keyword automatically installs **pgvector** as a dependency, so you don't need to install it separately. You should see:

```
NOTICE:  installing required extension "vector"
CREATE EXTENSION
```

> **Note:** If pgvector is already installed, the `NOTICE` line won't appear — that's fine.

**3d. Verify both extensions are installed**

Run this query to confirm everything is in place:

```sql
SELECT extname, extversion FROM pg_extension WHERE extname IN ('pg_textsearch', 'vectorscale', 'vector');
```

You should see three rows:

```
   extname     | extversion
---------------+------------
 vector        | 0.8.0
 pg_textsearch | 1.0.0
 vectorscale   | 0.7.0
```

(Your version numbers may differ — that's fine as long as all three appear.)

You're all set! Continue to the next section to create the table and load sample data.

---

## Step 1: Create a Table with Text and Embeddings

> **Quick start:** To run all the setup at once (extensions, table, data, indexes), use the included [`setup.sql`](./setup.sql) file:
> ```bash
> psql -h localhost -U postgres -f setup.sql
> ```

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

---

## Step 2: Generate Embeddings

An **embedding** is a list of numbers (a vector) that represents the meaning of a piece of text. Texts that are about similar topics end up with similar vectors, which is what lets vector search find semantically related results even when they don't share the same keywords. For example, an episode about "imposter syndrome" and one about "self-doubt at work" would have embeddings that are close together, even though the words are different.

The `embedding` column is currently empty. We'll be using a Python script to generate embeddings for each episode using OpenAI's `text-embedding-3-small` model and write them back to the database.

We'll be using [uv](https://docs.astral.sh/uv/) as a package manager for this, but feel free to use your package manager of choice.

**2a. Install uv (if you don't have it)**

Install uv with:

macOS / Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> **Using a different package manager?** That's fine — substitute the `uv` commands below:
> - **pip:** `pip install -r requirements.txt`
> - **conda:** `conda install openai psycopg2-binary python-dotenv`

**2b. Set up your environment**

From the `Hybrid-search/` directory, create a virtual environment and install dependencies:

```bash
cd Hybrid-search
uv venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

**2c. Configure your API key**

Copy the example environment file and add your OpenAI API key:

```bash
cp ../.env.example ../.env
```

Open the `.env` file and replace the placeholder with your actual key:

```
OPENAI_API_KEY=your-key-here
```

> **Where do I get an API key?** Sign up or log in at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) and create a new secret key.

**2d. Run the embedding script**

```bash
python embed.py
```

You should see output like:

```
Found 12 episodes without embeddings.
Generating embeddings with text-embedding-3-small...
Updating database...
Done! Embedded 12 episodes.
```

The script is idempotent — it only embeds episodes where `embedding IS NULL`, so you can safely re-run it if you add more data later.

**2e. Verify the embeddings**

Back in `psql`, confirm the embeddings were written:

```sql
SELECT id, title, left(embedding::text, 40) AS embedding_preview
FROM episodes
LIMIT 3;
```

You should see a truncated vector for each row instead of `NULL`.

---

## Step 3: Create Indexes

Now that we have data and embeddings, we need to create indexes so PostgreSQL can search efficiently. Without indexes, every query would scan every row — fine for 12 episodes, but slow for thousands.

We'll create two indexes, one for each search method we're going to use:

**3a. BM25 index for keyword search**

```sql
CREATE INDEX episodes_bm25_idx ON episodes
  USING bm25(description) WITH (text_config = 'english');
```

This creates a pg_textsearch BM25 index on the `description` column. The `text_config = 'english'` setting enables English stemming (so "productivity" also matches "productive") and removes common stopwords like "the" and "is."

**3b. StreamingDiskANN index for vector search**

```sql
CREATE INDEX episodes_embedding_idx ON episodes
  USING diskann (embedding vector_cosine_ops);
```

This creates a pgvectorscale StreamingDiskANN index on the `embedding` column. Unlike pgvector's built-in HNSW index, DiskANN stores the graph on disk rather than requiring the entire index to fit in RAM — a big advantage when you have a large number of embeddings.

With both indexes in place, we're ready to search.

---

## Step 4: Try Keyword Search (BM25)

Let's start with keyword search to see how BM25 works on its own. This is the kind of search you're used to — type in some words, get back results that contain those words, ranked by relevance.

pg_textsearch uses the `<@>` operator to score how well a row matches your search terms. Scores are negative so that PostgreSQL's default ascending `ORDER BY` puts the most relevant results first (a score of -15.3 is more relevant than -8.2).

**Basic keyword search** — find episodes that match "burnout productivity":

```sql
SELECT title, description <@> 'burnout productivity' AS score
FROM episodes
ORDER BY description <@> 'burnout productivity'
LIMIT 10;
```

You should see episodes like "The Conduit Burnout Candle" and "Happiness First, Productivity Second" near the top — they contain the words we searched for.

**Keyword search with a date filter** — same idea, but only episodes from 2023 onward. PostgreSQL detects the `<@>` operator and uses the BM25 index automatically, so you can freely combine it with `WHERE` clauses:

```sql
SELECT title, description <@> 'help' AS score
FROM episodes
WHERE pub_date >= '2023-01-01'
ORDER BY description <@> 'help'
LIMIT 10;
```

**What BM25 is good at:** finding exact keyword matches. If someone searches for "imposter syndrome," BM25 will find it.

**Where it falls short:** if someone searches for "feeling like a fraud at work," BM25 won't match the imposter syndrome episode because none of those exact words appear in its description. That's where vector search comes in.

---

## Step 5: Try Vector Search (Semantic Similarity)

Vector search uses the embeddings we generated in Step 2 to find episodes by *meaning* rather than keywords. Two pieces of text that are about the same topic will have similar embeddings, even if they use completely different words.

The `<=>` operator computes cosine distance between two vectors. Unlike BM25 scores, lower values mean more similar (0 = identical, 1 = completely unrelated).

**Semantic search** — find episodes closest in meaning to a query vector. Replace `$1` with an embedding generated from your search text (see the note below):

```sql
SELECT title, embedding <=> $1 AS distance
FROM episodes
ORDER BY embedding <=> $1
LIMIT 10;
```

> **How do I get a query vector?** You'd generate an embedding for your search text the same way we embedded the episodes — by calling the OpenAI embeddings API. The [`embed.py`](./embed.py) script shows how to do this. In a real application, your app would generate the query embedding at search time and pass it as a parameter.

**What vector search is good at:** finding semantically related content. A search for "feeling like a fraud at work" would surface the imposter syndrome episode, even though those exact words don't appear anywhere in its description.

**Where it falls short:** it can miss results that match on specific terms. If someone searches for "episode 100," BM25 finds it instantly, but vector search might rank it lower because "episode 100" doesn't carry strong semantic meaning.

Each method has blind spots — which is exactly why we combine them in the next step.

---

## Step 6: Hybrid Search with Reciprocal Rank Fusion (RRF)

This is where everything comes together. In Steps 4 and 5, we ran keyword search and vector search independently. Each one is good at different things — BM25 catches exact word matches, while vector search catches meaning. But what if we want the best of both?

**Reciprocal Rank Fusion (RRF)** is a simple technique for combining ranked results from multiple search methods into a single list. The idea: instead of trying to compare raw scores across different systems (which use different scales), RRF only looks at **rank position**. An episode ranked #1 by either method gets a high score. An episode ranked #1 by *both* methods gets an even higher score. Episodes that only one method found still make it into the final list, just ranked lower.

The formula for each result is `1 / (k + rank)`, where `k` is a smoothing constant (typically 60). You sum this across all the search methods, and sort by the total. That's it — no normalization, no tuning, and it works surprisingly well in practice.

**Hybrid search with RRF** — this query runs both search methods and fuses the results. We'll walk through each part below:

```sql
-- Step 1: Get the top 20 BM25 keyword matches
WITH bm25_results AS (
  SELECT id, ROW_NUMBER() OVER (
    ORDER BY description <@> 'mental health boundaries'
  ) AS rank
  FROM episodes
  ORDER BY description <@> 'mental health boundaries'
  LIMIT 20
),
-- Step 2: Get the top 20 vector similarity matches
vector_results AS (
  SELECT id, ROW_NUMBER() OVER (
    ORDER BY embedding <=> $1  -- $1 is the query embedding vector
  ) AS rank
  FROM episodes
  ORDER BY embedding <=> $1
  LIMIT 20
)
-- Step 3: Fuse the two ranked lists using RRF
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

**Breaking down what's happening:**

1. **`bm25_results`** — runs a keyword search for "mental health boundaries" and assigns each result a rank (1 = best match)
2. **`vector_results`** — runs a vector search using the query embedding and assigns ranks the same way
3. **The final `SELECT`** — joins both result sets by episode ID and computes an RRF score for each. The `COALESCE(..., 0)` ensures that episodes found by only one method still get a score (just lower). The `60` is the standard smoothing constant that prevents top-ranked results from dominating too heavily.

**An example to make it concrete:** Imagine a user searches for "how do I deal with feeling like a fraud at work?"

- **BM25 finds:** "Eating the Devil's Spaghetti: Combating Imposter Syndrome" — it matches on "imposter" after stemming
- **Vector search finds:** episodes about burnout, boundaries, and mental health — semantically related even though the words are different
- **RRF fuses both:** the imposter syndrome episode ranks highest (found by both methods), while related episodes about self-doubt and mental health also surface higher than they would with either method alone

That's hybrid search. You get the precision of keywords and the recall of semantic similarity in a single ranked list.

---

## Going Further

The tutorial above covers the core pattern. This section collects tips and techniques for when you're ready to take hybrid search into production.

### Search across multiple columns

Each BM25 index covers a single text column. To search across both title and description, create a generated column that combines them:

```sql
ALTER TABLE episodes ADD COLUMN search_text text
  GENERATED ALWAYS AS (title || ' ' || description) STORED;

CREATE INDEX ON episodes USING bm25(search_text)
  WITH (text_config = 'english');
```

Now queries against `search_text` will match words in either the title or description.

### Highlight matched terms in results

Use PostgreSQL's built-in `ts_headline()` to show which words matched, with surrounding context. This is useful for building search result snippets in a UI:

```sql
SELECT title,
  ts_headline('english', description, to_tsquery('english', 'productivity')),
  description <@> 'productivity' AS score
FROM episodes
ORDER BY description <@> 'productivity'
LIMIT 10;
```

This returns the description with matching terms wrapped in `<b>` tags (configurable).

### Filter out low-relevance results

By default, BM25 returns a ranked list regardless of how weak the match is. Use `to_bm25query()` with a threshold to discard results below a minimum relevance score:

```sql
SELECT title, description <@> to_bm25query('burnout', 'episodes_bm25_idx') AS score
FROM episodes
WHERE description <@> to_bm25query('burnout', 'episodes_bm25_idx') < -1.0
ORDER BY description <@> to_bm25query('burnout', 'episodes_bm25_idx')
LIMIT 10;
```

This only returns episodes with a BM25 score below -1.0 (remember, more negative = more relevant).

### Phrase search workaround

pg_textsearch 1.0 doesn't support native phrase queries (matching exact multi-word sequences). You can work around this by over-fetching from the BM25 index and then post-filtering with `ILIKE`:

```sql
SELECT * FROM (
  SELECT * FROM episodes
  ORDER BY description <@> 'year end planning'
  LIMIT 100  -- over-fetch to compensate for the post-filter
) sub
WHERE description ILIKE '%end-of-year%'
LIMIT 10;
```

The inner query uses BM25 to find the top 100 candidates, and the outer query filters down to rows containing the exact phrase.

### Tune vector search accuracy

pgvectorscale's StreamingDiskANN index uses smart defaults. If you need higher accuracy (at the cost of slightly slower queries), increase the rescore parameter:

```sql
SET LOCAL diskann.query_rescore = 150;

SELECT * FROM episodes
ORDER BY embedding <=> $1
LIMIT 10;
```

Higher values mean more candidates are re-scored for accuracy. The default works well for most cases.

### Speed up index builds for large tables

For tables with millions of rows, use parallel index builds to speed things up:

```sql
SET max_parallel_maintenance_workers = 4;
SET maintenance_work_mem = '256MB';  -- minimum 64MB for parallel builds

CREATE INDEX ON large_table USING bm25(content)
  WITH (text_config = 'english');

CREATE INDEX ON large_table
  USING diskann (embedding vector_cosine_ops);
```

### Compact the BM25 index after bulk inserts

If you bulk-insert a lot of data, the BM25 index may have multiple segments from repeated writes. Merge them for faster queries:

```sql
SELECT bm25_force_merge('episodes_bm25_idx');
```

This is a one-time operation — you don't need to run it after every insert, just after large bulk loads.

---

## Current Limitations

Things to be aware of in pg_textsearch 1.0:

- **No phrase queries**: The index stores term frequencies but not positions. Use the over-fetch + post-filter pattern shown above.
- **OR-only query semantics**: All query terms are implicitly OR'd. AND/OR/NOT operators are planned for a post-1.0 release.
- **No highlighting from the index**: Use PostgreSQL's built-in `ts_headline()` on the result set.
- **Single column per index**: Use a generated column to combine multiple fields.
- **PL/pgSQL requires explicit index names**: Use `to_bm25query('query', 'index_name')` inside PL/pgSQL, DO blocks, or stored procedures.
- **shared_preload_libraries required**: Requires a server restart for self-hosted installations. Handled automatically on Tiger Cloud.

---

## What's Next

You've built a working hybrid search system from scratch. Here are some directions to explore from here:

- **Load the full dataset** — The [conduit-transcripts](https://github.com/kjaymiller/conduit-transcripts) repo has 119 episodes. Try loading all of them with their full transcript text (not just descriptions) and see how hybrid search performs at a larger scale.
- **Build a search API** — Wrap the hybrid search query in a small Python or Node.js API that generates the query embedding on the fly and returns ranked results as JSON.
- **Try different embedding models** — We used OpenAI's `text-embedding-3-small` (1536 dimensions). Experiment with `text-embedding-3-large` (3072 dimensions) or open-source models like [nomic-embed-text](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) via [Ollama](https://ollama.com/) for a fully local setup.
- **Add a reranker** — RRF is a great starting point, but you can improve result quality further by adding a cross-encoder reranker (e.g., [Cohere Rerank](https://cohere.com/rerank) or an open-source model) as a final pass over the top results.
- **Plug it into a RAG pipeline** — Use the hybrid search results as context for an LLM. Feed the top-ranked episode descriptions (or full transcripts) into a model like Claude to answer natural language questions about the podcast.
- **Explore the pg_textsearch_demo** — Raja Rao's [pg_textsearch_demo](https://github.com/rajaraodv/pg_textsearch_demo) is a full working app with a web UI that demonstrates hybrid search end to end.

## Resources

- [pg_textsearch on GitHub](https://github.com/timescale/pg_textsearch)
- [pgvectorscale on GitHub](https://github.com/timescale/pgvectorscale)
- [pg_textsearch_demo](https://github.com/rajaraodv/pg_textsearch_demo) — working hybrid search demo with web UI
- [Conduit Podcast](https://www.relay.fm/conduit) — the podcast used as sample data in this cookbook
- [Conduit Transcripts](https://github.com/kjaymiller/conduit-transcripts) — MIT-licensed transcripts by Jay Miller
- [Tiger Cloud](https://www.tigerdata.com/search) — try it without any setup
- [Understanding DiskANN](https://www.tigerdata.com/blog/understanding-diskann)
- [It's 2026, Just Use Postgres](https://www.tigerdata.com/blog/its-2026-just-use-postgres)
- [You Don't Need Elasticsearch](https://www.tigerdata.com/blog/you-dont-need-elasticsearch-bm25-is-now-in-postgres)
