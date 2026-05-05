from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from FlagEmbedding import BGEM3FlagModel

from .config import BASE


FLAG_MODEL = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True, device="cpu")


def get_embedding(text: str, model: BGEM3FlagModel = FLAG_MODEL) -> np.ndarray | float:
    """Return a single dense embedding vector for input text."""
    if not isinstance(text, str) or not text.strip():
        return np.nan
    try:
        result = model.encode([text], batch_size=1, return_sparse=False)
        dense = result["dense_vecs"][0]
        return np.asarray(dense, dtype=np.float32)
    except Exception as e:
        print(f"Error generating embedding for text: {text[:30]}... Error: {e}")
        return np.nan


def process_and_embed(data: pd.DataFrame, field_names: List[str]) -> Dict[str, List[np.ndarray | float]]:
    """Compute embeddings for each requested field with dedup caching."""
    vector_cache: Dict[str, np.ndarray | float] = {}
    embeddings: Dict[str, List[np.ndarray | float]] = {field: [] for field in field_names}

    for _, row in data.iterrows():
        for field in field_names:
            if field in row and pd.notna(row[field]):
                content = str(row[field])
                if content not in vector_cache:
                    vector_cache[content] = get_embedding(content)
                embeddings[field].append(vector_cache[content])
            else:
                embeddings[field].append(np.nan)
    return embeddings


def run_embedding_pipeline(
    input_excel: Path | None = None,
    output_json: Path | None = None,
    output_excel: Path | None = None,
) -> None:
    """
    Generate embeddings for dataset fields.

    All default paths are relative to repository root (BASE).
    """
    input_excel = input_excel or (BASE / "db" / "merged_database_rag.xlsx")
    output_json = output_json or (BASE / "db" / "merged_database_rag.json")
    output_excel = output_excel or (BASE / "db" / "merged_database_rag.xlsx")

    data = pd.read_excel(input_excel)
    field_names = ["articleID", "chunkContent", "theme", "theme1", "theme2", "theme3", "theme4", "theme5"]
    data = data[field_names].fillna("")

    embedding_results = process_and_embed(data, field_names)
    for field, values in embedding_results.items():
        data[f"{field}_embedding"] = values

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_excel.parent.mkdir(parents=True, exist_ok=True)
    data.to_json(output_json, orient="records", lines=True, force_ascii=False)
    data.to_excel(output_excel, index=False)

    print(f"Embeddings saved to: {output_json}")
    print(f"Embeddings saved to: {output_excel}")


if __name__ == "__main__":
    run_embedding_pipeline()
