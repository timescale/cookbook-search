from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from elasticsearch import Elasticsearch, helpers
from openai import OpenAI

from app.db import connect, run_sql_file

DATA_DIR = Path("/workspace/data")
GENERATOR = Path("/incident-source/generate_data.py")
SEED_DIR = Path("/incident-source/seed")
MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
PROFILES = {
    "sample": {"events": 5_000, "deployments": 200, "incidents": 20, "routine_issues": 50},
    "demo": {"events": 50_000, "deployments": 1_000, "incidents": 20, "routine_issues": 150},
    "benchmark": {"events": 250_000, "deployments": 4_900, "incidents": 62, "routine_issues": 350},
}


def generate() -> None:
    profile_name = os.getenv("DATASET_PROFILE", "sample")
    if profile_name not in PROFILES:
        raise SystemExit(f"Unknown DATASET_PROFILE={profile_name!r}; choose {', '.join(PROFILES)}")
    profile = PROFILES[profile_name]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(GENERATOR),
        "--seed-dir",
        str(SEED_DIR),
        "--out",
        str(DATA_DIR),
        "--events",
        str(profile["events"]),
        "--deployments",
        str(profile["deployments"]),
        "--incidents",
        str(profile["incidents"]),
        "--routine-issues",
        str(profile["routine_issues"]),
    ]
    print(f"Generating deterministic {profile_name} corpus in {DATA_DIR}", flush=True)
    subprocess.run(command, check=True)


def setup() -> None:
    required = ("timescaledb", "vector", "pg_trgm")
    optional = ("pg_textsearch", "vectorscale")
    with connect(dict_rows=False) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            for extension in required + optional:
                try:
                    suffix = " CASCADE" if extension == "vectorscale" else ""
                    cur.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}{suffix}")
                    print(f"extension ready: {extension}")
                except psycopg.Error as exc:
                    if extension in required:
                        raise RuntimeError(
                            f"Required extension {extension} is unavailable: {exc.diag.message_primary}"
                        ) from exc
                    print(f"optional extension unavailable: {extension} ({exc.diag.message_primary})")
        conn.autocommit = False
        run_sql_file(conn, "schema.sql")


