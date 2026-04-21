import numpy as np
import pandas as pd
from Reaearch_Idea.code.hybrid_score import hybrid_similarity
import logging

logger = logging.getLogger("main_logger")

def abstract_retrieval(query, query_embedding, bm25_model_path, abstract_faiss_index_path, dataframe, final_k=15):
    """
    计算与查询相关的 abstract 文档的混合得分并返回最相关的文档的 unique_id、摘要文本 以及 得分。

    Args:
        query (str): 用户查询（文本）
        query_embedding (np.ndarray): 用户查询的嵌入向量
        bm25_model_path (str): BM25 模型路径
        abstract_faiss_index_path (str): FAISS 索引路径
        dataframe (pd.DataFrame): 包含文档数据的 DataFrame，需要至少包含 'doi' 和 'abstract' 列
        final_k (int): 返回最相关的前 K 个文档

    Returns:
        list of tuples: [
            (unique_id, abstract_text, score),
            ...
        ]，已经按 score 从高到低排序，并截断到前 final_k 条。
    """
    logger.debug("这是 abstract_retrieve 模块里的 DEBUG 日志")
    # 1. 获取混合相似度得分 [(idx, hybrid_score), ...]
    abstract_results = hybrid_similarity(
        abstract_faiss_index_path,
        bm25_model_path,
        query,
        query_embedding
    )

    # 2. 截断到前 final_k
    abstract_results = abstract_results[:final_k]
    logger.info("abstract_retrieval 得分 (idx, score): {}".format(abstract_results))

    if not abstract_results:
        return []

    # 3. 拆分索引和得分
    final_indices, final_scores = zip(*abstract_results)

    # 4. 根据 idx 从 dataframe 中取出 unique_id（例如 doi）和摘要文本
    unique_ids = []
    abstracts = []
    for idx in final_indices:
        row = dataframe.iloc[idx]
        unique_ids.append(row['doi'])
        # 假定摘要列名为 'abstract'
        abstracts.append(row['abstract'])

    # 5. 将 (unique_id, abstract_text, score) 组合成返回结果
    results = list(zip(unique_ids, abstracts, final_scores))
    return results
