import logging
from typing import List, Tuple, Any

import numpy as np
import pandas as pd
from RAG.rag_core.hybrid_score import hybrid_similarity
from RAG.rag_core.ref_and_id_match import adjust_final_top_k_indices

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 可以在主程序入口设置为 DEBUG


def abstract_retrieval(
    query: str,
    query_embedding: np.ndarray,
    bm25_model_path: str,
    abstract_faiss_index_path: str,
    dataframe: pd.DataFrame,
    doi_column: str = "doi",
    abstract_col: str = "abstract",  # 用于日志预览，可不存在
    final_k: int = 15,
    index_is_location: bool = True,
) -> List[Tuple[Any, float]]:
    """
    计算与查询相关的 abstract 文档的混合相似度，并返回最相关文档的 unique_id 及其得分。

    Returns
    -------
    List[Tuple[Any, float]]
        每个元素为 (unique_id, score)，按 score 降序排列，最多 final_k 条。
    """
    logger.info("Starting abstract_retrieval for query: %s", query)

    # 1) 确保 embedding 形状正确
    try:
        query_vec = np.atleast_2d(query_embedding).astype(np.float32)
    except Exception as e:
        logger.error("Invalid query_embedding format: %s", e)
        return []

    # 2) 调用混合检索
    try:
        results = hybrid_similarity(
            abstract_faiss_index_path,
            bm25_model_path,
            query,
            query_vec,
            top_k=10000,
        )
    except Exception as e:
        logger.error("Error in hybrid_similarity: %s", e)
        return []

    if not results:
        logger.warning("abstract_retrieval finished: no results found for query '%s'", query)
        return []

    # 3) 取 top_k
    results = results[:final_k]
    indices, scores = zip(*results)

    # 4) 如果需要，将位置索引映射到行标签
    if index_is_location:
        try:
            mapped_indices = adjust_final_top_k_indices(list(indices), dataframe)
        except Exception as e:
            logger.error("Error adjusting indices: %s", e)
            mapped_indices = list(indices)
    else:
        mapped_indices = list(indices)

    # 5) 获取 unique_ids
    unique_ids: List[Any] = []
    for idx in mapped_indices:
        try:
            uid = dataframe.loc[idx, doi_column]
            unique_ids.append(uid)
        except Exception as e:
            logger.error("Error fetching %s at index %s: %s", doi_column, idx, e)
            unique_ids.append(None)

    abstract_scores: List[Tuple[Any, float]] = list(zip(unique_ids, scores))

    # 6) 结果日志输出
    logger.info("=== abstract_retrieval results for query: '%s' ===", query)
    for rank, (uid, score, idx) in enumerate(zip(unique_ids, scores, mapped_indices), start=1):
        # 预览摘要前 120 字（若列存在）
        try:
            preview_raw = dataframe.loc[idx, abstract_col] if abstract_col in dataframe.columns else ""
        except Exception:
            preview_raw = ""
        preview = str(preview_raw)[0:120].replace("\n", " ") + ("..." if isinstance(preview_raw, str) and len(preview_raw) > 120 else "")

        logger.info(
            "Rank %d | uid=%s | score=%.4f | preview=%s",
            rank,
            uid,
            score,
            preview_raw,
        )
    logger.info("===============================================")

    return abstract_scores
