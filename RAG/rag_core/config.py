from __future__ import annotations
import os
from pathlib import Path

# Prefer env var; fallback to workspace root inferred from this file.
_WORKSPACE = Path(__file__).resolve().parents[2]  # D:/CODE
BASE = Path(os.getenv('RAG_BASE', str(_WORKSPACE)))

# Retrieval / index
FAISS = Path(os.getenv('RAG_FAISS_DIR', str(BASE / '.rag' / 'faiss_index' / 'connected')))
BM25 = Path(os.getenv('RAG_BM25_DIR', str(BASE / '.rag' / 'BM25_model' / 'connected')))

CHUNK_FAISS = str(Path(os.getenv('CHUNK_FAISS', str(FAISS / 'chunkContent_embedding_faiss.index'))))
THEME_FAISS = str(Path(os.getenv('THEME_FAISS', str(FAISS / 'theme_embedding_faiss.index'))))
CHUNK_BM25 = str(Path(os.getenv('CHUNK_BM25', str(BM25 / 'bm25_chunk.pkl'))))
THEME_BM25 = str(Path(os.getenv('THEME_BM25', str(BM25 / 'bm25_theme.pkl'))))
METADATA = Path(os.getenv('RAG_METADATA', str(BASE / 'db' / 'review_doi_metadata.json')))

# Scoring
SCORE_DIR = Path(os.getenv('RAG_SCORE_DIR', str(BASE / '.rag' / 'Scoring function')))
REF_FAISS = str(Path(os.getenv('REF_FAISS', str(SCORE_DIR / 'abstract_embedding_faiss.index'))))
REF_BM25 = str(Path(os.getenv('REF_BM25', str(SCORE_DIR / 'ref_bm25_model.pkl'))))

# Excel datasets
PROJECT = Path(os.getenv('RAG_PROJECT_ROOT', str(BASE / 'Project_root')))
REF_XLSX = Path(os.getenv('REF_XLSX', str(PROJECT / 'Reference' / 'dedup_ref_abstract_del.xlsx')))
DB_XLSX = Path(os.getenv('DB_XLSX', str(PROJECT / 'Review_db' / 'db_change_chunkid_updated.xlsx')))


def summarize_paths() -> dict:
    return {
        'BASE': str(BASE),
        'CHUNK_FAISS': CHUNK_FAISS,
        'THEME_FAISS': THEME_FAISS,
        'CHUNK_BM25': CHUNK_BM25,
        'THEME_BM25': THEME_BM25,
        'REF_FAISS': REF_FAISS,
        'REF_BM25': REF_BM25,
        'DB_XLSX': str(DB_XLSX),
        'REF_XLSX': str(REF_XLSX),
    }
