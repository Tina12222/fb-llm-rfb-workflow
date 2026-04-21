from __future__ import annotations
import logging
import pickle
from collections import defaultdict
from functools import lru_cache
from typing import List, Tuple
import faiss
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)         


# --------------------------------------------------------------------------- #
#                               模型加载与缓存                                 #
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=8)
def _load_faiss_index(path: str) -> faiss.Index:
    """缓存读 FAISS 索引。"""
    logger.info("Loading FAISS index from %s", path)
    return faiss.read_index(path)     


@lru_cache(maxsize=8)
def _load_bm25_model(path: str):
    """缓存读 BM25 模型（兼容 gensim / rank_bm25 / 自定义 pickle）。"""
    logger.info("Loading BM25 model from %s", path)
    with open(path, "rb") as f:        # pragma: no cover
        return pickle.load(f)


# --------------------------------------------------------------------------- #
#                               归一化函数                                    #
# --------------------------------------------------------------------------- #

def _faiss_normalize(distances: np.ndarray, metric: int) -> np.ndarray:
    """
    将 FAISS 距离（或相似度）归一到 [0, 1]，越大越相关。

    * L2：   score = 1 / (1 + distance)
    * IP：   原值 ∈ [-1, 1]，映射到 (val + 1) / 2
    """
    if metric == faiss.METRIC_L2:
        return 1.0 / (1.0 + distances)
    elif metric == faiss.METRIC_INNER_PRODUCT:
        return (distances + 1.0) / 2.0
    else:                               # pragma: no cover
        raise ValueError(f"Unsupported FAISS metric {metric}")


def _bm25_normalize(raw_scores: np.ndarray) -> np.ndarray:
    """
    Per-query min-max 归一：确保分布稳定且落在 [0, 1]。
    对极端情况（全部分数相等）返回 0 向量。
    """
    min_s, max_s = raw_scores.min(), raw_scores.max()
    if max_s == min_s:
        return np.zeros_like(raw_scores)
    return (raw_scores - min_s) / (max_s - min_s)


# --------------------------------------------------------------------------- #
#                               核心接口                                      #
# --------------------------------------------------------------------------- #

def hybrid_similarity(
    faiss_index_path: str,
    bm25_model_path: str,
    query: str,
    query_embedding: np.ndarray,
    *,
    top_k: int = 20000,
    faiss_weight: float = 0.5,
    bm25_weight: float = 0.5,
) -> List[Tuple[int, float]]:
    """
    计算 Query 与文档的混合相似度。

    Parameters
    ----------
    faiss_index_path : str
        FAISS 索引文件路径。
    bm25_model_path : str
        BM25 模型 pickle 路径。
    query : str
        用户输入原文本。
    query_embedding : np.ndarray
        形状 (dim,) 或 (1, dim) 的 Query 向量。
    top_k : int
        在各自检索通道中检回的深度（不影响融合后返回多少条）。
    faiss_weight / bm25_weight : float
        融合时的线性权重；会自动归一化。
    need_adjust_index : bool
        若 True，对最终索引调用 adjust_final_top_k_indices。

    Returns
    -------
    List[Tuple[int, float]]
        按融合得分从高到低排序的 (doc_index, score) 列表。
    """
    # ----------- 1. 语义检索（FAISS） ------------------------------------- #
    index = _load_faiss_index(faiss_index_path)
    query_vec = np.atleast_2d(query_embedding).astype(np.float32)
    dist, idx = index.search(query_vec, top_k)
    semantic_scores = _faiss_normalize(dist[0], index.metric_type)
    semantic_indices = idx[0]

    # ----------- 2. 关键词检索（BM25） ----------------------------------- #
    bm25 = _load_bm25_model(bm25_model_path)
    raw_bm25_scores = bm25.get_scores(query)          # shape: (N_docs,)
    # Top-k 按分数降序
    top_bm25_indices = np.argsort(raw_bm25_scores)[::-1][:top_k]
    keyword_scores = _bm25_normalize(raw_bm25_scores[top_bm25_indices])

    # ----------- 3. 融合 -------------------------------------------------- #
    scores = defaultdict(lambda: {"sem": 0.0, "kw": 0.0})
    for i, s in zip(semantic_indices, semantic_scores):
        scores[int(i)]["sem"] = float(s)
    for i, k in zip(top_bm25_indices, keyword_scores):
        scores[int(i)]["kw"] = float(k)

    # 权重归一化
    w_sum = faiss_weight + bm25_weight
    w_sem = faiss_weight / w_sum
    w_kw = bm25_weight / w_sum

    fused: List[Tuple[int, float]] = [
        (doc_id, w_sem * v["sem"] + w_kw * v["kw"])
        for doc_id, v in scores.items()
    ]
    fused.sort(key=lambda x: x[1], reverse=True)


    logger.debug("Hybrid top-5: %s", fused[:5])
    return fused
