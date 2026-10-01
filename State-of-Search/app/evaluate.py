from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from app.db import connect
from app.search import capabilities, search

DEFAULT_METHODS = ("fts", "bm25", "vector_exact", "hnsw", "ivfflat", "diskann", "hybrid")


def evaluate(methods: list[str], *, question_limit: int | None, k: int) -> list[dict]:
    available = capabilities()
    methods = [method for method in methods if available.get(method)]
    if not methods:
        raise SystemExit("None of the requested methods are available")
    sql = """
        SELECT question_id, question, query_kind, expected_family
        FROM labeled_questions
        WHERE coalesce(expected_family, '') <> ''
        ORDER BY question_id
    """
    params: tuple = ()
    if question_limit:
        sql += " LIMIT %s"
        params = (question_limit,)
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        questions = cur.fetchall()

    output = []
    for question in questions:
        for method in methods:
            result = search(method, question["question"], k)
            families = {row.get("incident_family") for row in result.rows}
            hit = question["expected_family"] in families
            output.append(
                {
                    "question_id": question["question_id"],
                    "query_kind": question["query_kind"],
                    "method": method,
                    "hit_at_k": int(hit),
                    "latency_ms": round(result.elapsed_ms, 3),
                }
            )
            print(
                f"q={question['question_id']:>3} method={method:<12} "
                f"hit@{k}={int(hit)} latency={result.elapsed_ms:.1f}ms",
                flush=True,
            )
    return output


def summarize(rows: list[dict]) -> None:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["method"], row["query_kind"])].append(row)
    print("\nMethod       Query kind   Recall     Mean latency")
    print("-" * 58)
    for (method, query_kind), values in sorted(groups.items()):
        recall = sum(value["hit_at_k"] for value in values) / len(values)
        latency = sum(value["latency_ms"] for value in values) / len(values)
        print(f"{method:<12} {query_kind:<12} {recall:>6.1%} {latency:>14.1f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval against labeled incident families")
    parser.add_argument("--methods", nargs="+", default=list(DEFAULT_METHODS))
    parser.add_argument("--questions", type=int, default=None, help="limit the labeled question count")
    parser.add_argument("-k", type=int, default=10)
    parser.add_argument("--output", default="/workspace/results/evaluation.csv")
    args = parser.parse_args()
    rows = evaluate(args.methods, question_limit=args.questions, k=args.k)
    summarize(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {output}")


if __name__ == "__main__":
    main()