def _copy_csv(conn, table: str, columns: tuple[str, ...], filename: str) -> None:
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Run the generate step first; missing {path}")
    column_sql = ", ".join(columns)
    with conn.cursor() as cur, cur.copy(
        f"COPY {table} ({column_sql}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    ) as copy:
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                copy.write(chunk)


def load() -> None:
    with connect(dict_rows=False) as conn:
        run_sql_file(conn, "reset.sql")
        _copy_csv(
            conn,
            "events",
            (
                "occurred_at", "service", "environment", "severity", "event_type",
                "region", "error_code", "incident_id", "content", "metadata",
            ),
            "events.csv",
        )
        _copy_csv(
            conn,
            "deployments",
            (
                "deploy_id", "deployed_at", "service", "environment", "version",
                "previous_version", "git_sha", "deployer", "strategy", "status",
                "duration_seconds", "change_summary", "metadata",
            ),
            "deployments.csv",
        )
        _copy_csv(
            conn,
            "source_documents",
            (
                "doc_id", "doc_type", "title", "section", "service",
                "incident_family", "incident_id", "published_at", "content",
            ),
            "documents.csv",
        )
        _copy_csv(
            conn,
            "labeled_questions",
            (
                "question_id", "question", "query_kind", "expected_family",
                "expected_incident_ids", "expected_services", "notes",
            ),
            "labeled_questions.csv",
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO search_items (
                  source_kind, source_id, title, content, service, incident_id,
                  incident_family, occurred_at, environment, region, severity,
                  error_code, metadata
                )
                SELECT 'event', id::text, service || ' ' || event_type, content,
                       service, incident_id, metadata->>'incident_family', occurred_at,
                       environment, region, severity, error_code, metadata
                FROM events
                ORDER BY id
                """
            )
            cur.execute(
                """
                INSERT INTO search_items (
                  source_kind, source_id, title, content, service, incident_id,
                  incident_family, occurred_at, metadata
                )
                SELECT 'document', doc_id, title || ': ' || section, content,
                       service, incident_id, incident_family, published_at,
                       jsonb_build_object('doc_type', doc_type, 'section', section)
                FROM source_documents
                ORDER BY doc_id
                """
            )
        conn.commit()
        run_sql_file(conn, "indexes.sql")
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM search_items")
            total = cur.fetchone()[0]
        print(f"Loaded {total:,} searchable rows")


def embed() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY in .env before running the embedding step")
    batch_size = int(os.getenv("EMBED_BATCH_SIZE", "100"))
    client = OpenAI()
    processed = 0
    with connect(dict_rows=False) as conn:
        while True:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title || E'\n' || content
                    FROM search_items
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
                input=[text for _, text in rows],
                encoding_format="float",
            )
            vectors = {item.index: item.embedding for item in response.data}
            if len(vectors) != len(rows):
                raise RuntimeError(f"Expected {len(rows)} embeddings, received {len(vectors)}")
            updates = [
                (json.dumps(vectors[index]), MODEL, row_id)
                for index, (row_id, _) in enumerate(rows)
            ]
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    UPDATE search_items
                    SET embedding = %s::vector,
                        embedding_model = %s
                    WHERE id = %s
                    """,
                    updates,
                )
            conn.commit()
            processed += len(rows)
            print(f"Embedded {processed:,} rows", flush=True)

        with conn.cursor() as cur:
            for table in ("vectors_hnsw", "vectors_ivfflat", "vectors_diskann"):
                cur.execute(f"TRUNCATE {table}")
                cur.execute(
                    f"INSERT INTO {table} (item_id, embedding) "
                    "SELECT id, embedding FROM search_items WHERE embedding IS NOT NULL"
                )
        conn.commit()
    print(f"Embeddings complete with {MODEL}")


def build_indexes() -> None:
    with connect(dict_rows=False) as conn:
        run_sql_file(conn, "vector-indexes.sql")
    print("Vector indexes built")


def load_elasticsearch() -> None:
    url = os.getenv("ELASTIC_URL", "http://elasticsearch:9200")
    es = Elasticsearch(url, request_timeout=60)
    if not es.ping():
        raise SystemExit("Elasticsearch is not reachable; start the elastic Compose profile")
    index = "incident-search"
    if es.indices.exists(index=index):
        es.indices.delete(index=index)
    es.indices.create(
        index=index,
        mappings={
            "properties": {
                "title": {"type": "text"},
                "content": {"type": "text"},
                "source_kind": {"type": "keyword"},
                "service": {"type": "keyword"},
                "incident_id": {"type": "keyword"},
                "incident_family": {"type": "keyword"},
                "region": {"type": "keyword"},
                "severity": {"type": "keyword"},
                "error_code": {"type": "keyword"},
                "occurred_at": {"type": "date"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 1536,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        },
    )
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source_kind, title, content, service, incident_id,
                   incident_family, region, severity, error_code, occurred_at,
                   embedding::text
            FROM search_items
            WHERE embedding IS NOT NULL
            ORDER BY id
            """
        )

        def actions():
            for row in cur:
                vector = json.loads(row.pop("embedding"))
                if row["occurred_at"] is not None:
                    row["occurred_at"] = row["occurred_at"].isoformat()
                yield {"_index": index, "_id": str(row.pop("id")), "_source": {**row, "embedding": vector}}

        success, errors = helpers.bulk(es, actions(), chunk_size=250, raise_on_error=False)
    es.indices.refresh(index=index)
    print(f"Indexed {success:,} Elasticsearch documents; errors={len(errors)}")


def doctor() -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT version() AS version")
        print(cur.fetchone()["version"])
        cur.execute("SELECT extname, extversion FROM pg_extension ORDER BY extname")
        extensions = {row["extname"]: row["extversion"] for row in cur.fetchall()}
        cur.execute("SELECT amname FROM pg_am ORDER BY amname")
        methods = {row["amname"] for row in cur.fetchall()}
        cur.execute("SELECT count(*) AS rows, count(embedding) AS embedded FROM search_items")
        counts = cur.fetchone()
        cur.execute(
            """
            SELECT
              (SELECT count(*) FROM vectors_hnsw) AS hnsw,
              (SELECT count(*) FROM vectors_ivfflat) AS ivfflat,
              (SELECT count(*) FROM vectors_diskann) AS diskann
            """
        )
        vector_counts = cur.fetchone()
    print("Extensions:", ", ".join(f"{k}={v}" for k, v in extensions.items()))
    print("Search access methods:", ", ".join(sorted(methods & {"bm25", "hnsw", "ivfflat", "diskann"})))
    print(f"Corpus: {counts['rows']:,} rows; {counts['embedded']:,} embedded")
    print(
        "Vector tables: "
        f"hnsw={vector_counts['hnsw']:,}, "
        f"ivfflat={vector_counts['ivfflat']:,}, "
        f"diskann={vector_counts['diskann']:,}"
    )
    if counts["rows"] and not counts["embedded"]:
        print(
            "Next step: run `docker compose run --rm app python -m app.prepare embed`, "
            "then run the index command."
        )
    elif counts["embedded"] != counts["rows"]:
        print("Warning: document embedding preparation is incomplete; rerun the embed command.")
    elif any(vector_counts[name] != counts["embedded"] for name in vector_counts):
        print("Warning: vector tables are incomplete; rerun the embed command before indexing.")


def all_steps(include_elastic: bool = False) -> None:
    generate()
    setup()
    load()
    embed()
    build_indexes()
    doctor()
    if include_elastic:
        load_elasticsearch()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the State of Search demo")
    parser.add_argument(
        "command",
        choices=("generate", "setup", "load", "embed", "index", "elastic", "doctor", "all"),
    )
    parser.add_argument("--with-elastic", action="store_true")
    args = parser.parse_args()
    actions = {
        "generate": generate,
        "setup": setup,
        "load": load,
        "embed": embed,
        "index": build_indexes,
        "elastic": load_elasticsearch,
        "doctor": doctor,
    }
    if args.command == "all":
        all_steps(include_elastic=args.with_elastic)
    else:
        actions[args.command]()


if __name__ == "__main__":
    main()
