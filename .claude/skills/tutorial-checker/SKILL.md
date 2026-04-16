---
name: tutorial-checker
version: 1.0.0
description: Validate that a tutorial follows the write-tutorial format and that all code runs correctly. Use when reviewing, finalizing, or QA-ing a cookbook/tutorial before shipping. Checks README structure, file completeness, code runnability, and consistency.
---

# Tutorial Checker

Validate a tutorial for structural consistency, completeness, and working code. Run this before merging or publishing any tutorial.

## How to Use

When invoked, perform ALL of the following checks in order. Report results as a checklist with pass/fail status for each item. At the end, provide a summary of what passed, what failed, and specific instructions to fix each failure.

## Phase 1: File Structure Check

Verify the tutorial folder contains the required files:

- [ ] `README.md` exists in the tutorial folder
- [ ] `setup.sql` exists (for database tutorials) OR equivalent setup script
- [ ] `requirements.txt` exists (if Python code is present)
- [ ] At least one supporting script exists (e.g., `embed.py`, `load.py`)
- [ ] `.env.example` exists at the repo root with all required env vars
- [ ] `.gitignore` at repo root excludes `.env` and includes `!.env.example`
- [ ] `LICENSE` file exists at repo root
- [ ] `CLAUDE.md` exists at repo root
- [ ] Root `README.md` links to the tutorial folder with a file index table
- [ ] No secrets or API keys are present in any committed file (check for patterns like `sk-`, `key-`, API tokens in `.env`, scripts, or SQL files)

**How to check:** Read each expected file. If missing, flag it. For secrets, grep the repo for common key patterns.

## Phase 2: README Structure Check

Read the tutorial's `README.md` and verify it follows the required section order:

- [ ] **Title** — H1 heading at the top
- [ ] **Overview** — explains what the tutorial covers, why, and what the reader gets
- [ ] **Getting Started** section exists
- [ ] **What You'll Need** — bulleted prerequisites list with bold names, descriptions, and links
- [ ] **At least two setup options** (e.g., managed service, Docker, manual install)
- [ ] **Numbered tutorial steps** — sequential Step 1, Step 2, Step 3, etc.
- [ ] **Going Further** (or equivalent) — additional tips and patterns
- [ ] **Current Limitations** — known issues or caveats
- [ ] **What's Next** — at least 4 concrete next directions with links
- [ ] **Resources** — link list at the bottom

**How to check:** Grep for the expected H2 headings. Flag any that are missing or out of order.

## Phase 3: Content Quality Check

Read through the full README and verify:

### Code Snippets
- [ ] Every code block has a **bold label** above it describing what it does
- [ ] No "orphan" code blocks (code dropped without any preceding explanation)
- [ ] SQL blocks use `sql` language tag
- [ ] Python blocks use `python` or `bash` language tags as appropriate
- [ ] Every code block that produces output includes expected output or a "you should see" description

### Concepts and Explanations
- [ ] New concepts (embeddings, BM25, RRF, etc.) are explained when first introduced
- [ ] Explanations are 2-4 sentences max with a concrete example from the tutorial's dataset
- [ ] Steps that demonstrate a technique include "What X is good at" and "Where it falls short" summaries
- [ ] Each step ends with a transition sentence connecting to the next step

### Prerequisites and Setup
- [ ] Every prerequisite links to a download/signup page
- [ ] Package manager choice is stated explicitly with alternatives linked
- [ ] Docker setup includes the exact `docker run` command
- [ ] Manual install includes platform-specific paths/commands (Linux, macOS, Windows)
- [ ] Every setup step that can fail has a verification command
- [ ] Common errors have troubleshooting guidance

### Data and Attribution
- [ ] Sample data uses a real dataset (not generic placeholders like "Document 1", "test", "foo")
- [ ] Dataset source is attributed with a link
- [ ] Dataset license is noted
- [ ] Attribution appears in both the README and any SQL/script files that contain the data

## Phase 4: Consistency Check

Verify that names and references are consistent across all files:

- [ ] Table names match across `README.md`, `setup.sql`, and all scripts
- [ ] Column names match across `README.md`, `setup.sql`, and all scripts
- [ ] Index names match across `README.md`, `setup.sql`, and all scripts
- [ ] Environment variable names in `.env.example` match what scripts expect
- [ ] `requirements.txt` lists every import used in Python scripts
- [ ] Python scripts import `load_dotenv` and load from the correct `.env` path
- [ ] The number of sample data rows is consistent between README, setup.sql, and any script output references (e.g., "Found 12 episodes")

