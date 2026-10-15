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

- **A free Tiger Cloud account** — [sign up or log in](https://console.cloud.timescale.com/). The recommended path below creates a dedicated free service, so you do not need an existing database.
- **Git** — downloads this repository. Install it from [git-scm.com](https://git-scm.com/downloads) if `git --version` does not work.
- **Python 3.11+** — runs the data loader, embedding script, and search CLI. Download it from [python.org](https://www.python.org/downloads/).
- **An OpenAI API key** — generates 1,536-dimensional embeddings with `text-embedding-3-small`. Create one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Embedding the sample makes a small billable API request.
- **uv** — this tutorial uses [uv](https://docs.astral.sh/uv/getting-started/installation/) to create a reproducible Python environment. You do not need to know Python packaging beforehand.
- **Tiger CLI** — creates the free database service and runs SQL without requiring `psql`. You will install it below.

### Download the Tutorial

If you have not cloned this repository, download it and enter the tutorial
directory. Run every remaining command from `Pg-vectorsearch` unless the guide
says otherwise.

**Clone the repository** — create a local copy and move into this cookbook:

```bash
git clone https://github.com/timescale/cookbook-search.git
cd cookbook-search/Pg-vectorsearch
```

You should now be in the folder containing `README.md`, `setup.sql`, and
`load.py`.

### Option 1: Create a Free Tiger Cloud Service (Recommended)

This path starts with a new, isolated database. A free Tiger Cloud service uses
shared compute and is enough for the 1,200-row tutorial. Creating a dedicated
service also means you can experiment or clean up without touching another
application's data.

1. **Install Tiger CLI.** Choose the command for your operating system.

   **macOS, Linux, or WSL** — run the official installer:

   ```bash
   curl -fsSL https://cli.tigerdata.com | sh
   ```

   **Windows PowerShell** — run the Windows installer:

   ```powershell
   irm https://cli.tigerdata.com/install.ps1 | iex
   ```

   Close and reopen your terminal if the installer asks you to refresh your
   shell.

2. **Verify the installation** — confirm the `tiger` command is available:

   ```bash
   tiger version
   ```

   You should see a Tiger CLI version table. If the shell says `tiger` was not
   found, open a new terminal and retry the command.

3. **Sign in to Tiger Cloud** — authenticate with the free account you created:

   ```bash
   tiger auth login
   ```

   The command opens a browser. Sign in, authorize the CLI, and select a Tiger
   Cloud project if prompted. The CLI stores the session securely; it does not
   add credentials to this repository. For a remote terminal without a browser,
   use `tiger auth login --headless` instead.

4. **Verify your login** — list the services in the selected project:

   ```bash
   tiger service list
   ```

   An empty table is fine for a new account. An authentication error means the
   login did not complete; rerun `tiger auth login`.

5. **Create a dedicated free service** — request shared CPU and memory:

   ```bash
   tiger service create --name pg-vectorsearch-tutorial --cpu shared --memory shared --region us-east-1 --environment DEV
   ```

   Provisioning normally takes less than a minute. The command waits until the
   service is ready, saves its generated database password in secure local
   credential storage, and makes it the CLI's default service. If your account
   reports a free-service limit, use an existing compatible service with Option
   2 or remove an unused service in the Tiger Cloud console.

6. **Check database connectivity** — verify the new service accepts connections:

   ```bash
   tiger db ping
   ```

   You should see that the server is accepting connections.

7. **Verify PostgreSQL and pg_vectorsearch** — check the two requirements before
   creating any objects:

   ```bash
   tiger db query --command "
   SELECT current_setting('server_version') AS server_version;
   SELECT name, default_version
   FROM pg_available_extensions
   WHERE name = 'pg_vectorsearch';"
   ```

   The first result should report PostgreSQL 18 or later. The second should
   contain one row named `pg_vectorsearch`. Your new service is ready for the
   tutorial.

### Option 2: Use an Existing Tiger Cloud Service

An existing service works when it runs PostgreSQL 18 or later and lists
`pg_vectorsearch` in `pg_available_extensions`. The cookbook creates its own
`incident_events` table and does not alter other application tables.

1. **Find the service ID** — list the services in your current project:

   ```bash
   tiger service list
   ```

   Copy the ID from the row for the service you want to use.

2. **Select the existing service** — replace `<SERVICE_ID>` with the value in
   the list:

   ```bash
   tiger config set service_id <SERVICE_ID>
   ```

   Tiger CLI should confirm that it saved the configuration value. Commands
   without an explicit service ID now target this service.

3. **Check the server and extension** — run both checks before continuing:

   ```bash
   tiger db query --command "
   SELECT current_setting('server_version') AS server_version;
   SELECT name, default_version
   FROM pg_available_extensions
   WHERE name = 'pg_vectorsearch';"
   ```

   The first result should report PostgreSQL 18 or later, and the second should
   return one extension row. If either check fails, create a new free service
   with Option 1 instead.

## Step 1: Configure the Connection

Keep credentials in a local `.env` file. The repository ignores `.env`, while
`.env.example` documents every required setting. This file connects the Python
scripts to the same service that Tiger CLI selected above.

**Create your local configuration** — copy the template:

```bash
cp .env.example .env
```

The command creates `Pg-vectorsearch/.env` without changing the example
template.

**Get the database URL** — ask Tiger CLI for the default service's connection
string:

```bash
tiger db uri --with-password
```

The output starts with `postgresql://` and ends with `sslmode=require`. It
contains the generated database password, so treat the entire URL as a secret.
Copy it, but do not paste it into chat, an issue, or a committed file.

**Set the Tiger Cloud and OpenAI credentials** — keep TLS enabled in the
connection string. Open `.env` in any text editor and replace the two
placeholder values:

```dotenv
DATABASE_URL=postgresql://tsdbadmin:your-password@your-host:5432/tsdb?sslmode=require
OPENAI_API_KEY=your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Save the file. Do not commit it or include it in logs and screenshots. The next
step installs the local Python tools and verifies these settings without
printing either secret.

> **Keep the URL intact:** passwords sometimes contain punctuation. Paste the
> complete value returned by Tiger CLI; do not add quotes or edit individual
> URL characters.

## Step 2: Install the Python Dependencies

uv creates an isolated `.venv` and installs the exact package versions recorded
in `uv.lock`. The project dependencies are declared in `pyproject.toml`, while
`requirements.txt` provides a pip-compatible alternative. You do not need to
activate the environment when using `uv run`.

If `uv --version` already works, skip directly to creating the environment.
Otherwise, install uv for your operating system.

**Install uv on macOS, Linux, or WSL** — run the official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Install uv on Windows PowerShell** — run the Windows installer:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen the terminal if `uv --version` is not immediately available.

**Create the environment** — reproduce the committed dependency set:

```bash
uv sync --locked
```

You should see uv create `.venv` and complete without dependency errors. If
`uv` reports that the lockfile needs updating after an intentional dependency
change, run `uv lock`, review `uv.lock`, and repeat `uv sync --locked`.

**Verify imports** — make sure every runtime package is available:

```bash
uv run python -c "import openai, psycopg, dotenv; print('Python dependencies ready')"
```

The command should print `Python dependencies ready`. Now verify that the
values in `.env` let Python connect to Tiger Cloud.

**Verify the saved database URL** — connect through the same helper used by all
three Python scripts:

```bash
uv run python -c "from load import connect_db; c = connect_db(); print(c.execute('SELECT current_user, current_database()').fetchone()); c.close()"
```

You should see a tuple containing `tsdbadmin` and `tsdb`. If you see an
authentication error, rerun `tiger db uri --with-password` and replace the
entire `DATABASE_URL` value in `.env`. If the error mentions host `db`, the file
still contains a Docker-only URL rather than the Tiger Cloud URL.

With the Python environment and database connection ready, create the vector
type and table in Tiger Cloud.

## Step 3: Create the Extension and Table

`pg_vectorsearch` supplies the native `vec32` type and the PRISM index access
method. This example uses `vec32(1536)` because
`text-embedding-3-small` returns exactly 1,536 floating-point values.

**Run the idempotent schema setup** — create the extension and table:

```bash
tiger db query --file setup.sql
```

You should see `CREATE EXTENSION`, `CREATE TABLE`, and `ALTER TABLE` on the first
run. `NOTICE` messages saying objects already exist are safe on later runs.

**Verify the installed version and vector column** — inspect the extension and
schema:

```bash
tiger db query --command "
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
tiger db query --command "
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

If OpenAI reports an authentication error, verify `OPENAI_API_KEY` in `.env`
and rerun the command; completed rows remain stored. If it reports an
unsupported dimensions parameter, use a `text-embedding-3` model—the scripts
request 1,536 dimensions to match the database column.

**Verify vector coverage and dimensions** — all rows should be populated:

```bash
tiger db query --command "
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
tiger db query --file indexes.sql
```

You should see five `CREATE INDEX` results on the first run: three B-tree
indexes for time and metadata filters, one GIN full-text index, and one PRISM
vector index.

**Verify the PRISM access method** — inspect the catalog directly:

```bash
tiger db query --command "
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
tiger db query --command "
SELECT occurred_at, service, incident_id, content
FROM incident_events
WHERE content_tsv @@ websearch_to_tsquery('english', 'SQLSTATE 53300');"
```

You should see the database pool exhaustion event containing `SQLSTATE 53300`.
Keyword search is precise here, but a phrase such as “database capacity ran
out” may not match; semantic search handles that paraphrase.

**Find Kubernetes terminology** — search for the literal failure modes:

```bash
tiger db query --command "
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
tiger db query --command "SELECT * FROM prism_index_settings('incident_events_embedding_prism_idx');"
```

You should see settings including the vector dimension, cosine metric, number
of lists, and effective `nprobe`. Keep the automatic defaults until recall and
latency measurements justify a change.

You have now created a free cloud database, loaded and embedded a reproducible
dataset, built a PRISM index, and tested semantic plus exact keyword search.

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
tiger db query --command "REINDEX INDEX incident_events_embedding_prism_idx;"
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
tiger db query --command "CALL prism_rebalance('incident_events_embedding_prism_idx');"
```

PostgreSQL should report `CALL`. Measure recall before and after maintenance on
your own workload rather than scheduling it blindly.

### Start Over Without Deleting the Cloud Service

Dropping the cookbook table removes its data and indexes while leaving the
Tiger Cloud service and extension available for other databases.

**Remove cookbook data** — this is destructive and cannot be undone without a
backup:

```bash
tiger db query --command "DROP TABLE IF EXISTS incident_events;"
```

PostgreSQL should report `DROP TABLE`. Run `setup.sql`, `load.py`, `embed.py`,
and `indexes.sql` to recreate the example.

### Pause or Delete the Tutorial Service

You can pause the service when you are finished and start it again later. If
you no longer need any of its data, delete it from Tiger Cloud instead.

**Find the tutorial service ID** — locate the row named
`pg-vectorsearch-tutorial`:

```bash
tiger service list
```

Copy its service ID before running either command below.

**Pause the service** — preserve its data while making it unavailable:

```bash
tiger service stop <SERVICE_ID>
```

Tiger CLI should report that the service is inactive. Run
`tiger service start <SERVICE_ID>` when you want to resume.

**Delete the service permanently** — remove the database and all of its data:

```bash
tiger service delete <SERVICE_ID>
```

Tiger CLI asks you to type the service ID before deleting anything. This cannot
be undone, so use the pause command if you may want the tutorial data later.

## Current Limitations

- **Alpha extension:** `pg_vectorsearch` is intended for testing, not production. Upgrades between prereleases may require recreating the extension and indexes.
- **PostgreSQL version:** the extension requires PostgreSQL 18 or later.
- **Small demonstration dataset:** 1,200 rows teach the workflow but do not represent large-scale benchmark performance; the planner may prefer a sequential scan.
- **Manual maintenance under churn:** inserts, updates, and deletes work, but heavy changes can require `prism_rebalance` or `REINDEX`.
- **OpenAI dependency:** embedding and query generation require network access, an API key, and incur usage charges.
- **Post-filter behavior:** selective `WHERE` filters are applied after ANN candidates are produced and can return fewer rows than requested when vector proximity and the filter are poorly correlated.

## What's Next

- **Measure recall** — generate exact nearest-neighbor ground truth and compare it with several `prism.nprobe` values using the [pg_vectorsearch tuning guide](https://github.com/timescale/pg_vectorsearch/blob/main/docs/tuning.md).
- **Expand the dataset** — add incident families and routine templates to [`generate_data.py`](./generate_data.py), then regenerate and re-embed the sample.
- **Add hybrid ranking** — combine semantic results with PostgreSQL full-text scores using Reciprocal Rank Fusion, following the repository's [Hybrid Search tutorial](../Hybrid-search/README.md).
- **Integrate an application** — call the parameterized query in [`search.py`](./search.py) from an API, support tool, or incident-response interface.
- **Use existing pgvector data** — follow the upstream [existing pgvector tables guide](https://github.com/timescale/pg_vectorsearch#existing-pgvector-tables) to build PRISM on compatible `vector` or `halfvec` columns without rewriting them.

## Resources

- [pg_vectorsearch on GitHub](https://github.com/timescale/pg_vectorsearch) — extension source, SQL usage, status, and build documentation.
- [pg_vectorsearch tuning guide](https://github.com/timescale/pg_vectorsearch/blob/main/docs/tuning.md) — `nprobe`, index parameters, query behavior, and inspection functions.
- [Announcing pg_vectorsearch](https://www.tigerdata.com/blog/announcing-pg_vectorsearch-scalable-open-source-vector-search-postgresql) — PRISM design, benchmark context, and current limitations.
- [Tiger Cloud](https://www.tigerdata.com/cloud) — managed PostgreSQL for the database used by this cookbook.
- [Tiger CLI](https://github.com/timescale/tiger-cli) — installs the `tiger` command used to create the free service and execute SQL.
- [Tiger Cloud connection details](https://www.tigerdata.com/docs/integrate/find-connection-details) — where to find the host, port, database, user, and password.
- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings) — embedding concepts and API usage.
