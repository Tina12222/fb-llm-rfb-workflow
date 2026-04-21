# -*- coding: utf-8 -*-
"""
E1-2: Overlap/Jaccard@10 between Chunk-only vs Theme-only TopK results
- Reads your two Excel files
- Parses TopK ids from col_retrieved ("id")
- Computes per-query Overlap@10, Jaccard@10, IntersectionSize@10, Unique counts
- Saves an output Excel with (1) per-query table (2) summary sheet
- Plots and saves ONE scatter: x=Overlap@10, y=Jaccard@10

Requirements:
    pip install pandas openpyxl matplotlib
"""

import os
import re
import json
import ast
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# Paths + column names (yours)
# =========================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RETRIEVAL_DIR = Path(os.getenv("RAG_RETRIEVAL_DIR", str(PROJECT_ROOT / "RAG" / "retrieval")))
chunk_path = str(Path(os.getenv("RAG_E12_CHUNK_PATH", str(RETRIEVAL_DIR / "chunk_only" / "chunk_RA.xlsx"))))
theme_path = str(Path(os.getenv("RAG_E12_THEME_PATH", str(RETRIEVAL_DIR / "73" / "C_T_Rk.xlsx"))))

col_relevant_full = "S"   # 完全匹配（金标准）列名（可选，仅用于输出保留）
col_partial = "part"      # 部分相关列名（可选，仅用于输出保留）
col_retrieved = "id"      # 检索到的 TopK（有顺序）

K = 10  # E1-2 uses @10

# Output folder
out_dir = str(Path(os.getenv("RAG_E12_OUT_DIR", str(RETRIEVAL_DIR / "E1-2_results"))))
os.makedirs(out_dir, exist_ok=True)
out_xlsx = os.path.join(out_dir, "E1-2_overlap_jaccard_at10.xlsx")
out_fig_scatter = os.path.join(out_dir, "E1-2_overlap_vs_jaccard_at10.png")


# =========================
# Helpers
# =========================
def _strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1].strip()
    return s

def parse_ids(cell):
    """Parse a cell into an ordered list[str] of ids."""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)) or pd.isna(cell):
        return []
    if isinstance(cell, (list, tuple)):
        return [str(x).strip() for x in cell if str(x).strip()]

    s = str(cell).strip()
    if not s:
        return []

    # Try JSON list
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
    except Exception:
        pass

    # Try Python literal (list/tuple)
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
        try:
            v = ast.literal_eval(s)
            if isinstance(v, (list, tuple)):
                return [str(x).strip() for x in v if str(x).strip()]
        except Exception:
            pass

    s = _strip_quotes(s)

    # Split on common delimiters
    if any(d in s for d in [",", ";", "\n", "\t"]):
        parts = re.split(r"[,\n;\t]+", s)
        return [p.strip() for p in parts if p.strip()]

    return [s]


def compute_e1_2_metrics(ids_chunk, ids_theme, k=10):
    """
    Compute Overlap@k and Jaccard@k using Top-k *sets*.
    Use k_eff = min(k, lenC, lenT) when lists shorter than k.
    """
    ids_chunk = ids_chunk or []
    ids_theme = ids_theme or []

    k_eff = min(k, len(ids_chunk), len(ids_theme))
    if k_eff == 0:
        return {
            "k_eff": 0,
            "IntersectionSize@k": 0,
            "UnionSize@k": 0,
            "Overlap@k": 0.0,
            "Jaccard@k": 0.0,
            "UniqueChunk@k": 0,
            "UniqueTheme@k": 0,
        }

    Ck = set(ids_chunk[:k_eff])
    Tk = set(ids_theme[:k_eff])
    inter = len(Ck & Tk)
    union = len(Ck | Tk)

    overlap = inter / k_eff
    jaccard = inter / union if union else 0.0
    unique_c = len(Ck - Tk)
    unique_t = len(Tk - Ck)

    return {
        "k_eff": k_eff,
        "IntersectionSize@k": inter,
        "UnionSize@k": union,
        "Overlap@k": overlap,
        "Jaccard@k": jaccard,
        "UniqueChunk@k": unique_c,
        "UniqueTheme@k": unique_t,
    }


