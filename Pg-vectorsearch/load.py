#!/usr/bin/env python3
"""Generate and load the synthetic incident dataset into Tiger Cloud.

Usage:
    cp .env.example .env
    uv run python load.py
    uv run python load.py --rows 5000 --truncate

Environment variables:
    DATABASE_URL  Tiger Cloud PostgreSQL connection string (required)
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from generate_data import generate_events


HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")


def connection_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL in Pg-vectorsearch/.env")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--truncate", action="store_true", help="replace existing events")
    args = parser.parse_args()
    events = generate_events(args.rows, args.seed)

    with psycopg.connect(connection_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('incident_events')")
            if cur.fetchone()[0] is None:
                raise SystemExit("Table incident_events does not exist. Run setup.sql first.")
            cur.execute("SELECT count(*) FROM incident_events")
            existing = cur.fetchone()[0]
            if existing and not args.truncate:
                print(f"incident_events already contains {existing:,} rows; nothing to do")
                print("To replace them, run: uv run python load.py --truncate")
                return
            if args.truncate:
                cur.execute("TRUNCATE incident_events RESTART IDENTITY")
                print("Truncated incident_events.")

            print(f"Loading {len(events):,} generated events into Tiger Cloud...")
            cur.executemany(
                """
                INSERT INTO incident_events
                  (occurred_at, service, severity, incident_id,
                   incident_family, content, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                [
                    (
                        row["occurred_at"],
                        row["service"],
                        row["severity"],
                        row["incident_id"],
                        row["incident_family"],
                        row["content"],
                        row["metadata"],
                    )
                    for row in events
                ],
            )
        conn.commit()
    print(f"Done! Loaded {len(events):,} events.")


if __name__ == "__main__":
    main()
