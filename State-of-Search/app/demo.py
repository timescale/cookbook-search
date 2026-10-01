from __future__ import annotations

import argparse

from app.prepare import doctor
from app.search import capabilities, compare, search

TOUR = (
    ("Exact identifier", "PG_53300", ["exact"]),
    ("Typo tolerance", "conection pool exaustion", ["trigram", "fts"]),
    ("Lexical relevance", "too many clients already", ["fts", "bm25", "elastic_bm25"]),
    ("Semantic paraphrase", "why does checkout keep losing database capacity", ["vector_exact", "hnsw", "ivfflat", "diskann"]),
    ("Hybrid intent", "payments deploy saturated postgres max_connections", ["hybrid", "elastic_hybrid"]),
)


def print_result(result) -> None:
    print(f"\n{result.method}: {result.elapsed_ms:.1f} ms")
    if result.note:
        print(f"  note: {result.note}")
    for index, row in enumerate(result.rows, 1):
        score = row.get("score")
        score_text = f" score={float(score):.4f}" if score is not None else ""
        family = row.get("incident_family") or "—"
        print(f"  {index:>2}. {row.get('title', '')[:68]} family={family}{score_text}")


def run_tour() -> None:
    available = capabilities()
    for title, query, methods in TOUR:
        runnable = [method for method in methods if available.get(method)]
        print(f"\n{'=' * 78}\n{title}\nQuery: {query}")
        if not runnable:
            print("No methods for this scene are available; run the preparation steps and doctor.")
            continue
        for result in compare(query, runnable, limit=5):
            print_result(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the State of Search terminal demo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("tour")
    search_parser = sub.add_parser("search")
    search_parser.add_argument("method")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("query")
    compare_parser.add_argument("methods", nargs="+")
    compare_parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.command == "doctor":
        doctor()
    elif args.command == "tour":
        run_tour()
    elif args.command == "search":
        print_result(search(args.method, args.query, args.limit))
    elif args.command == "compare":
        for result in compare(args.query, args.methods, args.limit):
            print_result(result)


if __name__ == "__main__":
    main()
