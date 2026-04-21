import logging
from typing import Tuple, List, Any
from collections import defaultdict

import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 主程序可调为 DEBUG


def rewrite_scores(
    review_scores: Tuple[np.ndarray, List[float], List[str], List[List[Any]], List[Any]],
    abstract_scores: List[Tuple[Any, float]],
    doc_ref_weight: float = 0.1,
    ref_count_weight: float = 0.1,
    top_k: int = 20,
) -> List[Tuple[str, Any, Any, float]]:
    """根据引用关系重新计算文档与参考文献评分，并返回排名前 top_k 的条目。"""
    logger.info("Starting rewrite_scores -> top_k=%d", top_k)

    # --------------------- 解包 & 校验 --------------------- #
    try:
        indices, doc_scores, doc_contents, doc_references, doc_ids = review_scores
    except Exception as e:
        logger.error("Invalid review_scores structure: %s", e)
        return []

    n = len(indices)
    if not (
        n == len(doc_scores) == len(doc_contents) == len(doc_references) == len(doc_ids)
    ):
        logger.error(
            "review_scores elements length mismatch: indices=%d, scores=%d, contents=%d, refs=%d, ids=%d",
            n,
            len(doc_scores),
            len(doc_contents),
            len(doc_references),
            len(doc_ids),
        )
        raise ValueError("review_scores elements length mismatch")

    # --------------------- Data 准备 --------------------- #
    abstract_map = {ref_id: float(score) for ref_id, score in abstract_scores}
    ref_counter: defaultdict[Any, int] = defaultdict(int)
    doc_items: List[Tuple[str, Any, Any, float]] = []
    ref_items: List[Tuple[str, Any, Any, float]] = []

    # ------------------ 第一阶段：文档 ------------------ #
    for idx, orig_score, content, refs, doc_id in zip(
        indices, doc_scores, doc_contents, doc_references, doc_ids
    ):
        orig_score = float(orig_score)
        unique_refs = set(refs)  # 去重
        valid_refs = [r for r in unique_refs if r in abstract_map]
        boost = len(valid_refs) * doc_ref_weight
        for r in valid_refs:
            ref_counter[r] += 1
        new_score = orig_score + boost
        doc_items.append(("document", doc_id, content, new_score))

    # ------------------ 第二阶段：参考文献 ------------------ #
    for ref_id, orig_score in abstract_scores:
        orig_score = float(orig_score)
        count = ref_counter.get(ref_id, 0)
        new_score = orig_score + count * ref_count_weight
        ref_items.append(("reference", ref_id, None, new_score))

    # ------------------ 合并 & 排序 ------------------ #
    items: List[Tuple[str, Any, Any, float]] = doc_items + ref_items
    items.sort(key=lambda x: x[3], reverse=True)
    top_items = items[:top_k]

    # ------------------ 日志输出 ------------------ #
    logger.info("=== rewrite_scores Document Results (top %d) ===", top_k)
    for rank, (typ, did, content, score) in enumerate(top_items, start=1):
        if typ != "document":
            continue
        preview = (content or "")[0:120].replace("\n", " ") + (
            "..." if content and len(content) > 120 else ""
        )
        logger.info("Rank %d | doc_id=%s | score=%.4f | preview=%s", rank, did, score, preview)

    logger.info("=== rewrite_scores Abstract/Reference Results (top %d) ===", top_k)
    for rank, (typ, rid, _, score) in enumerate(top_items, start=1):
        if typ != "reference":
            continue
        logger.info("Rank %d | ref_id=%s | score=%.4f", rank, rid, score)

    logger.info("==========================================================")
    return top_items
