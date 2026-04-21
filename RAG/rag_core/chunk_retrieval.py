import logging
from collections import defaultdict
from typing import Tuple, List

import numpy as np
import pandas as pd

from RAG.rag_core.ref_and_id_match import extract_references_and_id
from RAG.rag_core.hybrid_score import hybrid_similarity

# 模块日志配置
logger = logging.getLogger(__name__)
# 日志级别建议在应用入口统一设置，模块内保持 INFO 级别以上
logger.setLevel(logging.INFO)


def review_retrieval(
    query: str,
    query_vector: np.ndarray,
    dataframe: pd.DataFrame,
    chunk_faiss_index_path: str,
    chunk_bm25_model_path: str,
    top_k: int,
    channel_top_k: int = 10000,
    content_col: str = "chunkContent"
) -> Tuple[
    np.ndarray,
    List[float],
    List[str],
    List[List[str]],
    List[List[str]]
]:
    """
    对 review 进行检索，返回最相关的 chunk。

    1) 对 chunk 通道使用 hybrid_similarity 检索，得到带权重的得分。
    2) 合并两路得分并排序，截取 top_k。
    3) 从 dataframe 中取文本、提取参考文献与唯一 ID。

    Returns:
        final_top_k_indices (np.ndarray): 文档行索引
        final_top_k_scores (List[float]): 对应行的融合得分
        final_top_k_documents (List[str]): 对应行的文本内容
        references_list (List[List[str]]): 每条 chunk 对应的参考文献列表
        unique_ids (List[List[str]]): 每条 chunk 对应的唯一标识列表
    """
    logger.info("Starting review_retrieval for query: %s", query)

    # 1) chunk 通道检索
    try:
        chunk_results = hybrid_similarity(
            chunk_faiss_index_path,
            chunk_bm25_model_path,
            query,
            query_vector,
            top_k=channel_top_k,
            faiss_weight=1.0,
            bm25_weight=1.0
        )
    except Exception as e:
        logger.error("Error in chunk hybrid_similarity: %s", e)
        chunk_results = []

    logger.debug("chunk_results: %s", chunk_results)


    doc_score_map: defaultdict[int, float] = defaultdict(float)
    for idx, score in chunk_results:
        doc_score_map[idx] += score

    # 排序并截取 top_k
    sorted_results = sorted(
        doc_score_map.items(), key=lambda x: x[1], reverse=True
    )[:top_k]

    if not sorted_results:
        logger.warning("review_retrieval finished: no results found for query '%s'", query)
        return np.array([]), [], [], [], []

    final_indices, final_scores = zip(*sorted_results)
    final_top_k_indices = np.array(final_indices, dtype=int)
    final_top_k_scores = list(final_scores)

    # 4) 提取文档内容
    try:
        final_top_k_documents = dataframe.iloc[
            final_top_k_indices
        ][content_col].tolist()
    except Exception as e:
        logger.error("Error fetching documents from dataframe: %s", e)
        final_top_k_documents = []

    # 5) 提取参考文献与唯一 ID
    try:
        refs_and_ids = extract_references_and_id(
            dataframe, final_top_k_indices
        )
        references_list = [item[0] for item in refs_and_ids]
        unique_ids = [item[1] for item in refs_and_ids]
    except Exception as e:
        logger.error("Error extracting references and IDs: %s", e)
        references_list = [[] for _ in final_top_k_indices]
        unique_ids = [[] for _ in final_top_k_indices]

    # 6) 结果日志输出
    logger.info("=== review_retrieval results for query: '%s' ===", query)
    for rank, (idx, score, doc, refs, uids) in enumerate(
        zip(final_top_k_indices, final_top_k_scores, final_top_k_documents, references_list, unique_ids), start=1
    ):
        logger.info(
            "Rank %d | idx=%d | score=%.4f | preview=%s",
            rank,
            idx,
            score,
            doc
        )
    logger.info("===============================================")

    return (
        final_top_k_indices,
        final_top_k_scores,
        final_top_k_documents,
        references_list,
        unique_ids,
    )
