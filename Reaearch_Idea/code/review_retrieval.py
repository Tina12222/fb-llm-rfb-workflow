import logging
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

from Reaearch_Idea.code.hybrid_score import hybrid_similarity
from RAG.rag_core.ref_and_id_match import extract_references_and_id

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def review_retrieval(
    query: str,
    query_vector: np.ndarray,
    dataframe: pd.DataFrame,
    chunk_faiss_index_path: str,
    theme_faiss_index_path: str,
    chunk_bm25_model_path: str,
    theme_bm25_model_path: str,
    top_k: int,
    channel_top_k: int = 10000,
    chunk_weight: float = 0.7,
    theme_weight: float = 0.3,
    content_col: str = "chunkContent",
) -> Tuple[np.ndarray, List[float], List[str], List[List[str]], List[List[str]]]:
    """Retrieve top-k review chunks using weighted chunk/theme hybrid scores."""
    logger.info("Starting review_retrieval for query: %s", query)

    try:
        chunk_results = hybrid_similarity(
            chunk_faiss_index_path,
            chunk_bm25_model_path,
            query,
            query_vector,
            top_k=channel_top_k,
            faiss_weight=1.0,
            bm25_weight=1.0,
        )
    except Exception as exc:
        logger.error("Error in chunk hybrid_similarity: %s", exc)
        chunk_results = []

    try:
        theme_results = hybrid_similarity(
            theme_faiss_index_path,
            theme_bm25_model_path,
            query,
            query_vector,
            top_k=channel_top_k,
            faiss_weight=1.0,
            bm25_weight=1.0,
        )
    except Exception as exc:
        logger.error("Error in theme hybrid_similarity: %s", exc)
        theme_results = []

    doc_score_map: defaultdict[int, float] = defaultdict(float)
    for idx, score in chunk_results:
        doc_score_map[idx] += chunk_weight * score
    for idx, score in theme_results:
        doc_score_map[idx] += theme_weight * score

    sorted_results = sorted(doc_score_map.items(), key=lambda x: x[1], reverse=True)[:top_k]
    if not sorted_results:
        return np.array([]), [], [], [], []

    final_indices, final_scores = zip(*sorted_results)
    final_top_k_indices = np.array(final_indices, dtype=int)
    final_top_k_scores = list(final_scores)

    try:
        final_top_k_documents = dataframe.iloc[final_top_k_indices][content_col].tolist()
    except Exception as exc:
        logger.error("Error fetching documents from dataframe: %s", exc)
        final_top_k_documents = []

    try:
        refs_and_ids = extract_references_and_id(dataframe, final_top_k_indices)
        references_list = [item[0] for item in refs_and_ids]
        unique_ids = [item[1] for item in refs_and_ids]
    except Exception as exc:
        logger.error("Error extracting references and IDs: %s", exc)
        references_list = [[] for _ in final_top_k_indices]
        unique_ids = [[] for _ in final_top_k_indices]

    return final_top_k_indices, final_top_k_scores, final_top_k_documents, references_list, unique_ids
