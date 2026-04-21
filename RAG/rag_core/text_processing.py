import re
from typing import List, Iterable, Optional
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer, WordNetLemmatizer
import unicodedata

_STOP_WORDS = set(stopwords.words("english"))
_STEMMER = PorterStemmer()
_LEMMATIZER = WordNetLemmatizer()

_URL_RE   = re.compile(r"https?://\S+|www\.\S+", flags=re.I)
_EMAIL_RE = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")

CHEM_RE = re.compile(r"[A-Za-z]{1,3}[0-9]{0,3}")  # 简化示例
STOP_WHITELIST = {"c", "n", "s"}  # 元素符号/缩写白名单

def preprocess_text(
    text: str,
    *,
    extra_stopwords: Optional[Iterable[str]] = None,
    keep_digits: bool = True,
    use_lemmatizer: bool = True,
    min_token_len: int = 1,
    filter_pure_numbers: bool = True,   # NEW: 是否过滤纯数字 token（如 "123"）
) -> List[str]:
    if not text:
        return []

    # 0. Unicode → NFKD，去下标/上标
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    # 1. lower-case
    text = text.lower()

    # 2. 去 URL / email
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)

    # 3. 是否保留数字（为 False 则直接从原文中移除所有数字字符）
    if not keep_digits:
        text = re.sub(r"\d+", " ", text)

    # 4. 把连接符替换为空格，方便分段
    text = re.sub(r"[@/-]", " ", text)

    # 5. 正则分词
    tokens = re.findall(r"[a-z0-9α-ωΑ-Ωµ]+", text)

    # 6. 停用词
    stop_set = _STOP_WORDS.union(extra_stopwords or set()) - STOP_WHITELIST
    tokens = [t for t in tokens if t not in stop_set]

    # 6.5 过滤纯数字（独立于 keep_digits；如需保留“123”这类 token，把参数设为 False）
    if filter_pure_numbers:
        tokens = [t for t in tokens if not t.isdigit()]

    # 7. 词干 / 词形
    if use_lemmatizer:
        tokens = [_LEMMATIZER.lemmatize(t) for t in tokens]
    else:
        tokens = [_STEMMER.stem(t) for t in tokens]

    # 8. 长度过滤
    tokens = [t for t in tokens if len(t) >= min_token_len]

    return tokens

