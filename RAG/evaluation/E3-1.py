import ast
import os
from collections import Counter
from pathlib import Path
from typing import Any, List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RETRIEVAL_DIR = Path(os.getenv("RAG_RETRIEVAL_DIR", str(PROJECT_ROOT / "RAG" / "retrieval")))

chunk_path = Path(os.getenv("RAG_E3_CHUNK_PATH", str(RETRIEVAL_DIR / "chunk_only" / "chunk_RA.xlsx")))
fusion_path = Path(os.getenv("RAG_E3_FUSION_PATH", str(RETRIEVAL_DIR / "73" / "C_T_Rk.xlsx")))
theme_path = Path(os.getenv("RAG_E3_THEME_PATH", str(RETRIEVAL_DIR / "theme_only" / "theme_RA.xlsx")))
db_path = Path(os.getenv("RAG_E3_DB_PATH", str(PROJECT_ROOT / "Review_db" / "database.xlsx")))

col_retrieved = "id"
col_article = "articleID"
K = 10


def parse_ids(cell: Any) -> List[str]:
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    if isinstance(cell, (list, tuple, set)):
        return [str(x).strip() for x in cell if str(x).strip()]
    if isinstance(cell, str):
        s = cell.strip()
        if not s or s.lower() in {"nan", "none"}:
            return []
        try:
            v = ast.literal_eval(s)
            if isinstance(v, (list, tuple, set)):
                return [str(x).strip() for x in v if str(x).strip()]
        except Exception:
            pass
        for sep in [",", ";", "\n", "\t"]:
            s = s.replace(sep, " ")
        return [p for p in s.split() if p]
    return [str(cell).strip()]


def dedup_topk(ids: List[str], k: int) -> List[str]:
    seen = set()
    out = []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(x)
        if len(out) >= k:
            break
    return out


db = pd.read_excel(db_path)
if col_article not in db.columns:
    raise ValueError(f"database.xlsx missing column '{col_article}', got: {list(db.columns)}")

db.index = db.index.map(lambda x: str(x).strip())
db[col_article] = db[col_article].astype(str).str.strip()


def chunkids_to_articleids(chunk_ids: List[str]) -> List[str]:
    arts = []
    for cid in chunk_ids:
        cid2 = str(cid).strip()
        if cid2 in db.index:
            arts.append(db.at[cid2, col_article])
        else:
            arts.append("UNKNOWN")
    return arts


def calc_doc_metrics(chunk_ids_topk: List[str], k: int):
    arts = chunkids_to_articleids(chunk_ids_topk)
    cnt = Counter(arts)
    unique_docs = len(cnt)
    max_share = (max(cnt.values()) / k) if k and cnt else 0.0
    hhi = sum((c / k) ** 2 for c in cnt.values()) if k and cnt else 0.0
    return unique_docs, unique_docs / k if k else 0.0, max_share, hhi


def run_method(path: Path, method_name: str) -> pd.DataFrame:
    df = pd.read_excel(path).reset_index(drop=True)
    rows = []
    for i, r in df.iterrows():
        top_ids = dedup_topk(parse_ids(r.get(col_retrieved)), K)
        ud, cov, maxs, hhi = calc_doc_metrics(top_ids, K)
        rows.append(
            {
                "method": method_name,
                "row": i,
                "UniqueDocs@K": ud,
                "DocCoverage@K": cov,
                "MaxDocShare@K": maxs,
                "HHI@K": hhi,
                "TopK_articleIDs": chunkids_to_articleids(top_ids),
            }
        )
    return pd.DataFrame(rows)


res = pd.concat(
    [run_method(chunk_path, "chunk"), run_method(theme_path, "theme"), run_method(fusion_path, "fusion")],
    ignore_index=True,
)
summary = res.groupby("method")[["UniqueDocs@K", "DocCoverage@K", "MaxDocShare@K", "HHI@K"]].agg(["mean", "std", "median"])
print("=== Summary ===")
print(summary)

out_detail = Path(os.getenv("RAG_E3_OUT_DETAIL", str(RETRIEVAL_DIR / "analysis_doc_diversity_detail.xlsx")))
out_sum = Path(os.getenv("RAG_E3_OUT_SUM", str(RETRIEVAL_DIR / "analysis_doc_diversity_summary.xlsx")))
out_detail.parent.mkdir(parents=True, exist_ok=True)
res.to_excel(out_detail, index=False)
summary.to_excel(out_sum)
print("\nSaved:")
print(out_detail)
print(out_sum)
