#!/usr/bin/env python3
"""Create OpenAI embeddings for incident events stored in Tiger Cloud.

Run after load.py and before indexes.sql. Existing embeddings are skipped, so
the script is safe to rerun after an interruption.

Usage:
    uv run python embed.py
    uv run python embed.py --limit 100

Environment variables:
    DATABASE_URL             Tiger Cloud connection string (required)
    OPENAI_API_KEY           OpenAI API key (required)
    OPENAI_EMBEDDING_MODEL   Defaults to text-embedding-3-small
"""

from __future__ import annotations

import argparse
import os

import psycopg
from openai import OpenAI

from load import HERE, connection_url


MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DIMENSIONS = 1536


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--limit", type=int, default=None, help="maximum rows to embed")
    args = parser.parse_args()
    if args.batch_size < 1 or (args.limit is not None and args.limit < 1):
        parser.error("--batch-size and --limit must be positive")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error(f"Set OPENAI_API_KEY in {HERE / '.env'}")

    client = OpenAI()
    embedded = 0
    with psycopg.connect(connection_url()) as conn:
        while args.limit is None or embedded < args.limit:
            batch_size = min(args.batch_size, args.limit - embedded) if args.limit else args.batch_size
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, content
                    FROM incident_events
                    WHERE embedding IS NULL
                    ORDER BY id
                    LIMIT %s
                    """,
                    (batch_size,),
                )
                rows = cur.fetchall()
            if not rows:
                break

            response = client.embeddings.create(
                model=MODEL,
                input=[row[1] for row in rows],
                dimensions=DIMENSIONS,
            )
            vectors = sorted(response.data, key=lambda item: item.index)
            if len(vectors) != len(rows):
                raise RuntimeError(f"Expected {len(rows)} embeddings, received {len(vectors)}")
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE incident_events SET embedding = %s::vec32 WHERE id = %s",
                    [(str(item.embedding), row[0]) for row, item in zip(rows, vectors)],
                )
            conn.commit()
            embedded += len(rows)
            print(f"Embedded {embedded:,} events with {MODEL}...", flush=True)

    if embedded:
        print(f"Done! Added {embedded:,} embeddings.")
    else:
        print("All events already have embeddings. Nothing to do.")


if __name__ == "__main__":
    main()
