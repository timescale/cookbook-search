from __future__ import annotations

import streamlit as st

from app.search import capabilities, compare

st.set_page_config(page_title="State of Search", page_icon="🔎", layout="wide")
st.title("State of Search")
st.caption("One incident corpus. Many retrieval strategies. No universal winner.")

available = capabilities()
all_methods = [
    "exact", "trigram", "fts", "bm25", "vector_exact", "hnsw",
    "ivfflat", "diskann", "hybrid", "elastic_bm25",
    "elastic_knn", "elastic_hybrid",
]
ready = [method for method in all_methods if available.get(method)]
missing = [method for method in all_methods if not available.get(method)]

with st.sidebar:
    st.subheader("Environment")
    st.write("Available: " + ", ".join(ready))
    if missing:
        st.write("Unavailable: " + ", ".join(missing))
    limit = st.slider("Results per method", 3, 20, 5)

query = st.text_input(
    "Query",
    value="payments deploy saturated postgres max_connections",
)
methods = st.multiselect(
    "Methods",
    options=ready,
    default=[method for method in ("fts", "bm25", "hnsw", "hybrid") if method in ready],
)

if st.button("Compare", type="primary", disabled=not query or not methods):
    results = compare(query, methods, limit)
    columns = st.columns(len(results))
    for column, result in zip(columns, results):
        with column:
            st.subheader(result.method)
            st.metric("Client-observed latency", f"{result.elapsed_ms:.1f} ms")
            if result.note:
                st.warning(result.note)
            for index, row in enumerate(result.rows, 1):
                score = row.get("score")
                score_text = f" · {float(score):.4f}" if score is not None else ""
                with st.container(border=True):
                    st.markdown(f"**{index}. {row.get('title', 'Untitled')}**{score_text}")
                    st.caption(
                        f"{row.get('source_kind', '')} · {row.get('service') or 'no service'} · "
                        f"{row.get('incident_family') or 'no incident family'}"
                    )
                    content = row.get("content", "")
                    st.write(content[:360] + ("…" if len(content) > 360 else ""))

st.divider()
st.markdown(
    "This is a comparison harness, not a universal benchmark. Use the labeled "
    "question set and repeatable benchmark profile before making production claims."
)
