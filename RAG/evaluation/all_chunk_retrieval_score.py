import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from RAG.rag_core import chunk_retrieval, review_retrieval, theme_retrieval
from RAG.rag_core.config import CHUNK_BM25, CHUNK_FAISS, DB_XLSX, THEME_BM25, THEME_FAISS
from RAG.rag_core.query_process import get_keywords, preprocess_user_query
from RAG.rag_core.text_processing import preprocess_text

logger = logging.getLogger("PLOT-SCORES")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def get_embedding(text: str) -> np.ndarray:
    from FlagEmbedding import BGEM3FlagModel

    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False, device="cpu")
    vecs = model.encode([text], batch_size=32, return_sparse=False)["dense_vecs"]
    return np.atleast_2d(vecs).astype(np.float32)


def build_tokenized_query(user_query: str):
    final_query = preprocess_user_query(user_query)
    keywords = get_keywords(final_query)
    tokens_nested = [preprocess_text(kw) for kw in keywords]
    tokenized_query = list(dict.fromkeys(t for sub in tokens_nested for t in sub))
    return final_query, tokenized_query


def to_full_array(indices, scores, n: int) -> np.ndarray:
    arr = np.full(n, np.nan, dtype=float)
    for i, s in zip(indices, scores):
        arr[int(i)] = float(s)
    return arr


def main():
    db_df = pd.read_excel(DB_XLSX)
    db_df.reset_index(drop=True, inplace=True)
    n_docs = len(db_df)

    user_query = "In VRBs, how do VGCF modifications of graphite felt enhance electrode activity by altering surface chemistry and lowering the resistance of vanadium reactions?"
    final_query, tokenized_query = build_tokenized_query(user_query)
    query_vec = get_embedding(final_query)

    idx_c, score_c, *_ = chunk_retrieval.review_retrieval(
        tokenized_query, query_vec, db_df, CHUNK_FAISS, CHUNK_BM25, top_k=n_docs, channel_top_k=n_docs, content_col="chunkContent"
    )
    idx_t, score_t, *_ = theme_retrieval.review_retrieval(
        tokenized_query, query_vec, db_df, THEME_FAISS, THEME_BM25, top_k=n_docs, channel_top_k=n_docs, content_col="chunkContent"
    )
    idx_h, score_h, *_ = review_retrieval.review_retrieval(
        tokenized_query,
        query_vec,
        db_df,
        CHUNK_FAISS,
        THEME_FAISS,
        CHUNK_BM25,
        THEME_BM25,
        top_k=n_docs,
        channel_top_k=n_docs,
        chunk_weight=0.7,
        theme_weight=0.3,
        content_col="chunkContent",
    )

    s_chunk = to_full_array(idx_c, score_c, n_docs)
    s_theme = to_full_array(idx_t, score_t, n_docs)
    s_hybrid = to_full_array(idx_h, score_h, n_docs)

    x = np.arange(n_docs)
    plt.figure(figsize=(16, 6))
    plt.scatter(x, s_chunk, s=12, marker="o", color="blue", label="chunk-only", alpha=0.85)
    plt.scatter(x, s_theme, s=12, marker="x", color="orange", label="theme-only", alpha=0.85)
    plt.plot(x, s_hybrid, color="green", linewidth=1.2, label="hybrid")
    plt.xlabel("Row ID (Chunk Index)")
    plt.ylabel("Score")
    plt.title("All chunk scores (chunk-only / theme-only / hybrid)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig("all_chunk_scores.png", dpi=300)
    plt.show()


if __name__ == "__main__":
    main()
