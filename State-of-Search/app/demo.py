from __future__ import annotations

import argparse

from app.prepare import doctor
from app.search import capabilities, compare, search

METHOD_CONTEXT = {
    "exact": (
        "Exact lookup",
        "Checks structured fields for the same error code or identifier you typed.",
        "A match is either present or absent, so the numeric score is not meaningful.",
    ),
    "trigram": (
        "Trigram similarity",
        "Breaks text into overlapping three-character pieces so misspellings can still match.",
        "Higher scores mean the query and result share more three-character pieces.",
    ),
    "fts": (
        "PostgreSQL full-text search",
        "Normalizes words and ranks rows containing the query's searchable terms.",
        "Higher scores mean PostgreSQL found a stronger textual match.",
    ),
    "bm25": (
        "BM25 keyword ranking",
        "Ranks text using term rarity, repeated terms, and document length.",
        "Higher scores are better within this result list; do not compare them "
        "with another method's scores.",
    ),
    "vector_exact": (
        "Exact vector search",
        "Compares the query embedding with every stored embedding to find similar meaning.",
        "Higher cosine-similarity scores mean the query and result are closer in meaning.",
    ),
    "hnsw": (
        "HNSW approximate vector search",
        "Traverses a graph of nearby embeddings instead of scoring every stored vector.",
        "Higher cosine-similarity scores are better; compare the returned rows "
        "with exact vector search to check recall.",
    ),
    "ivfflat": (
        "IVFFlat approximate vector search",
        "Searches selected clusters of similar embeddings instead of the entire corpus.",
        "Higher cosine-similarity scores are better; missing an exact-search "
        "result is the speed/recall tradeoff.",
    ),
    "diskann": (
        "StreamingDiskANN approximate vector search",
        "Uses a disk-oriented graph index to retrieve and rescore likely semantic matches.",
        "Higher cosine-similarity scores are better; compare the rows with exact "
        "vector search, not just the latency.",
    ),
    "hybrid": (
        "Hybrid search with RRF",
        "Runs BM25 keyword search and HNSW semantic search, then combines their rank positions.",
        "Higher fused scores are better, but they represent combined ranks "
        "rather than probability or similarity.",
    ),
    "elastic_bm25": (
        "Elasticsearch BM25",
        "Sends the same text query to the optional Elasticsearch copy of the corpus.",
        "Higher scores are better within this Elasticsearch result list; "
        "cross-system scores are not directly comparable.",
    ),
    "elastic_knn": (
        "Elasticsearch approximate vector search",
        "Uses Elasticsearch k-nearest-neighbor retrieval over the same stored embeddings.",
        "Higher scores are better within this result list; compare returned rows "
        "across systems rather than raw scores.",
    ),
    "elastic_hybrid": (
        "Elasticsearch hybrid search",
        "Combines Elasticsearch BM25 and vector candidates with Reciprocal Rank Fusion (RRF).",
        "Higher fused scores are better, but they are ranking signals rather "
        "than confidence percentages.",
    ),
}

TOUR = (
    (
        "Exact identifier",
        "Find a record when the query is a known error code, not a sentence.",
        "PG_53300",
        ["exact"],
        "The database should return only rows whose structured identifier "
        "exactly matches PG_53300.",
    ),
    (
        "Typo tolerance",
        "See how character similarity helps when a person misspells important words.",
        "conection pool exaustion",
        ["trigram", "fts"],
        "Trigram search can recover the intended topic; full-text search may "
        "struggle because the misspelled words are different tokens.",
    ),
    (
        "Lexical relevance",
        "Compare two ways of ranking documents that contain the words in the query.",
        "too many clients already",
        ["fts", "bm25", "elastic_bm25"],
        "Look at which incident family reaches the top, not whether the methods "
        "produce the same numeric score.",
    ),
    (
        "Semantic paraphrase",
        "Find related meaning even though the query does not repeat the incident's exact wording.",
        "why does checkout keep losing database capacity",
        ["vector_exact", "hnsw", "ivfflat", "diskann"],
        "Treat exact vector search as the reference, then check whether each "
        "faster approximate index returns similar top rows.",
    ),
    (
        "Hybrid intent",
        "Combine exact technical terms with the broader meaning of the question.",
        "payments deploy saturated postgres max_connections",
        ["hybrid", "elastic_hybrid"],
        "Strong results should benefit from both literal clues such as "
        "max_connections and semantically related incident text.",
    ),
)


def print_result(result) -> None:
    label, explanation, score_guide = METHOD_CONTEXT.get(
        result.method,
        (result.method, "Runs the selected retrieval method.", "Higher scores usually rank first."),
    )
    print(f"\nMethod: {label} [{result.method}]")
    print(f"  What is running: {explanation}")
    print(f"  Client-observed retrieval time: {result.elapsed_ms:.1f} ms")
    print(f"  How to read the score: {score_guide}")
    if result.note:
        print(f"  Note: {result.note}")
    print(f"  Results returned: {len(result.rows)}")
    if not result.rows:
        print("  No matching rows were returned.")
        return
    for index, row in enumerate(result.rows, 1):
        score = row.get("score")
        score_text = (
            f" | score={float(score):.4f}"
            if score is not None and result.method != "exact"
            else ""
        )
        family = row.get("incident_family") or "not labeled"
        source = row.get("source_kind") or "unknown source"
        service = row.get("service") or "no service"
        title = (row.get("title") or "Untitled")[:68]
        print(f"  {index:>2}. {title}")
        print(
            f"      source={source} | service={service} | "
            f"incident family={family}{score_text}"
        )


def run_tour() -> None:
    available = capabilities()
    print(
        "This tour runs the same incident corpus through several search strategies.\n"
        "Each step changes the kind of question so you can see why no single search\n"
        "method is best for every query. Timings cover retrieval and client overhead;\n"
        "query-embedding creation happens before the displayed retrieval timer."
    )
    for step, (title, goal, query, methods, watch_for) in enumerate(TOUR, 1):
        runnable = [method for method in methods if available.get(method)]
        unavailable = [method for method in methods if not available.get(method)]
        print(f"\n{'=' * 78}")
        print(f"STEP {step} OF {len(TOUR)}: {title}")
        print(f"Goal: {goal}")
        print(f"Query being searched: {query!r}")
        print(f"Methods being compared: {', '.join(runnable) or 'none'}")
        if unavailable:
            print(
                "Skipped because they are not available in this environment: "
                + ", ".join(unavailable)
            )
        print(f"What to look for: {watch_for}")
        if not runnable:
            print(
                "Nothing ran in this step. Run `python -m app.prepare doctor` to see "
                "which extension, index, or service still needs to be prepared."
            )
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
        print(f"Searching for {args.query!r} with one method: {args.method}")
        print_result(search(args.method, args.query, args.limit))
    elif args.command == "compare":
        print(f"Searching for {args.query!r}")
        print(f"Methods being compared: {', '.join(args.methods)}")
        print(
            "Compare result order and content; scores from different methods "
            "use different scales."
        )
        for result in compare(args.query, args.methods, args.limit):
            print_result(result)


if __name__ == "__main__":
    main()
