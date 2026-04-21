from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from RAG.rag_core.query_process import get_keywords, preprocess_user_query
from RAG.rag_core.review_retrieval import review_retrieval
from RAG.rag_core.text_processing import preprocess_text
from RAG.rag_core.config import CHUNK_BM25, CHUNK_FAISS, DB_XLSX, THEME_BM25, THEME_FAISS


def build_arg_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[2]
    default_out = project_root / "RAG" / "retrieval" / "hybrid" / "retrieval_results.xlsx"
    default_log = project_root / "RAG" / "retrieval" / "hybrid" / "retrieval_search.log"
    default_input = project_root / "RAG" / "accuracy_test.xlsx"

    parser = argparse.ArgumentParser(description="Run hybrid retrieval on a query Excel file.")
    parser.add_argument("--input", type=Path, default=default_input, help="Input Excel containing a 'query' column.")
    parser.add_argument("--output", type=Path, default=default_out, help="Output Excel path.")
    parser.add_argument("--log-file", type=Path, default=default_log, help="Log file path.")
    parser.add_argument("--db-xlsx", type=Path, default=Path(DB_XLSX), help="Review database Excel path.")
    parser.add_argument("--save-every", type=int, default=1, help="Checkpoint every N rows.")
    parser.add_argument("--skip-done", action="store_true", help="Skip rows with existing id.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true", help="Validate imports and paths only.")
    return parser


def setup_logger(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("chunk_search")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
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


def retrieve_topk_indices(db_df: pd.DataFrame, user_query: str, top_k: int) -> Tuple[List[int], Optional[int]]:
    final_query = preprocess_user_query(user_query)
    keywords = get_keywords(final_query)
    tokens_nested = [preprocess_text(kw) for kw in keywords]
    tokenized_query = list(dict.fromkeys(t for sub in tokens_nested for t in sub))

    query_vec = get_embedding(final_query)
    if query_vec.size == 0:
        return [], None

    scores = review_retrieval(
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

    indices = scores[0]
    if getattr(indices, "size", 0) == 0:
        return [], None

    indices = [int(x) for x in indices]
    return indices[:top_k], indices[0]


def save_checkpoint(df: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f"{out_path.stem}.tmp{out_path.suffix}")
    with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    tmp_path.replace(out_path)


def main() -> int:
    args = build_arg_parser().parse_args()
    logger = setup_logger(args.log_file)

    if args.dry_run:
        print("[dry-run] CHUNK_SEARCH checks")
        print(f"input={args.input}")
        print(f"output={args.output}")
        print(f"db={args.db_xlsx}")
        print(f"chunk_faiss={CHUNK_FAISS}")
        print(f"theme_faiss={THEME_FAISS}")
        return 0

    if not args.input.exists():
        logger.error("Input Excel not found: %s", args.input)
        return 1
    if not args.db_xlsx.exists():
        logger.error("DB Excel not found: %s", args.db_xlsx)
        return 1

    db_df = pd.read_excel(args.db_xlsx)
    db_df.reset_index(drop=True, inplace=True)

    qdf = pd.read_excel(args.input)
    if "query" not in qdf.columns:
        logger.error("Input Excel must contain column 'query'.")
        return 1

    qdf["id"] = qdf.get("id", "").astype(str)
    qdf["most_like"] = qdf.get("most_like", "").astype(str)

    for i, row in qdf.iterrows():
        if args.skip_done and qdf.at[i, "id"].strip():
            continue
        query = str(row.get("query", "")).strip()
        if len(query) < 3:
            qdf.at[i, "id"] = ""
            qdf.at[i, "most_like"] = ""
            continue

        top_ids, most_like = retrieve_topk_indices(db_df, query, args.top_k)
        qdf.at[i, "id"] = ",".join(map(str, top_ids))
        qdf.at[i, "most_like"] = "" if most_like is None else str(most_like)

        if args.save_every > 0 and (i + 1) % args.save_every == 0:
            save_checkpoint(qdf, args.output)

    save_checkpoint(qdf, args.output)
    logger.info("Saved results to %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
