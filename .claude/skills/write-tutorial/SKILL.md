---
name: write-tutorial
version: 1.0.0
description: Write a consistent, step-by-step technical tutorial. Use when creating a new cookbook, guide, or walkthrough — especially for database, search, or data engineering topics. Produces a README, supporting scripts, and a setup file following a proven structure.
---

# Tutorial Writing Guide

Write technical tutorials that are beginner-friendly, consistent in structure, and fully runnable from start to finish.

## Core Principles

- **Every tutorial should be runnable end-to-end.** A reader should be able to start from zero and have a working result by the end. No hand-waving, no "left as an exercise."
- **Label every code snippet.** Bold description above the block explaining what it does and why. Never drop a code block without context.
- **Explain concepts when they first appear.** Brief, plain-language definitions — 2-3 sentences max. Use concrete examples tied to the tutorial's dataset.
- **Show strengths AND weaknesses.** When introducing a technique, explain what it's good at and where it falls short. This builds trust and motivates the next step.
- **Connect every step to the one before it.** Each section should end with a bridge sentence that tells the reader why the next step matters.
- **Use real data.** Avoid generic placeholder data ("foo", "test123", "Document 1"). Use a real, interesting dataset with proper attribution and licensing.
- **Be explicit about tooling choices.** State what you're using (e.g., "We'll be using uv as a package manager for this") and link to alternatives so readers aren't locked in.

## File Structure

Every tutorial lives in its own folder and should contain:

```
Tutorial-Name/
├── README.md             # The full step-by-step walkthrough
├── setup.sql             # One-command setup (if DB-related): schema, data, indexes
├── requirements.txt      # Python dependencies (if applicable)
└── script.py             # Supporting script(s) with clear docstrings
├── .env.example          # Template with placeholder values for any required API keys
└── .env                  # Actual keys (gitignored, never committed)
```

At the repo root:
- `.gitignore` — must exclude `.env` and include `!.env.example`
- `README.md` — root README linking to the tutorial with a file index table
- `LICENSE` — appropriate open-source license

## README Structure

Follow this exact section order:

### 1. Title and Overview

```markdown
# Tutorial Name

One-sentence description of what this tutorial demonstrates.

## Overview

2-3 short paragraphs or bullet points explaining:
- What techniques/tools this covers
- Why you'd use them together
- What the reader will have by the end
```

### 2. Getting Started — Prerequisites

```markdown
## Getting Started

### What You'll Need

Bulleted list of every dependency:
- The primary tool/database and where to get it
- Extensions or plugins needed
- Programming language + version
- API keys and where to obtain them
- Package manager — state your choice, link alternatives
```

**Rules for prerequisites:**
- List them in order of "most likely to already have" → "most likely to need to install"
- Every item gets a bold name, a dash, and a plain-English explanation
- Link directly to download/signup pages — don't make the reader search

### 3. Getting Started — Setup Options

Offer multiple paths ordered by ease:

```markdown
### Option 1: Managed service (recommended for beginners)
### Option 2: Docker (recommended for local development)
### Option 3: Manual install
```

**Rules for setup options:**
- Each option must be self-contained — don't assume they read the other options
- Docker options should include the exact `docker run` command, connection instructions, and any relevant notes (e.g., Apple Silicon compatibility)
- Manual install should have numbered steps with sub-steps (2a, 2b, 2c) for complex operations
- Include platform-specific commands in a table or with labeled blocks (Linux, macOS, Windows)
- Every step that can fail should have a verification command and troubleshooting for common errors
- End each option with a clear "you're all set" signal

### 4. The Tutorial Steps

Number them sequentially: Step 1, Step 2, Step 3, etc.

Each step follows this pattern:

```markdown
## Step N: Action-Oriented Title

1-2 sentences explaining what this step does and why it matters.
Connect it to the previous step if applicable.

**Sub-step label** — brief description of what this specific block does:

\```language
code here
\```

Expected output or what to look for after running it.
```

