# eval_retrieval_metrics.py
import re
import math
import numpy as np
import pandas as pd
from pathlib import Path
import os

# === 按需修改路径 ===
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_XLSX = str(Path(os.getenv("RAG_METRICS_INPUT", str(PROJECT_ROOT / "RAG" / "queries_with_ids.xlsx"))))
OUTPUT_XLSX = str(Path(os.getenv("RAG_METRICS_OUTPUT", str(PROJECT_ROOT / "RAG" / "queries_with_metrics.xlsx"))))
K = 5  # 统计@k，与你的 id 列长度一致
# ===================

def _norm_int(s):
    """把 '1', '1.0', 1.0 都规范成 int；无法转的返回 None。"""
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        f = float(s)
        if f.is_integer():
            return int(f)
    except Exception:
        pass
    try:
        return int(s)
    except Exception:
        return None

def parse_list(cell):
    """把 '1,2, 3' / '1 2 3' / '[1,2,3]' 都解析成 int 列表。"""
    if cell is None or (isinstance(cell, float) and math.isnan(cell)):
        return []
    s = str(cell).strip()
    if not s:
        return []
    s = s.strip("[](){}")
    parts = re.split(r"[,\s;]+", s)
    out = []
    for p in parts:
        v = _norm_int(p)
        if v is not None:
            out.append(v)
    return out

def main():
    df = pd.read_excel(INPUT_XLSX)

    # 取标注：优先 labels（多标注），否则 index（单一标注）
    if "labels" in df.columns:
        gt_list = df["labels"].apply(parse_list)
    elif "index" in df.columns:
        gt_list = df["index"].apply(lambda x: [v] if (v := _norm_int(x)) is not None else [])
    else:
        raise KeyError("缺少标注列：请提供 'labels'（多标注）或 'index'（单标注）")

    if "id" not in df.columns:
        raise KeyError("缺少检索结果列 'id'（逗号分隔的 top-k 索引）")

    ret_list = df["id"].apply(parse_list).apply(lambda xs: xs[:K])

    # 可选的 top1 列
    has_top1 = "most_like" in df.columns
    top1 = df["most_like"].apply(_norm_int) if has_top1 else pd.Series([None]*len(df))

    # —— 逐行计算 —— #
    top1_acc = []
    p_at_k   = []
    r_at_k   = []

    # 额外常见指标（可选）
    mrr_at_k = []
    ap_at_k  = []  # Average Precision@k

    # 微平均统计用
    micro_hits = 0
    micro_retrieved = 0
    micro_relevant = 0

    for gt, ret, t1 in zip(gt_list, ret_list, top1):
        gt_set = set(gt)
        if not ret:
            # 没有任何检索结果
            top1_acc.append(0.0)
            p_at_k.append(0.0)
            r_at_k.append(0.0)
            mrr_at_k.append(0.0)
            ap_at_k.append(0.0)
            micro_retrieved += 0
            micro_relevant  += len(gt_set)
            continue

        # Top1 准确率（若 most_like 不提供，就用 ret[0] 代替）
        top1_pred = t1 if t1 is not None else ret[0]
        top1_acc.append(1.0 if (top1_pred in gt_set and len(gt_set) > 0) else 0.0)

        # 命中布尔序列（用于 MRR/AP/nDCG）
        hits_bool = [1 if r in gt_set else 0 for r in ret]
        hits = sum(hits_bool)

        # P@k / R@k
        p = hits / len(ret)
        r = (hits / len(gt_set)) if len(gt_set) > 0 else 0.0
        p_at_k.append(p)
        r_at_k.append(r)

        # 微平均统计
        micro_hits      += hits
        micro_retrieved += len(ret)
        micro_relevant  += len(gt_set)

        # MRR@k
        rr = 0.0
        for rank, h in enumerate(hits_bool, start=1):
            if h:
                rr = 1.0 / rank
                break
        mrr_at_k.append(rr)

        # AP@k（平均精度，截断到 k）
        if len(gt_set) == 0:
            ap_at_k.append(0.0)
        else:
            precs = []
            cum = 0
            for i, h in enumerate(hits_bool, start=1):
                if h:
                    cum += 1
                    precs.append(cum / i)
            ap_at_k.append(sum(precs) / len(gt_set) if len(gt_set) > 0 else 0.0)

    # —— 汇总 —— #
    macro_p = float(np.mean(p_at_k)) if len(p_at_k) else 0.0
    macro_r = float(np.mean(r_at_k)) if len(r_at_k) else 0.0
    macro_f1 = (2*macro_p*macro_r/(macro_p+macro_r)) if (macro_p+macro_r)>0 else 0.0

    micro_p = (micro_hits / micro_retrieved) if micro_retrieved>0 else 0.0
    micro_r = (micro_hits / micro_relevant)  if micro_relevant>0  else 0.0
    micro_f1 = (2*micro_p*micro_r/(micro_p+micro_r)) if (micro_p+micro_r)>0 else 0.0

    summary = {
        "Top1_Acc_mean": float(np.mean(top1_acc)) if top1_acc else 0.0,
        f"P@{K}_macro": macro_p,
        f"R@{K}_macro": macro_r,
        f"F1@{K}_macro": macro_f1,
        f"P@{K}_micro": micro_p,
        f"R@{K}_micro": micro_r,
        f"F1@{K}_micro": micro_f1,
        f"MRR@{K}_mean": float(np.mean(mrr_at_k)) if mrr_at_k else 0.0,
        f"AP@{K}_mean":  float(np.mean(ap_at_k)) if ap_at_k else 0.0,
    }

    # 写回每行的指标
    df[f"Top1_Acc"] = top1_acc
    df[f"P@{K}"]    = p_at_k
    df[f"R@{K}"]    = r_at_k
    df[f"MRR@{K}"]  = mrr_at_k
    df[f"AP@{K}"]   = ap_at_k

    # 导出（两个 sheet：明细 + 汇总）
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="per_query", index=False)
        pd.DataFrame([summary]).to_excel(writer, sheet_name="summary", index=False)

    print("=== Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v:.4f}")
    print(f"\n结果已保存：{OUTPUT_XLSX}")

if __name__ == "__main__":
    main()
