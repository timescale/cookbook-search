"""
Generate embeddings for Conduit podcast episodes using OpenAI's API
and update the episodes table in PostgreSQL.

Usage:
    1. Copy .env.example to .env and add your OpenAI API key
    2. uv pip install -r requirements.txt
    3. python embed.py

By default, connects to localhost:5432 as user 'postgres' with password 'password'.
Override with environment variables in your .env file (in the Hybrid-search/ directory):
    OPENAI_API_KEY, PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from openai import OpenAI

# Load .env from the Hybrid-search/ directory (same directory as this script)
load_dotenv(Path(__file__).resolve().parent / ".env")

# --- Configuration ---
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions

DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": os.getenv("PGPORT", "5432"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "password"),
    "dbname": os.getenv("PGDATABASE", "postgres"),
}


def get_episodes_without_embeddings(conn):
    """Fetch episodes that don't have embeddings yet."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, description FROM episodes WHERE embedding IS NULL"
        )
        return cur.fetchall()


def generate_embeddings(texts):
    """Call OpenAI to generate embeddings for a list of texts."""
    client = OpenAI()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def update_embeddings(conn, episode_ids, embeddings):
    """Write embeddings back to the database."""
    with conn.cursor() as cur:
        for episode_id, embedding in zip(episode_ids, embeddings):
            cur.execute(
                "UPDATE episodes SET embedding = %s WHERE id = %s",
                (str(embedding), episode_id),
            )
    conn.commit()


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY is not set.")
        print("Copy .env.example to .env and add your key:")
        print("  cp .env.example .env")
        raise SystemExit(1)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        episodes = get_episodes_without_embeddings(conn)

        if not episodes:
            print("All episodes already have embeddings. Nothing to do.")
            return

        print(f"Found {len(episodes)} episodes without embeddings.")

        # Combine title + description for richer embeddings
        ids = [row[0] for row in episodes]
        texts = [f"{row[1]}: {row[2]}" for row in episodes]

        print(f"Generating embeddings with {EMBEDDING_MODEL}...")
        embeddings = generate_embeddings(texts)

        print("Updating database...")
        update_embeddings(conn, ids, embeddings)

        print(f"Done! Embedded {len(embeddings)} episodes.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