**Rules for tutorial steps:**
- Titles should be action-oriented: "Create a Table", "Try Keyword Search", "Generate Embeddings" — not "Tables" or "Keyword Search"
- When introducing a new concept (embeddings, RRF, BM25), add a brief explainer paragraph before the first code block. Keep it to 2-4 sentences with a concrete example from the tutorial's dataset.
- Every code snippet gets a **bold label** above it explaining what it does
- After each code snippet, tell the reader what they should see (expected output, success message, or what to verify)
- When a step has multiple examples, label them: "Basic search", "Search with a filter", etc.
- At the end of steps that demonstrate a technique, include a **"What X is good at:"** and **"Where it falls short:"** summary. Use these to motivate the next step.
- End each step with a transition sentence bridging to the next one

### 5. Going Further

```markdown
## Going Further

The tutorial above covers the core pattern. This section collects
tips and techniques for when you're ready to go deeper.
```

**Rules:**
- Each subsection is a self-contained recipe with a descriptive heading
- Every code snippet has a 1-2 sentence explanation above it saying what it does and when you'd use it
- Order from most common needs to most specialized

### 6. Limitations

```markdown
## Current Limitations

Things to be aware of in [tool] [version]:

- **Limitation name**: Brief explanation. Workaround if one exists.
```

Keep this factual and concise. Link to workarounds shown in "Going Further" when applicable.

### 7. What's Next

```markdown
## What's Next

You've built [what they built]. Here are some directions to explore:

- **Direction** — 1-2 sentences on what to do and a link if relevant
```

**Rules:**
- 4-6 concrete next steps, ordered from easiest to most ambitious
- Each should be a distinct direction, not a variation of the same thing
- Include links to repos, tools, or docs where applicable
- At least one should point to expanding the tutorial's dataset
- At least one should point to integrating with a real application

### 8. Resources

```markdown
## Resources

- [Name](url) — one-line description
```

Link to: source repos, the dataset used, managed service options, relevant blog posts, and related demos.

## Supporting Scripts

### Python scripts (`embed.py`, `load.py`, etc.)

- Start with a docstring explaining what the script does, usage instructions, and configurable env vars
- Use `python-dotenv` to load from a `.env` file in the same directory as the script
- Use `os.getenv()` with sensible defaults for all config (host, port, user, password, database)
- Print progress messages: what it's about to do, how many items, and a "Done!" summary
- Make scripts idempotent where possible (e.g., skip rows that already have data)
- Include a clear error message if a required env var is missing, with instructions on how to fix it

### SQL setup files (`setup.sql`)

- Comment header with: what it does, dataset attribution, and usage command
- Numbered sections: 1. Extensions, 2. Table, 3. Sample data, 4. Indexes
- Use `IF NOT EXISTS` / `IF NOT EXISTS` for idempotency
- Include 8-15 rows of sample data — enough to show variety, not so many it's overwhelming

## Writing Style

- **Voice:** direct, second person ("you"), conversational but not chatty
- **Explain the "why" before the "how"** — tell the reader why a step matters before showing the code
- **Use the dataset to make concepts concrete.** Don't explain BM25 in the abstract — show how it finds the "Imposter Syndrome" episode when you search for "imposter syndrome" but misses it when you search for "feeling like a fraud."
- **Label alternatives clearly:** "We'll be using [X] for this tutorial, but feel free to use [Y] or [Z]"
- **Callouts and tips:** Use `>` blockquotes for tips, notes, and "where do I find X?" answers
- **Don't over-explain what's obvious.** If the reader just ran `CREATE TABLE`, you don't need to explain what a table is.
- **Transition between sections.** End steps with a sentence that previews what's next and why it matters.
- **Keep definitions brief.** 2-3 sentences with a concrete example, not a textbook paragraph.

## Checklist Before Shipping

- [ ] Every code snippet has a bold label and description
- [ ] Every concept is explained when first introduced
- [ ] Every step has a verification command or expected output
- [ ] All file paths, table names, and column names are consistent across README, setup.sql, and scripts
- [ ] `.env.example` exists in the tutorial folder with placeholder values
- [ ] `.gitignore` excludes `.env` but includes `.env.example`
- [ ] Dataset has proper attribution and license noted
- [ ] Root README has a file index table and getting started instructions
- [ ] Scripts load from `.env` and print helpful errors if config is missing
- [ ] setup.sql is runnable with a single `psql -f` command
- [ ] The tutorial is runnable end-to-end by someone starting from zero
