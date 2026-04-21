from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(
    os.getenv(
        "IDEA_PROMPT_DIR",
        str(Path(__file__).resolve().parents[2] / "prompt_dedup_all"),
    )
)

KEY_TO_FILE = {
    "background": "prompt-background.txt",
    "rewrite": "prompt-rewrite.txt",
    "translate": "prompt-translate.txt",
    "keyword": "prompt-keyword.txt",
    "selection": "prompt-selection.txt",
    "interaction": "prompt-interaction.txt",
    "hypothesis": "prompt-hypothesis.txt",
    "hypothesis_con": "prompt-hypothesis_con.txt",
    "idea_update": "prompt-idea_update.txt",
    "idea_no_inspiration": "prompt-idea_no_inspiration.txt",
    "novelty": "prompt-novelty.txt",
    "quality": "prompt-quality.txt",
    "deduplication": "prompt-idea_no_inspiration.txt",
    "evaluation": "prompt-evaluation.txt",
    "extraction": "prompt-extraction.txt",
    "contradiction": "prompt-contradiction.txt",
}


@lru_cache(maxsize=64)
def _load_prompt(name: str) -> str:
    if not PROMPT_DIR.exists():
        return "{content}"

    mapped = KEY_TO_FILE.get(name)
    if mapped:
        path = PROMPT_DIR / mapped
        if path.exists():
            return path.read_text(encoding="utf-8")

    for path in PROMPT_DIR.glob(f"*{name}*.txt"):
        return path.read_text(encoding="utf-8")

    return "{content}"


def template(name: str, **kwargs):
    text = _load_prompt(name)
    for k, v in kwargs.items():
        text = text.replace("{" + k + "}", str(v))
    return [{"role": "user", "content": text}]
