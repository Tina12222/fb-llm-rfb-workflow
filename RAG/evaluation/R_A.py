import pandas as pd
import numpy as np
import re
from typing import Set, List
from pathlib import Path
import os

# ==== 配置 ====
PROJECT_ROOT = Path(__file__).resolve().parents[2]
excel_path = str(
    Path(
        os.getenv(
            "RAG_RA_INPUT",
            str(PROJECT_ROOT / "RAG" / "retrieval" / "theme_only" / "retrieved_theme.xlsx"),
        )
    )
)
OUT_EXCEL_PATH = str(
    Path(
        os.getenv(
            "RAG_RA_OUTPUT",
            str(PROJECT_ROOT / "RAG" / "retrieval" / "theme_only" / "theme_RA.xlsx"),
        )
    )
)



col_relevant_full = "S"   # 完全匹配（金标准）列名
col_partial = "part"      # 部分相关列名
col_retrieved = "id"      # 检索到的 TopK（有顺序）
K = 10                    # 只评一个固定的 k

# ==== 工具函数 ====
_SPLIT_PATTERN = re.compile(r"[,\s;|/，；]+")
_BRACKETS = re.compile(r"^[\[\(\{]|[\]\)\}]$")  # 去掉首尾括号

def _to_id_set(cell) -> Set[str]:
    if pd.isna(cell):
        return set()
    s = str(cell).strip()
    if not s:
        return set()
    s = _BRACKETS.sub("", s)
    parts = [p.strip() for p in _SPLIT_PATTERN.split(s) if p.strip() != ""]
    return set(parts)

def _to_id_list(cell) -> List[str]:
    if pd.isna(cell):
        return []
    s = str(cell).strip()
    if not s:
        return []
    s = _BRACKETS.sub("", s)
    parts = [p.strip() for p in _SPLIT_PATTERN.split(s) if p.strip() != ""]
    seen, ordered = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered

# ==== 读取与解析 ====
df = pd.read_excel(excel_path)

F_sets = df[col_relevant_full].apply(_to_id_set)  # 完全匹配 F
P_sets = df[col_partial].apply(_to_id_set) if col_partial in df.columns else pd.Series([set()]*len(df))  # 部分相关 P
S_lists = df[col_retrieved].apply(_to_id_list)    # 有序检索结果列表
S_sets  = S_lists.apply(set)

# 并集 U = F ∪ P
U_sets = [F.union(P) for F, P in zip(F_sets, P_sets)]

# ==== 行级指标 ====
precision_list = []       
tp_union_list = []
recall_at_k_F_list = []     
recall_at_k_U_list = []     

lenF_list, lenP_list, lenU_list, lenS_list = [], [], [], []

for F, P, U, S_list, S_set in zip(F_sets, P_sets, U_sets, S_lists, S_sets):
    # precision（TopK，并集口径）
    tp_union = len(U & S_set)
    prec = tp_union / len(S_set) if len(S_set) > 0 else np.nan

    # Recall@K(F)
    prefix = set(S_list[:K])
    hits_F = len(F & prefix)
    rec_F = hits_F / len(F) if len(F) > 0 else np.nan

    # Recall@K(U)
    hits_U = len(U & prefix)
    rec_U = hits_U / len(U) if len(U) > 0 else np.nan

    precision_list.append(prec)
    tp_union_list.append(tp_union)
    recall_at_k_F_list.append(rec_F)
    recall_at_k_U_list.append(rec_U)
    lenF_list.append(len(F))
    lenP_list.append(len(P))
    lenU_list.append(len(U))
    lenS_list.append(len(S_set))

# 写回 DataFrame
df["precision"]       = precision_list
df[f"Recall@{K}_F"]   = recall_at_k_F_list        # 只看 F
df[f"Recall@{K}_U"]   = recall_at_k_U_list        # 并集 U
df["tp_union"]        = tp_union_list
df["|F|"]             = lenF_list
df["|P|"]             = lenP_list
df["|U|"]             = lenU_list
df["|S|"]             = lenS_list

# ==== 汇总 ====
# 宏平均
macro_precision = float(np.nanmean(df["precision"])) if len(df) else float("nan")
macro_recall_F  = float(np.nanmean(df[f"Recall@{K}_F"])) if len(df) else float("nan")
macro_recall_U  = float(np.nanmean(df[f"Recall@{K}_U"])) if len(df) else float("nan")

# 微平均
TP_union_total = int(df["tp_union"].sum())
S_total        = int(df["|S|"].sum())
micro_precision = TP_union_total / S_total if S_total > 0 else float("nan")

# Recall 微平均 (F, U)
hits_F_total, F_total = 0, 0
hits_U_total, U_total = 0, 0
for F, U, S_list in zip(F_sets, U_sets, S_lists):
    prefix = set(S_list[:K])
    if len(F) > 0:
        hits_F_total += len(F & prefix)
        F_total += len(F)
    if len(U) > 0:
        hits_U_total += len(U & prefix)
        U_total += len(U)

micro_recall_F = hits_F_total / F_total if F_total > 0 else float("nan")
micro_recall_U = hits_U_total / U_total if U_total > 0 else float("nan")

# ==== 打印 ====
print("=== 行级指标（前10行预览）===")
print(df[[col_relevant_full, col_partial, col_retrieved, "precision", f"Recall@{K}_F", f"Recall@{K}_U"]].head(10))

print("\n=== 宏平均（Macro）===")
print(f"Precision_macro (U=F∪P, all topk) = {macro_precision:.6f}")
print(f"Recall@{K}_macro (F only)          = {macro_recall_F:.6f}")
print(f"Recall@{K}_macro (U=F∪P)           = {macro_recall_U:.6f}")

print("\n=== 微平均（Micro）===")
print(f"Precision_micro (U=F∪P, all topk)  = {micro_precision:.6f}")
print(f"Recall@{K}_micro (F only)          = {micro_recall_F:.6f}")
print(f"Recall@{K}_micro (U=F∪P)           = {micro_recall_U:.6f}")

# ==== 保存 ====
df.to_excel(OUT_EXCEL_PATH, index=False)
print(f"\n结果已保存到 {OUT_EXCEL_PATH}")
