import ast
import os
from pathlib import Path
from typing import Any, List, Set

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RETRIEVAL_DIR = Path(os.getenv("RAG_RETRIEVAL_DIR", str(PROJECT_ROOT / "RAG" / "retrieval")))

chunk_path = Path(os.getenv("RAG_REL_CHUNK_PATH", str(RETRIEVAL_DIR / "chunk_only" / "chunk_RA.xlsx")))
fusion_path = Path(os.getenv("RAG_REL_FUSION_PATH", str(RETRIEVAL_DIR / "73" / "C_T_Rk.xlsx")))
theme_path = Path(os.getenv("RAG_REL_THEME_PATH", str(RETRIEVAL_DIR / "theme_only" / "theme_RA.xlsx")))

col_relevant_full = "S"
col_partial = "part"
col_retrieved = "id"
K = 10


def normalize_id(x: Any) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    return str(x).replace("\u200b", "").replace("\ufeff", "").strip()


_SPLIT_SEPS = [",", "，", ";", "；", "、", "|", "/", "\\", "\n", "\t", "\r"]


def parse_ids(cell: Any) -> List[str]:
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    if isinstance(cell, (list, tuple, set)):
        return [x for x in (normalize_id(v) for v in cell) if x]
    if isinstance(cell, str):
        s = cell.strip()
        if not s or s.lower() in {"nan", "none"}:
            return []
        try:
            v = ast.literal_eval(s)
            if isinstance(v, (list, tuple, set)):
                return [x for x in (normalize_id(i) for i in v) if x]
        except Exception:
            pass
        for sep in _SPLIT_SEPS:
            s = s.replace(sep, " ")
        return [normalize_id(p) for p in s.split() if normalize_id(p)]
    s = normalize_id(cell)
    return [s] if s else []


def topk_list(cell: Any, k: int) -> List[str]:
    ids = parse_ids(cell)
    seen = set()
    out = []
    for x in ids:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out[:k]


def topk_set(cell: Any, k: int) -> Set[str]:
    return set(topk_list(cell, k))


df_c = pd.read_excel(chunk_path)
df_f = pd.read_excel(fusion_path)
df_t = pd.read_excel(theme_path)

possible_keys = ["query_id", "qid", "index", "question", "Query", "Q", "query", "查询"]
common_keys = [k for k in possible_keys if k in df_c.columns and k in df_f.columns and k in df_t.columns]

if common_keys:
    key = common_keys[0]
    df = df_c.merge(df_f, on=key, suffixes=("_chunk", "_fusion")).merge(df_t, on=key, suffixes=("", "_theme"))
else:
    df_c = df_c.reset_index(drop=False).rename(columns={"index": "_row"})
    df_f = df_f.reset_index(drop=False).rename(columns={"index": "_row"})
    df_t = df_t.reset_index(drop=False).rename(columns={"index": "_row"})
    df = df_c.merge(df_f, on="_row", suffixes=("_chunk", "_fusion")).merge(df_t, on="_row", suffixes=("", "_theme"))

col_c_ret = f"{col_retrieved}_chunk"
col_f_ret = f"{col_retrieved}_fusion"
theme_candidates = [f"{col_retrieved}_theme", col_retrieved, f"{col_retrieved}.1", f"{col_retrieved}_y"]
col_t_ret = next((c for c in theme_candidates if c in df.columns), None)
if col_t_ret is None:
    for c in df.columns:
        if col_retrieved in str(c).lower() and "theme" in str(c).lower():
            col_t_ret = c
            break
if col_t_ret is None:
    raise ValueError("Cannot find theme retrieved-id column.")

col_full = f"{col_relevant_full}_chunk" if f"{col_relevant_full}_chunk" in df.columns else col_relevant_full
col_part = f"{col_partial}_chunk" if f"{col_partial}_chunk" in df.columns else col_partial

rows = []
debug_zero_hits = []

for _, r in df.iterrows():
    c_list = topk_list(r.get(col_c_ret), K)
    t_list = topk_list(r.get(col_t_ret), K)
    f_list = topk_list(r.get(col_f_ret), K)
    c_set = set(c_list)
    t_set = set(t_list)
    f_set = set(f_list)
    rel_set = set(parse_ids(r.get(col_full))) | set(parse_ids(r.get(col_part)))

    hit_c = len(c_set & rel_set)
    hit_t = len(t_set & rel_set)
    hit_f = len(f_set & rel_set)

    out = {
        "K": K,
        "Hit_chunk": hit_c,
        "Hit_theme": hit_t,
        "Hit_fusion": hit_f,
        "DeltaHit_F_minus_C": hit_f - hit_c,
        "DeltaHit_F_minus_T": hit_f - hit_t,
    }
    if common_keys:
        out[common_keys[0]] = r.get(common_keys[0])
    if "_row" in df.columns:
        out["_row"] = r.get("_row")
    if hit_c == 0 and rel_set:
        debug_zero_hits.append(
            {
                **({common_keys[0]: r.get(common_keys[0])} if common_keys else {}),
                **({"_row": r.get("_row")} if "_row" in df.columns else {}),
                "C_topk": c_list,
                "R_sample": list(rel_set)[:20],
            }
        )
    rows.append(out)

res = pd.DataFrame(rows)
summary = {
    "K": K,
    "mean_Hit_chunk": res["Hit_chunk"].mean(),
    "mean_Hit_theme": res["Hit_theme"].mean(),
    "mean_Hit_fusion": res["Hit_fusion"].mean(),
    "pct_F_gt_C": (res["DeltaHit_F_minus_C"] > 0).mean(),
    "pct_F_eq_C": (res["DeltaHit_F_minus_C"] == 0).mean(),
    "pct_F_lt_C": (res["DeltaHit_F_minus_C"] < 0).mean(),
    "mean_DeltaHit_F_minus_C": res["DeltaHit_F_minus_C"].mean(),
    "median_DeltaHit_F_minus_C": res["DeltaHit_F_minus_C"].median(),
    "pct_F_gt_T": (res["DeltaHit_F_minus_T"] > 0).mean(),
    "pct_F_eq_T": (res["DeltaHit_F_minus_T"] == 0).mean(),
    "pct_F_lt_T": (res["DeltaHit_F_minus_T"] < 0).mean(),
    "mean_DeltaHit_F_minus_T": res["DeltaHit_F_minus_T"].mean(),
    "median_DeltaHit_F_minus_T": res["DeltaHit_F_minus_T"].median(),
}

print("=== Summary (Hit@k) ===")
for k, v in summary.items():
    print(f"{k}: {v}")

out_path = Path(os.getenv("RAG_REL_OUT_PATH", str(RETRIEVAL_DIR / "analysis_hit_at_k.xlsx")))
out_path.parent.mkdir(parents=True, exist_ok=True)
res.to_excel(out_path, index=False)
print(f"\nSaved per-query details to: {out_path}")

if debug_zero_hits:
    dbg_path = Path(os.getenv("RAG_REL_DEBUG_PATH", str(RETRIEVAL_DIR / "debug_hit_zero.xlsx")))
    pd.DataFrame(debug_zero_hits).to_excel(dbg_path, index=False)
    print(f"Saved debug rows (Hit_chunk=0) to: {dbg_path}")