def pick_key_column(df1, df2):
    """Try to find a common key column to align rows robustly."""
    candidates = ["qid", "query_id", "index", "idx", "question_id", "QID", "Index"]
    for c in candidates:
        if c in df1.columns and c in df2.columns:
            return c
    return None


# =========================
# Load
# =========================
C = pd.read_excel(chunk_path)
T = pd.read_excel(theme_path)

if col_retrieved not in C.columns:
    raise KeyError(f'Chunk file missing "{col_retrieved}" column. Found columns: {list(C.columns)}')
if col_retrieved not in T.columns:
    raise KeyError(f'Theme file missing "{col_retrieved}" column. Found columns: {list(T.columns)}')

key = pick_key_column(C, T)

# Align
if key:
    merged = C[[key]].merge(T[[key]], on=key, how="inner")
    C_aligned = C.set_index(key).loc[merged[key]].reset_index()
    T_aligned = T.set_index(key).loc[merged[key]].reset_index()
    row_id = C_aligned[key].astype(str)
else:
    n = min(len(C), len(T))
    C_aligned = C.iloc[:n].reset_index(drop=True)
    T_aligned = T.iloc[:n].reset_index(drop=True)
    row_id = pd.Series(range(n), name="row").astype(str)

# =========================
# Compute E1-2 per query
# =========================
records = []
for i in range(len(C_aligned)):
    ids_c = parse_ids(C_aligned.loc[i, col_retrieved])
    ids_t = parse_ids(T_aligned.loc[i, col_retrieved])

    m = compute_e1_2_metrics(ids_c, ids_t, k=K)

    rec = {
        "row_id": row_id.iloc[i],
        "k_eff": m["k_eff"],
        f"IntersectionSize@{K}": m["IntersectionSize@k"],
        f"UnionSize@{K}": m["UnionSize@k"],
        f"Overlap@{K}": m["Overlap@k"],
        f"Jaccard@{K}": m["Jaccard@k"],
        f"UniqueChunk@{K}": m["UniqueChunk@k"],
        f"UniqueTheme@{K}": m["UniqueTheme@k"],
    }

    # Optional: carry relevant columns if they exist
    if col_relevant_full in C_aligned.columns:
        rec[f"{col_relevant_full}_chunk"] = C_aligned.loc[i, col_relevant_full]
    if col_partial in C_aligned.columns:
        rec[f"{col_partial}_chunk"] = C_aligned.loc[i, col_partial]
    if col_relevant_full in T_aligned.columns:
        rec[f"{col_relevant_full}_theme"] = T_aligned.loc[i, col_relevant_full]
    if col_partial in T_aligned.columns:
        rec[f"{col_partial}_theme"] = T_aligned.loc[i, col_partial]

    records.append(rec)

res = pd.DataFrame(records)

# =========================
# Summary
# =========================
overlap_col = f"Overlap@{K}"
jaccard_col = f"Jaccard@{K}"
inter_col = f"IntersectionSize@{K}"

summary = pd.DataFrame([{
    "N_queries": len(res),
    "K_target": K,
    "K_eff_min": int(res["k_eff"].min()),
    "K_eff_mean": float(res["k_eff"].mean()),
    "Mean_Overlap@K": float(res[overlap_col].mean()),
    "Std_Overlap@K": float(res[overlap_col].std(ddof=1)),
    "Mean_Jaccard@K": float(res[jaccard_col].mean()),
    "Std_Jaccard@K": float(res[jaccard_col].std(ddof=1)),
    "P(NoOverlap)": float((res[inter_col] == 0).mean()),
}])

print("\n===== E1-2 Summary =====")
print(summary.to_string(index=False))
print("\n===== Per-query head =====")
print(res.head(10).to_string(index=False))

