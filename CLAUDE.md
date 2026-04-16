# cookbook-search

A collection of step-by-step tutorials demonstrating search capabilities in PostgreSQL and Tiger Data.

## Project Structure

```
cookbook-search/
├── .gitignore                # Excludes .env, caches, data files
├── LICENSE                   # Apache 2.0
├── README.md                 # Repo overview, prerequisites, getting started
├── CLAUDE.md                 # This file
└── Hybrid-search/            # First cookbook
    ├── README.md             # Full tutorial walkthrough
    ├── setup.sql             # One-command DB setup
    ├── embed.py              # Embedding generation script
    ├── requirements.txt      # Python dependencies
    ├── .env.example          # Template for API keys (copy to .env)
    └── .env                  # Your actual keys (gitignored)
```

## Skills

This repo includes two custom Claude skills:

### `/write-tutorial` — Create a new tutorial

Use when writing a new cookbook or tutorial from scratch. Enforces the established format:
- Consistent section ordering (Overview → Prerequisites → Setup Options → Steps → Going Further → Limitations → What's Next → Resources)
- Labeled code snippets with descriptions
- Concepts explained when first introduced
- Real datasets with proper attribution
- Runnable end-to-end from zero setup
- Supporting files: `setup.sql`, Python scripts with `.env` support, `requirements.txt`

### `/tutorial-checker` — Validate an existing tutorial

Use before merging or publishing to verify a tutorial meets quality standards. Runs six phases of checks:
1. **File structure** — verifies all required files exist and no secrets are committed
2. **README structure** — confirms sections follow the correct order
3. **Content quality** — checks that every code block is labeled, concepts are explained, and transitions exist
4. **Consistency** — cross-references table/column/index names across README, SQL, and scripts
5. **Code runnability** — runs `setup.sql`, installs dependencies, executes scripts, and tests sample queries
6. **Link check** — flags placeholder links, broken internal links, and HTTP (non-HTTPS) URLs

Reports results as a pass/fail checklist with specific fix instructions for each failure.

## Conventions

- **Database:** PostgreSQL 17+ with pg_textsearch and pgvectorscale extensions
- **Python:** 3.9+, managed with uv (link to pip/conda as alternatives)
- **Environment variables:** stored in `.env` within each cookbook folder, loaded via `python-dotenv`
- **SQL setup files:** idempotent with `IF NOT EXISTS`, commented section headers
- **License:** Apache 2.0 for the repo; dataset licenses noted individually
- **Sample data:** Use real, attributed datasets — avoid generic placeholders

## Adding a New Cookbook

1. Create a new folder at the repo root (e.g., `Full-text-search/`)
2. Use `/write-tutorial` to scaffold the README and supporting files
3. Add an entry to the root README's "What's Inside" table
4. Include any new Python dependencies in a `requirements.txt` within the folder
5. Add a `.env.example` in the cookbook folder with any required env vars
6. Run `/tutorial-checker` to validate everything before merging
