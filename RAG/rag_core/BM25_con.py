import os
import pickle as pkl
import re
import unicodedata
from pathlib import Path
from typing import Iterable, List, Optional

import nltk
import pandas as pd
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer
from rank_bm25 import BM25Okapi

try:
    nltk.download("punkt")
    nltk.download("stopwords")
    nltk.download("wordnet")
except Exception as e:
    print(f"Error downloading NLTK data: {e}")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = Path(os.getenv("BM25_SOURCE_XLSX", str(PROJECT_ROOT / "Review_db" / "db_con_theme.xlsx")))
try:
    data = pd.read_excel(file_path)
except FileNotFoundError:
    print(f"The file at path {file_path} was not found.")
    raise
except Exception as e:
    print(f"An error occurred while reading the file: {e}")
    raise

data = data[data[["chunkContent", "theme"]].notna().all(axis=1)]

_STOP_WORDS = set(stopwords.words("english"))
_STEMMER = PorterStemmer()
_LEMMATIZER = WordNetLemmatizer()

_URL_RE = re.compile(r"https?://\S+|www\.\S+", flags=re.I)
_EMAIL_RE = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")
STOP_WHITELIST = {"c", "n", "s"}


def preprocess_text(
    text: str,
    *,
    extra_stopwords: Optional[Iterable[str]] = None,
    keep_digits: bool = True,
    use_lemmatizer: bool = True,
    min_token_len: int = 1,
    filter_pure_numbers: bool = True,
) -> List[str]:
    if not text:
        return []

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)

    if not keep_digits:
        text = re.sub(r"\d+", " ", text)

    text = re.sub(r"[@/-]", " ", text)
    tokens = re.findall(r"[a-z0-9]+", text)

    stop_set = _STOP_WORDS.union(extra_stopwords or set()) - STOP_WHITELIST
    tokens = [t for t in tokens if t not in stop_set]

    if filter_pure_numbers:
        tokens = [t for t in tokens if not t.isdigit()]

    if use_lemmatizer:
        tokens = [_LEMMATIZER.lemmatize(t) for t in tokens]
    else:
        tokens = [_STEMMER.stem(t) for t in tokens]

    tokens = [t for t in tokens if len(t) >= min_token_len]
    return tokens


data["processed_theme"] = data["theme"].apply(preprocess_text)
data["processed_chunkContent"] = data["chunkContent"].apply(preprocess_text)


def build_bm25_model(texts: List[List[str]], model_name: str) -> Optional[BM25Okapi]:
    try:
        bm25 = BM25Okapi(texts)
        with open(model_name, "wb") as f:
            pkl.dump(bm25, f)
        return bm25
    except Exception as e:
        print(f"An error occurred while building or saving the BM25 model: {e}")
        return None


bm25_out_dir = Path(os.getenv("BM25_OUTPUT_DIR", str(PROJECT_ROOT / "RAG" / "faiss_bm25")))
bm25_out_dir.mkdir(parents=True, exist_ok=True)
bm25_chunk = build_bm25_model(data["processed_chunkContent"].tolist(), str(bm25_out_dir / "bm25_chunk.pkl"))
bm25_theme = build_bm25_model(data["processed_theme"].tolist(), str(bm25_out_dir / "bm25_theme.pkl"))

if bm25_chunk and bm25_theme:
    print("BM25 models for chunk and theme have been built and saved successfully.")
else:
    print("There was an issue building one or both BM25 models.")
