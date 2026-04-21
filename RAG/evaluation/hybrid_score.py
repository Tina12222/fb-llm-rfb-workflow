import numpy as np
import faiss
import pickle
from collections import defaultdict
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main_logger")



def calculate_faiss_similarity(query_embedding, faiss_index_path, k_semantic=1300):
    """
    使用 FAISS 计算向量相似度，返回 (scores, indices)
    """
    index = faiss.read_index(faiss_index_path)
    D_semantic, I_semantic = index.search(query_embedding, k_semantic)
    # FAISS 距离越小相似度越大，这里用负距离当作分数
    distances = D_semantic[0]
    return distances, I_semantic[0]

def calculate_bm25_similarity(query, bm25_model_path, k_bm25=1300):
    """
    使用 BM25 模型计算关键词相似度，返回 (scores, indices)
    """
    with open(bm25_model_path, 'rb') as f:
        bm25_model = pickle.load(f)

    bm25_scores = bm25_model.get_scores(query)
    
    bm25_top_k_indices = bm25_scores.argsort()[::-1][:k_bm25]
    return bm25_scores, bm25_top_k_indices



def faiss_normalize_scores(scores: np.ndarray) -> np.ndarray:
    return 1 / (1 + scores)

def sigmoid(score, k=1.0):
    return 2 / (1 + np.exp(-k * score)) - 1

def bm25_normalize_scores(scores: np.ndarray) -> np.ndarray:
    return sigmoid(scores)



def hybrid_similarity(
    faiss_index_path: str,
    query: str,
    query_embedding: np.ndarray,
    bm25_model_path: str,
    top_k: int = 20000,
    faiss_weight: float = 0.5,
    bm25_weight: float = 0.5
) -> list:
    """
    使用 BM25 + FAISS 的混合相似度计算，返回 [(index, hybrid_score), ...] 

    Args:
        faiss_index_path (str): FAISS 索引路径
        query (str): 用户原始文本 query
        query_embedding (np.ndarray): 用户 query 的向量 (1, dim)
        bm25_model_path (str): BM25 模型路径
        faiss_weight (float): 语义相似度权重
        bm25_weight (float): 关键词相似度权重

    Returns:
        list of (adjusted_index, hybrid_score)
    """
    # 计算语义相似度
    distances, semantic_indices = calculate_faiss_similarity(query_embedding, faiss_index_path)
    logger.debug("distances: {}".format(distances))
    logger.debug("semantic_indices: {}".format(semantic_indices))

    # 计算关键词相似度
    bm25_scores, bm25_top_k_indices = calculate_bm25_similarity(query, bm25_model_path)
    keywords_scores = bm25_scores[bm25_top_k_indices]
    logger.debug("bm25_scores: {}".format(bm25_scores))
    logger.debug("bm25_top_k_indices: {}".format(bm25_top_k_indices))

    # 分别归一化
    semantic_scores_normalized = faiss_normalize_scores(distances)
    keywords_scores_normalized = bm25_normalize_scores(keywords_scores)
    logger.debug("semantic_scores_normalized: {}".format(semantic_scores_normalized))
    logger.debug("keywords_scores_normalized: {}".format(keywords_scores_normalized))

    # 用字典记录某个 doc 的语义分数、关键词分数
    doc_scores = defaultdict(lambda: {'semantic': 0.0, 'keywords': 0.0})

    # 记录语义得分
    for idx, s_score in zip(semantic_indices, semantic_scores_normalized):
        doc_scores[idx]['semantic'] = s_score

    # 记录关键词得分
    for idx, k_score in zip(bm25_top_k_indices, keywords_scores_normalized):
        doc_scores[idx]['keywords'] = k_score

    # 计算混合得分
    final_scores_with_indices = []
    for idx, score_dict in doc_scores.items():
        final_score = faiss_weight * score_dict['semantic'] + bm25_weight * score_dict['keywords']
        final_scores_with_indices.append((idx, final_score))

    # 按混合得分降序排序
    final_scores_with_indices.sort(key=lambda x: x[1], reverse=True)
    

    # # 可能需要对索引进行特殊“adjust”处理
    # all_indices = [idx for idx, _ in final_scores_with_indices]
    # adjusted_indices = adjust_final_top_k_indices(all_indices)
    # all_scores = [score for _, score in final_scores_with_indices]

    # # 拼回成 [(adjusted_idx, score), ...]
    # result = list(zip(adjusted_indices, all_scores))
    # logger.debug("hybrid_similarity 计算的所有得分：{}".format(final_scores_with_indices))
    return final_scores_with_indices
