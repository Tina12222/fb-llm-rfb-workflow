import json
import os
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sklearn.preprocessing import normalize

PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = Path(os.getenv("REF_FAISS_SOURCE_JSONL", str(PROJECT_ROOT / "Idea" / "ab_year_embedding.json")))
with open(file_path, "r", encoding="utf-8") as f:
    data = pd.DataFrame([json.loads(line) for line in f])
data = data[["abstract_embedding"]].dropna()

index_save_directory = Path(os.getenv("REF_FAISS_OUTPUT_DIR", str(PROJECT_ROOT / "Idea")))
index_save_directory.mkdir(parents=True, exist_ok=True)


def normalize_embeddings(embeddings):
    return normalize(embeddings, axis=1, norm="l2")


def build_faiss_index(embedding_column, original_indices, save_dir: Path, column_name: str):
    embeddings = np.array(list(embedding_column))
    embeddings = normalize_embeddings(embeddings)

    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, str(save_dir / f"{column_name}_faiss.index"))

    mapping = pd.DataFrame({"faiss_index": np.arange(embeddings.shape[0]), "original_index": original_indices})
    mapping.to_csv(save_dir / f"{column_name}_mapping.csv", index=False)


for column_name in ["abstract_embedding"]:
    build_faiss_index(data[column_name], data.index.tolist(), index_save_directory, column_name)

print("FAISS index and mapping files saved.")
