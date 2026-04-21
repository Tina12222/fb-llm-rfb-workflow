import os
import pickle as pkl
import re
import unicodedata
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer
from rank_bm25 import BM25Okapi

PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = Path(
    os.getenv(
        "REF_BM25_SOURCE_XLSX",
        str(PROJECT_ROOT / "Reference" / "dedup_ref_abstract_del.xlsx"),
    )
)
data = pd.read_excel(file_path)
data = data[data[["abstract"]].notna().all(axis=1)]

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
    if use_lemmatizer:
        tokens = [_LEMMATIZER.lemmatize(t) for t in tokens]
    else:
        tokens = [_STEMMER.stem(t) for t in tokens]
    return [t for t in tokens if len(t) >= min_token_len]


data["processed_abstract"] = data["abstract"].apply(preprocess_text)


def build_bm25_model(texts: List[List[str]], model_name: str) -> BM25Okapi:
    bm25 = BM25Okapi(texts)
    with open(model_name, "wb") as f:
        pkl.dump(bm25, f)
    return bm25


out_path = Path(os.getenv("REF_BM25_OUTPUT", str(PROJECT_ROOT / "RAG" / "faiss_bm25" / "ref_bm25_model.pkl")))
out_path.parent.mkdir(parents=True, exist_ok=True)
build_bm25_model(data["processed_abstract"].tolist(), str(out_path))
print("BM25 model for abstracts built and saved successfully.")
