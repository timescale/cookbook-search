from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from elasticsearch import Elasticsearch
from openai import OpenAI

from app.db import connect

MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
ELASTIC_URL = os.getenv("ELASTIC_URL", "http://elasticsearch:9200")


@dataclass
class SearchResult:
    method: str
    elapsed_ms: float
    rows: list[dict[str, Any]]
    note: str = ""


def postgres_capabilities() -> dict[str, bool]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension")
        extensions = {row["extname"] for row in cur.fetchall()}
        cur.execute("SELECT amname FROM pg_am")
        access_methods = {row["amname"] for row in cur.fetchall()}
    return {
        "exact": True,
        "trigram": "pg_trgm" in extensions,
        "fts": True,
        "bm25": "bm25" in access_methods,
        "vector_exact": "vector" in extensions,
        "hnsw": "hnsw" in access_methods,
        "ivfflat": "ivfflat" in access_methods,
        "diskann": "diskann" in access_methods,
        "hybrid": "bm25" in access_methods and "hnsw" in access_methods,
    }


def capabilities() -> dict[str, bool]:
    result = postgres_capabilities()
    elastic = False
    try:
        es = Elasticsearch(ELASTIC_URL, request_timeout=2)
        elastic = bool(
            es.ping()
            and es.indices.exists(index="incident-search")
            and es.count(index="incident-search")["count"]
        )
    except Exception:
        pass
    result.update({
        "elastic_bm25": elastic,
        "elastic_knn": elastic,
        "elastic_hybrid": elastic,
    })
    return result


