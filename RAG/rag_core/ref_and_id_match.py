import logging
from collections.abc import Iterable
from typing import Any, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 可在主程序入口调整日志级别


def adjust_final_top_k_indices(
    final_top_k_indices: List[int],
    dataframe: pd.DataFrame
) -> List[Any]:
    """
    将位置索引映射为 DataFrame 的实际行标签。

    参数:
        final_top_k_indices (List[int]): DataFrame 的位置索引列表
        dataframe (pd.DataFrame): 用于映射的 DataFrame
    返回:
        List[Any]: 对应的 DataFrame 行标签列表
    """
    try:
        # 使用 .index.take 保留原 DataFrame 索引标签
        mapped = list(dataframe.index.take(final_top_k_indices))
        logger.debug("Mapped indices %s to labels %s", final_top_k_indices, mapped)
        return mapped
    except Exception as e:
        logger.error("映射索引失败: %s", e)
        # 兜底返回原位置索引
        return final_top_k_indices.copy()


def extract_references_and_id(
    dataframe: pd.DataFrame,
    final_top_k_indices: List[Any],
    reference_column: str = 'reference',
    ref_id_column: str = 'ref_ids',
    index_is_location: bool = True
) -> List[Tuple[List[str], List[str]]]:
    """
    从 DataFrame 中提取指定行的 reference 和 ref_ids 列内容。

    参数:
        dataframe (pd.DataFrame): 已读取的 DataFrame
        final_top_k_indices (List[Any]): 索引列表（位置或标签）
        reference_column (str): 参考文献列名，默认 'reference'
        ref_id_column (str): 唯一标识列名，默认 'ref_ids'
        index_is_location (bool): True 表示 final_top_k_indices 为位置索引，使用 .iloc；
                                False 表示为标签索引，使用 .loc。

    返回:
        List[Tuple[List[str], List[str]]]: 每行 (reference_list, ref_ids_list)
    """
    # 列存在性检查
    for col in (reference_column, ref_id_column):
        if col not in dataframe.columns:
            logger.error("DataFrame 中缺少列 '%s'", col)
            raise KeyError(f"DataFrame 中缺少列 '{col}'")

    # 子集提取，减少循环内访问开销
    if index_is_location:
        try:
            subset = dataframe.iloc[final_top_k_indices][[reference_column, ref_id_column]]
        except Exception as e:
            logger.error("使用 iloc 提取子集失败: %s", e)
            raise
    else:
        try:
            subset = dataframe.loc[final_top_k_indices][[reference_column, ref_id_column]]
        except Exception as e:
            logger.error("使用 loc 提取子集失败: %s", e)
            raise

    results: List[Tuple[List[str], List[str]]] = []
    total = len(subset)
    for pos, (_, row) in enumerate(subset.iterrows()):
        refs = row[reference_column]
        ids = row[ref_id_column]

        # 处理可能的缺失值
        if pd.isna(refs):
            ref_list: List[str] = []
        elif isinstance(refs, Iterable) and not isinstance(refs, (str, bytes)):
            ref_list = list(refs)
        else:
            ref_list = [str(refs)]

        if pd.isna(ids):
            id_list: List[str] = []
        elif isinstance(ids, Iterable) and not isinstance(ids, (str, bytes)):
            id_list = list(ids)
        else:
            id_list = [str(ids)]

        results.append((ref_list, id_list))

    if len(results) != total:
        logger.warning("提取的结果数量 %d 与期望 %d 不符", len(results), total)
    return results