**How to check:** Extract table names, column names, and index names from each file and cross-reference. Grep for env var names across `.env.example` and all scripts.

## Phase 5: Code Runnability Check

Actually run the code to verify it works. Perform these checks in order:

### 5a. SQL Setup
- [ ] Run `setup.sql` against a test database and confirm it completes without errors
  ```bash
  psql -h localhost -U postgres -f setup.sql
  ```
- [ ] Verify the table was created with the correct schema
  ```sql
  \d episodes
  ```
- [ ] Verify sample data was inserted with the expected row count
  ```sql
  SELECT count(*) FROM episodes;
  ```
- [ ] Verify indexes were created
  ```sql
  SELECT indexname FROM pg_indexes WHERE tablename = '<table_name>';
  ```

### 5b. Python Environment
- [ ] Create a virtual environment and install dependencies without errors
  ```bash
  cd <tutorial-folder>
  uv venv && source .venv/bin/activate
  uv pip install -r requirements.txt
  ```
- [ ] Verify all imports resolve (no missing packages)
  ```bash
  python -c "import openai; import psycopg2; from dotenv import load_dotenv; print('All imports OK')"
  ```

### 5c. Python Scripts
- [ ] Run the main script (e.g., `embed.py`) and confirm it completes successfully
- [ ] Verify the script's output matches what the README says to expect
- [ ] Run the script a second time to confirm idempotency (should report "nothing to do" or equivalent)
- [ ] Verify the data was actually written to the database (e.g., embeddings are not NULL)
  ```sql
  SELECT count(*) FROM episodes WHERE embedding IS NOT NULL;
  ```

### 5d. Tutorial Queries
Run a sample of the SQL queries from the README and verify they return results:

- [ ] At least one BM25/keyword search query returns rows
- [ ] Verify results look reasonable (relevant titles appear near the top)
- [ ] If vector search queries use `$1` placeholders, note that these require a runtime embedding (acceptable — just verify the query parses without syntax errors)

**Important:** If a database or API key is not available, skip the runnability checks and clearly note which checks were skipped and why. Do not fail the tutorial for checks that couldn't be run due to missing infrastructure.

## Phase 6: Link Check

Verify all links in the README:

- [ ] No placeholder links (e.g., `(link-to-part-1)`, `(TODO)`, `(#)`)
- [ ] Internal file links resolve (e.g., `./setup.sql`, `./embed.py`)
- [ ] GitHub repo links point to repos that exist
- [ ] External links are HTTPS (not HTTP)

**How to check:** Extract all markdown links with a regex, check internal links against the file system, and flag any obvious placeholders.

## Output Format

Report results in this format:

```markdown
# Tutorial Check: [Tutorial Name]

## Summary
- **Passed:** X / Y checks
- **Failed:** N checks
- **Skipped:** M checks (reason)

## Results

### Phase 1: File Structure
- [x] README.md exists
- [x] setup.sql exists
- [ ] requirements.txt — MISSING (embed.py imports openai but no requirements.txt)

### Phase 2: README Structure
...

### Phase 3: Content Quality
...

### Phase 4: Consistency
...

### Phase 5: Code Runnability
...

### Phase 6: Link Check
...

## Fixes Needed

1. **[Phase 1]** Create `requirements.txt` with: openai, psycopg2-binary, python-dotenv
2. **[Phase 3]** Add a bold label above the SQL block on line 142
3. ...
```

## Rules

- **Be thorough but fair.** Flag real issues, not style nitpicks.
- **Be specific in fix instructions.** "Add a bold label above the SQL block on line 142" is better than "some code blocks are missing labels."
- **Don't auto-fix.** Report what's wrong and let the user decide what to address. Only make changes if explicitly asked.
- **If code can't be run** (no database, no API key, no Docker), skip those checks and clearly state what was skipped.
- **Check for secrets aggressively.** Grep for `sk-proj-`, `sk-`, `key-`, `token`, `password` (excluding placeholder values in `.env.example`). A leaked key is the highest-priority finding.
