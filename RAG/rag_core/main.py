from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, List, Tuple

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent

from RAG.rag_core.abstract_retrieve import abstract_retrieval
from RAG.rag_core.config import (
    CHUNK_BM25,
    CHUNK_FAISS,
    DB_XLSX,
    REF_BM25,
    REF_FAISS,
    REF_XLSX,
    THEME_BM25,
    THEME_FAISS,
    summarize_paths,
)
from RAG.rag_core.query_process import get_keywords, preprocess_user_query
from RAG.rag_core.review_retrieval import review_retrieval
from RAG.rag_core.rewrite_score import rewrite_scores
from RAG.rag_core.text_processing import preprocess_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG main retrieval pipeline")
    parser.add_argument("--query", type=str, default="", help="User query. If omitted, interactive input is used.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--log-file", type=Path, default=SCRIPT_DIR.parent / "rag.log")
    parser.add_argument("--dry-run", action="store_true", help="Check import and path configuration only.")
    return parser.parse_args()


def setup_logger(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("RAG")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def get_embedding(text: str) -> np.ndarray:
    if not text.strip():
        return np.array([])
    try:
        from FlagEmbedding import BGEM3FlagModel
    except ImportError as exc:
        raise RuntimeError("Missing dependency: FlagEmbedding") from exc

    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False, device="cpu")
    vecs = model.encode([text], batch_size=32, return_sparse=False)["dense_vecs"]
    return np.atleast_2d(vecs).astype(np.float32)


def run_pipeline(query: str, top_k: int, db_df: pd.DataFrame, ref_df: pd.DataFrame, logger: logging.Logger) -> List[Tuple[str, Any, Any, float]]:
    final_query = preprocess_user_query(query)
    keywords = get_keywords(final_query)
    tokens_nested = [preprocess_text(kw) for kw in keywords]
    tokenized_query = list(dict.fromkeys(t for sub in tokens_nested for t in sub))

    query_vec = get_embedding(final_query)
    if query_vec.size == 0:
        logger.error("Failed to generate embedding.")
        return []

    review_scores = review_retrieval(
        tokenized_query,
        query_vec,
        db_df,
        CHUNK_FAISS,
        THEME_FAISS,
        CHUNK_BM25,
        THEME_BM25,
        top_k=top_k,
        content_col="chunkContent",
    )
    if review_scores[0].size == 0:
        logger.warning("No review results.")
        return []

    abstract_scores = abstract_retrieval(
        tokenized_query,
        query_vec,
        REF_BM25,
        REF_FAISS,
        ref_df,
        doi_column="doi",
        final_k=top_k,
        index_is_location=True,
    )

    reranked = rewrite_scores(
        review_scores,
        abstract_scores,
        doc_ref_weight=0.1,
        ref_count_weight=0.1,
        top_k=top_k,
    )

    mapped: List[Tuple[str, Any, Any, float]] = []
    for typ, uid, content, score in reranked:
        if typ == "document":
            mapped.append((typ, uid, content, score))
        else:
            ref_rows = ref_df.loc[ref_df["doi"] == uid]
            text = ref_rows.iloc[0]["abstract"] if not ref_rows.empty else "(no abstract)"
            mapped.append((typ, uid, text, score))
    return mapped


def main() -> int:
    args = parse_args()
    logger = setup_logger(args.log_file)

    if args.dry_run:
        print("[dry-run] RAG main checks")
        for k, v in summarize_paths().items():
            print(f"{k}={v}")
        return 0

    db_path = Path(DB_XLSX)
    ref_path = Path(REF_XLSX)
    if not db_path.exists() or not ref_path.exists():
        logger.error("Missing data files. DB=%s REF=%s", db_path, ref_path)
        return 1

    db_df = pd.read_excel(db_path)
    db_df.reset_index(drop=True, inplace=True)
    ref_df = pd.read_excel(ref_path)
    ref_df.reset_index(drop=True, inplace=True)

    query = args.query.strip()
    if not query:
        try:
            query = input("请输入您的问题: ").strip()
        except EOFError:
            logger.error("No query provided.")
            return 1

    if len(query) < 3:
        logger.error("Query too short.")
        return 1

    results = run_pipeline(query, args.top_k, db_df, ref_df, logger)
    logger.info("Retrieved %d items.", len(results))
    for i, item in enumerate(results, start=1):
        logger.info("%d. %s", i, item)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