def query_embedding(query: str) -> str:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT embedding::text FROM query_embeddings WHERE query = %s AND model = %s",
            (query, MODEL),
        )
        row = cur.fetchone()
        if row:
            return row["embedding"]
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY to run semantic search")
    vector = OpenAI().embeddings.create(
        model=MODEL, input=query, encoding_format="float"
    ).data[0].embedding
    encoded = json.dumps(vector)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO query_embeddings (query, embedding, model)
            VALUES (%s, %s::vector, %s)
            ON CONFLICT (query) DO UPDATE SET
              embedding = EXCLUDED.embedding,
              model = EXCLUDED.model,
              embedded_at = now()
            """,
            (query, encoded, MODEL),
        )
        conn.commit()
    return encoded


def _rows(cur) -> list[dict[str, Any]]:
    return [dict(row) for row in cur.fetchall()]


def _vector_readiness_note(method: str) -> str:
    table = {
        "hnsw": "vectors_hnsw",
        "ivfflat": "vectors_ivfflat",
        "diskann": "vectors_diskann",
        "hybrid": "vectors_hnsw",
    }.get(method)
    with connect() as conn, conn.cursor() as cur:
        if table:
            cur.execute(f"SELECT count(*) AS ready FROM {table}")
        else:
            cur.execute(
                "SELECT count(*) AS ready FROM search_items WHERE embedding IS NOT NULL"
            )
        ready = cur.fetchone()["ready"]
    if ready:
        return ""
    return (
        "No document embeddings are prepared for this method. Run "
        "`docker compose run --rm app python -m app.prepare embed`, then "
        "`docker compose run --rm app python -m app.prepare index`. "
        "Running the load step again resets stored embeddings."
    )


def postgres_search(method: str, query: str, limit: int = 10) -> SearchResult:
    available = postgres_capabilities()
    if not available.get(method, False):
        return SearchResult(method, 0, [], f"{method} is unavailable in this image")

    vector = None
    if method in {"vector_exact", "hnsw", "ivfflat", "diskann", "hybrid"}:
        readiness_note = _vector_readiness_note(method)
        if readiness_note:
            return SearchResult(method, 0, [], readiness_note)
        vector = query_embedding(query)

    started = time.perf_counter()
    with connect() as conn, conn.cursor() as cur:
        if method == "exact":
            cur.execute(
                """
                SELECT id, source_kind, title, content, service, incident_id,
                       incident_family, error_code, 0::float AS score
                FROM search_items
                WHERE error_code = %s OR source_id = %s OR incident_id = %s
                ORDER BY occurred_at DESC NULLS LAST LIMIT %s
                """,
                (query, query, query, limit),
            )
        elif method == "trigram":
            cur.execute(
                """
                SELECT id, source_kind, title, content, service, incident_id,
                       incident_family, error_code,
                       word_similarity(%s, title || ' ' || content) AS score
                FROM search_items
                WHERE %s <%% (title || ' ' || content)
                ORDER BY score DESC LIMIT %s
                """,
                (query, query, limit),
            )
        elif method == "fts":
            cur.execute(
                """
                SELECT id, source_kind, title, content, service, incident_id,
                       incident_family, error_code,
                       ts_rank_cd(content_tsv, websearch_to_tsquery('english', %s)) AS score
                FROM search_items
                WHERE content_tsv @@ websearch_to_tsquery('english', %s)
                ORDER BY score DESC, occurred_at DESC NULLS LAST, id LIMIT %s
                """,
                (query, query, limit),
            )
        elif method == "bm25":
            cur.execute(
                """
                SELECT id, source_kind, title, content, service, incident_id,
                       incident_family, error_code,
                       -(content <@> to_bm25query(%s, 'search_items_bm25_idx')) AS score
                FROM search_items
                ORDER BY content <@> to_bm25query(%s, 'search_items_bm25_idx')
                LIMIT %s
                """,
                (query, query, limit),
            )
        elif method == "vector_exact":
            cur.execute("SET LOCAL enable_indexscan = off")
            cur.execute("SET LOCAL enable_bitmapscan = off")
            cur.execute(
                """
                SELECT id, source_kind, title, content, service, incident_id,
                       incident_family, error_code, 1 - (embedding <=> %s::vector) AS score
                FROM search_items WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector LIMIT %s
                """,
                (vector, vector, limit),
            )
        elif method in {"hnsw", "ivfflat", "diskann"}:
            table = f"vectors_{method}"
            cur.execute("SET LOCAL enable_seqscan = off")
            if method == "hnsw":
                cur.execute("SET LOCAL hnsw.ef_search = 100")
            elif method == "ivfflat":
                cur.execute("SET LOCAL ivfflat.probes = 10")
            elif method == "diskann":
                cur.execute("SET LOCAL diskann.query_rescore = 100")
            cur.execute(
                f"""
                SELECT s.id, s.source_kind, s.title, s.content, s.service,
                       s.incident_id, s.incident_family, s.error_code,
                       1 - (v.embedding <=> %s::vector) AS score
                FROM {table} AS v JOIN search_items AS s ON s.id = v.item_id
                ORDER BY v.embedding <=> %s::vector LIMIT %s
                """,
                (vector, vector, limit),
            )
        elif method == "hybrid":
            cur.execute("SET LOCAL enable_seqscan = off")
            cur.execute("SET LOCAL hnsw.ef_search = 100")
            cur.execute(
                """
                WITH keyword AS (
                  SELECT id, row_number() OVER (
                    ORDER BY content <@> to_bm25query(%s, 'search_items_bm25_idx')
                  ) AS rank
                  FROM search_items
                  ORDER BY content <@> to_bm25query(%s, 'search_items_bm25_idx')
                  LIMIT 40
                ), semantic AS (
                  SELECT s.id, row_number() OVER (
                    ORDER BY v.embedding <=> %s::vector
                  ) AS rank
                  FROM vectors_hnsw AS v
                  JOIN search_items AS s ON s.id = v.item_id
                  ORDER BY v.embedding <=> %s::vector LIMIT 40
                ), fused AS (
                  SELECT id, sum(1.0 / (60 + rank)) AS score
                  FROM (
                    SELECT * FROM keyword UNION ALL SELECT * FROM semantic
                  ) candidates GROUP BY id
                )
                SELECT s.id, s.source_kind, s.title, s.content, s.service,
                       s.incident_id, s.incident_family, s.error_code, f.score
                FROM fused AS f JOIN search_items AS s USING (id)
                ORDER BY f.score DESC LIMIT %s
                """,
                (query, query, vector, vector, limit),
            )
        else:
            raise ValueError(f"Unknown PostgreSQL method: {method}")
        rows = _rows(cur)
    elapsed = (time.perf_counter() - started) * 1000
    return SearchResult(method, elapsed, rows)


def elastic_search(method: str, query: str, limit: int = 10) -> SearchResult:
    available = capabilities()
    if not available.get(method, False):
        return SearchResult(method, 0, [], "Elasticsearch is not running or has no reachable node")
    es = Elasticsearch(ELASTIC_URL, request_timeout=30)
    vector = None
    if method in {"elastic_knn", "elastic_hybrid"}:
        vector_text = query_embedding(query)
        vector = json.loads(vector_text)
    started = time.perf_counter()
    if method == "elastic_bm25":
        response = es.search(
            index="incident-search",
            size=limit,
            query={"multi_match": {"query": query, "fields": ["title^2", "content"]}},
        )
    elif method == "elastic_knn":
        response = es.search(
            index="incident-search",
            size=limit,
            knn={"field": "embedding", "query_vector": vector, "k": limit, "num_candidates": max(100, limit * 10)},
        )
    elif method == "elastic_hybrid":
        rank_window = 40
        rank_constant = 60
        keyword_response = es.search(
            index="incident-search",
            size=rank_window,
            query={"multi_match": {"query": query, "fields": ["title^2", "content"]}},
        )
        semantic_response = es.search(
            index="incident-search",
            size=rank_window,
            knn={
                "field": "embedding",
                "query_vector": vector,
                "k": rank_window,
                "num_candidates": 100,
            },
        )
        fused: dict[str, float] = {}
        sources: dict[str, dict[str, Any]] = {}
        for candidate_response in (keyword_response, semantic_response):
            for rank, hit in enumerate(candidate_response["hits"]["hits"], 1):
                hit_id = hit["_id"]
                fused[hit_id] = fused.get(hit_id, 0.0) + 1.0 / (rank_constant + rank)
                sources[hit_id] = hit["_source"]
        rows = []
        for hit_id, score in sorted(fused.items(), key=lambda item: (-item[1], item[0]))[:limit]:
            source = dict(sources[hit_id])
            source["id"] = hit_id
            source["score"] = score
            source.pop("embedding", None)
            rows.append(source)
        elapsed = (time.perf_counter() - started) * 1000
        return SearchResult(method, elapsed, rows)
    else:
        raise ValueError(f"Unknown Elasticsearch method: {method}")
    rows = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        source["id"] = hit["_id"]
        source["score"] = hit.get("_score")
        source.pop("embedding", None)
        rows.append(source)
    elapsed = (time.perf_counter() - started) * 1000
    return SearchResult(method, elapsed, rows)


def search(method: str, query: str, limit: int = 10) -> SearchResult:
    if method.startswith("elastic_"):
        return elastic_search(method, query, limit)
    return postgres_search(method, query, limit)


def compare(query: str, methods: list[str], limit: int = 10) -> list[SearchResult]:
    return [search(method, query, limit) for method in methods]