# =========================
# Save Excel (table + summary)
# =========================
with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
    res.to_excel(writer, sheet_name=f"E1-2@{K}_per_query", index=False)
    summary.to_excel(writer, sheet_name="summary", index=False)

print(f"\nSaved results to: {out_xlsx}")

# =========================
# Plot: CDF for Overlap@10 and Jaccard@10
# =========================
import numpy as np

overlap_col = f"Overlap@{K}"
jaccard_col = f"Jaccard@{K}"
inter_col = f"IntersectionSize@{K}"

def plot_cdf(values, xlabel, title, outpath):
    v = pd.Series(values).dropna().astype(float).values
    v = np.sort(v)
    n = len(v)
    if n == 0:
        print(f"[WARN] No data for {title}, skip.")
        return

    y = np.arange(1, n + 1) / n

    plt.figure()
    plt.step(v, y, where="post")
    plt.xlabel(xlabel)
    plt.ylabel("CDF")
    plt.title(title)
    plt.xlim(-0.02, 1.02)
    plt.ylim(0.0, 1.02)
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)

    # 标注：完全不重叠比例（对 Overlap 更有意义；对 Jaccard 同样适用）
    p0 = float((pd.Series(values) == 0).mean())
    plt.text(0.60, 0.15, f"P({xlabel}=0) = {p0:.2f}", transform=plt.gca().transAxes)

    plt.tight_layout()
    plt.savefig(outpath, dpi=300)
    plt.show()
    print(f"Saved CDF figure to: {outpath}")

# 单独两张图
out_fig_cdf_overlap = os.path.join(out_dir, f"E1-2_CDF_overlap_at{K}.png")
out_fig_cdf_jaccard = os.path.join(out_dir, f"E1-2_CDF_jaccard_at{K}.png")

plot_cdf(res[overlap_col], overlap_col,
         f"CDF of {overlap_col} (Chunk-only vs Theme-only)", out_fig_cdf_overlap)

plot_cdf(res[jaccard_col], jaccard_col,
         f"CDF of {jaccard_col} (Chunk-only vs Theme-only)", out_fig_cdf_jaccard)

# =========================
# (Optional) One figure overlaying both CDFs (good for paper)
# =========================
out_fig_cdf_overlay = os.path.join(out_dir, f"E1-2_CDF_overlay_at{K}.png")

ov = np.sort(res[overlap_col].dropna().astype(float).values)
ja = np.sort(res[jaccard_col].dropna().astype(float).values)

plt.figure()
if len(ov) > 0:
    plt.step(ov, np.arange(1, len(ov) + 1) / len(ov), where="post", label=overlap_col)
if len(ja) > 0:
    plt.step(ja, np.arange(1, len(ja) + 1) / len(ja), where="post", label=jaccard_col)

plt.xlabel("Score")
plt.ylabel("CDF")
plt.title(f"CDF Overlay at K={K} (Chunk-only vs Theme-only)")
plt.xlim(-0.02, 1.02)
plt.ylim(0.0, 1.02)
plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
plt.legend()
plt.tight_layout()
plt.savefig(out_fig_cdf_overlay, dpi=300)
plt.show()
print(f"Saved overlay CDF figure to: {out_fig_cdf_overlay}")


overlap_vals = res[overlap_col].astype(float)
jaccard_vals = res[jaccard_col].astype(float)

print("\n===== Chunk vs Theme: Overlap/Jaccard @{} =====".format(K))
print(f"N_queries = {len(res)} | K_target = {K} | K_eff_mean = {res['k_eff'].mean():.2f}")

print(
    f"Overlap@{K}:  mean={overlap_vals.mean():.4f}  median={overlap_vals.median():.4f}  "
    f"std={overlap_vals.std(ddof=1):.4f}  P(=0)={(overlap_vals==0).mean():.3f}"
)
print(
    f"Jaccard@{K}:  mean={jaccard_vals.mean():.4f}  median={jaccard_vals.median():.4f}  "
    f"std={jaccard_vals.std(ddof=1):.4f}  P(=0)={(jaccard_vals==0).mean():.3f}"
)
