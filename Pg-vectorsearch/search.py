#!/usr/bin/env python3
"""Search incident events in Tiger Cloud with a pg_vectorsearch PRISM index.

Usage:
    uv run python search.py "why are checkout database connections exhausted?"
    uv run python search.py "certificate renewal failed" --service edge-proxy
    uv run python search.py "worker memory crash" --nprobe 40 --explain

Environment variables:
    DATABASE_URL             Tiger Cloud connection string (required)
    OPENAI_API_KEY           OpenAI API key (required)
    OPENAI_EMBEDDING_MODEL   Defaults to text-embedding-3-small
"""

from __future__ import annotations

import argparse
import os
import re

from openai import OpenAI

from load import HERE, connect_db


MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
DIMENSIONS = 1536
SEARCH_SQL = """
SELECT id, occurred_at, service, incident_id, incident_family, content,
       1 - (embedding <=> %s::vec32) AS cosine_similarity
FROM incident_events
WHERE embedding IS NOT NULL
  AND (%s::text IS NULL OR service = %s)
ORDER BY embedding <=> %s::vec32
LIMIT %s
"""
VECTOR_LITERAL_RE = re.compile(r"'\[[^]]+\]'::vec32")


def display_plan_line(line: str) -> str:
    """Hide the generated vector while keeping the useful EXPLAIN details."""
    return VECTOR_LITERAL_RE.sub("<query-vector>::vec32", line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--service", default=None)
    parser.add_argument("--nprobe", type=int, default=None)
    parser.add_argument("--explain", action="store_true")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.nprobe is not None and args.nprobe < 0:
        parser.error("--nprobe cannot be negative")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error(f"Set OPENAI_API_KEY in {HERE / '.env'}")

    with connect_db() as conn:
        print(f"Embedding query with {MODEL}...", flush=True)
        response = OpenAI().embeddings.create(
            model=MODEL,
            input=args.query,
            dimensions=DIMENSIONS,
        )
        query_vector = str(response.data[0].embedding)
        params = (query_vector, args.service, args.service, query_vector, args.limit)

        with conn.cursor() as cur:
            if args.nprobe is not None:
                cur.execute("SELECT set_config('prism.nprobe', %s, true)", (str(args.nprobe),))
            if args.explain:
                cur.execute("EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) " + SEARCH_SQL, params)
                print("\nQuery plan:")
                for line, in cur.fetchall():
                    print(display_plan_line(line))
            cur.execute(SEARCH_SQL, params)
            rows = cur.fetchall()

    print(f"\nTop {len(rows)} matches for: {args.query!r}\n")
    for rank, row in enumerate(rows, start=1):
        event_id, occurred_at, service, incident_id, family, content, score = row
        print(f"{rank:>2}. similarity={score:.4f}  service={service}  incident={incident_id or '-'}")
        print(f"    family={family or '-'}  time={occurred_at.isoformat()}")
        print(f"    {content}\n")


if __name__ == "__main__":
    main()
