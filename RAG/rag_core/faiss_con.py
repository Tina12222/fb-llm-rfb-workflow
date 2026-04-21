import json
import os
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sklearn.preprocessing import normalize

PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = Path(
    os.getenv(
        "FAISS_SOURCE_JSONL",
        str(PROJECT_ROOT / "Review_db" / "co_theme_embedding.json"),
    )
)
with open(file_path, "r", encoding="utf-8") as f:
    data = pd.DataFrame([json.loads(line) for line in f])

columns_to_index = ["chunkContent_embedding", "theme_embedding"]
index_save_directory = Path(
    os.getenv("FAISS_OUTPUT_DIR", str(PROJECT_ROOT / ".rag" / "faiss_index" / "connected"))
)
index_save_directory.mkdir(parents=True, exist_ok=True)


def normalize_embeddings(embeddings):
    return normalize(embeddings, axis=1, norm="l2")


def build_faiss_index(embedding_column, original_indices, save_dir: Path, column_name: str):
    valid_embeddings = []
    valid_indices = []

    expected_length = None
    for emb in embedding_column:
        if emb and len(emb) > 0:
            expected_length = len(emb)
            break
    if expected_length is None:
        raise ValueError("No valid embedding data found.")

    for idx, emb in zip(original_indices, embedding_column):
        if emb is not None and len(emb) == expected_length:
            valid_embeddings.append(emb)
            valid_indices.append(idx)
        else:
            print(f"Skip invalid embedding at row={idx}")

    embeddings_array = normalize_embeddings(np.array(valid_embeddings))
    index = faiss.IndexFlatL2(embeddings_array.shape[1])
    index.add(embeddings_array)
    faiss.write_index(index, str(save_dir / f"{column_name}_faiss.index"))

    mapping_df = pd.DataFrame({"faiss_index": np.arange(len(valid_indices)), "original_index": valid_indices})
    mapping_df.to_csv(save_dir / f"{column_name}_mapping.csv", index=False)


for column_name in columns_to_index:
    build_faiss_index(data[column_name], data.index.tolist(), index_save_directory, column_name)

print("FAISS indices and mapping files saved.")
