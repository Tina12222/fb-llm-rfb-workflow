# -*- coding: utf-8 -*-
"""
dedup.py —— 参考文献去重模块
【既能被 import 调用，也能独立运行】
"""
from __future__ import annotations
import json, logging, argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any, Set
import re
# --------------------------------------------------------------------------- #
# 0. 公共工具
# --------------------------------------------------------------------------- #
DOI_PREFIX_RE = re.compile(r"^https?://(dx\.)?doi\.org/", flags=re.I)

def normalize_doi(doi: str | None) -> str:
    """
    统一 DOI 写法：
    1) 去掉前后空白
    2) 去掉 https://doi.org/ 或 dx.doi.org/ 前缀
    3) 全部转小写
    """
    if not doi:
        return ""
    doi = DOI_PREFIX_RE.sub("", doi.strip())   # 删除前缀
    return doi.lower()

def _tokenize(text: str) -> Set[str]:
    """简单分词：小写 + 去标点（只保留字母/数字）"""
    import re
    return set(re.findall(r"\b[\w\-]+\b", text.lower()))

def is_similar_title(t1: str, t2: str, threshold: float = 0.8) -> bool:
    """Jaccard 相似度判定标题是否相近"""
    s1, s2 = _tokenize(t1), _tokenize(t2)
    if not s1 or not s2:
        return False
    return len(s1 & s2) / len(s1 | s2) >= threshold

def normalize_authors(authors: List[str]) -> str:
    return ",".join(a.replace(" ", "").lower() for a in authors or [])

# --------------------------------------------------------------------------- #
# 1. 纯逻辑：去重
# --------------------------------------------------------------------------- #
def deduplicate_references(
    refs: List[Dict[str, Any]],
    title_threshold: float = 0.8,
    short_len: int = 28,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    先按 DOI 精确去重，再对无 DOI 条目做标题 + 元信息匹配去重。
    返回 (unique_refs, duplicate_refs)
    """
    # —— ① DOI 去重
    doi_index: Dict[str, Dict[str, Any]] = {}
    no_doi_refs: List[Dict[str, Any]] = []
    dup_refs: List[Dict[str, Any]] = []

    for ref in refs:
        raw_doi = ref.get("doi")
        doi = normalize_doi(raw_doi) 
        if doi:
            if doi in doi_index:
                dup_refs.append(ref)
            else:
                doi_index[doi] = ref
        else:
            no_doi_refs.append(ref)

    # —— ② 处理无 DOI 的条目
    processed_long: List[Tuple[str, str, int | None]] = []  # (norm_title, norm_authors, year)
    unique_long:  List[Dict[str, Any]] = []
    short_refs:   List[Dict[str, Any]] = []

    for ref in no_doi_refs:
        title   = (ref.get("title") or "").strip()
        authors = ref.get("authors", [])
        year    = ref.get("year")

        # 无标题或标题较短 -> 留到短标题流程
        if not title or len(title) < short_len:
            short_refs.append(ref)
            continue

        # 长标题：先归一化，再模糊匹配已有记录
        norm_title = title.lower()
        norm_auth  = normalize_authors(authors)
        is_dup = any(
            norm_auth == pa and year == py and
            is_similar_title(norm_title, pt, title_threshold)
            for pt, pa, py in processed_long
        )
        if is_dup:
            dup_refs.append(ref)
        else:
            processed_long.append((norm_title, norm_auth, year))
            unique_long.append(ref)

    # —— ③ 短标题精确去重（tuple: authors, year, volume, title.lower()）
    seen: Set[Tuple[str, int | None, str, str]] = set()
    unique_short: List[Dict[str, Any]] = []
    for ref in short_refs:
        tpl = (
            normalize_authors(ref.get("authors", [])),
            ref.get("year"),
            str(ref.get("volume") or ""),
            (ref.get("title") or "").lower(),
        )
        if tpl in seen:
            dup_refs.append(ref)
        else:
            seen.add(tpl)
            unique_short.append(ref)

    # —— ④ 聚合结果
    unique_refs = list(doi_index.values()) + unique_long + unique_short
    return unique_refs, dup_refs

# --------------------------------------------------------------------------- #
# 2. I/O 层：读取 / 保存
# --------------------------------------------------------------------------- #
def load_from_json(file_path: str | Path) -> List[Dict[str, Any]]:
    file_path = Path(file_path)
    try:
        with file_path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data.get("references", data)  # 允许直接给 list
    except Exception as e:
        logging.warning("读取 %s 失败：%s", file_path.name, e)
        return []

def save_refs(
    refs: List[Dict[str, Any]], outfile: str | Path, key="references"
) -> None:
    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with outfile.open("w", encoding="utf-8") as f:
        json.dump({key: refs}, f, ensure_ascii=False, indent=2)

# --------------------------------------------------------------------------- #
# 3. CLI / __main__
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="参考文献去重")
    ap.add_argument("-i", "--input", default=r"Reference\merged_ref.json", help="合并后的 JSON 文件")
    ap.add_argument("-o", "--output", default=r"Reference\dedup_ref.json", help="去重后输出 JSON")
    ap.add_argument("-d", "--dup", default=None, help="重复项输出 JSON")
    ap.add_argument("--thr", type=float, default=0.8, help="长标题 Jaccard 阈值")
    ns = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    refs = load_from_json(ns.input)
    if not refs:
        logging.error("输入为空，终止。")
        return

    uniq, dup = deduplicate_references(refs, title_threshold=ns.thr)

    save_refs(uniq, ns.output)
    logging.info("✅ 去重完成，保留 %d 条。", len(uniq))

    if ns.dup:
        save_refs(dup, ns.dup, key="duplicates")
        logging.info("⚠️  重复条目 %d 条已写入 %s。", len(dup), ns.dup)


if __name__ == "__main__":
    main()

# 导出给其他脚本 import
__all__ = [
    "deduplicate_references",
    "load_from_json",
    "save_refs",
]
