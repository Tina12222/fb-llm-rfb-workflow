from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache

PROMPT_DIR = Path(os.getenv('RAG_PROMPT_DIR', str(Path(__file__).resolve().parents[2] / 'prompt_dedup_all')))

KEY_TO_FILE = {
    'answer': 'prompt-answer.txt',
    'background': 'prompt-background.txt',
    'rewrite': 'prompt-rewrite.txt',
    'translate': 'prompt-translate.txt',
    'keyword': 'prompt-keyword.txt',
    'selection': 'prompt-selection.txt',
    'interaction': 'prompt-interaction.txt',
    'hypothesis': 'prompt-hypothesis.txt',
    'hypothesis_con': 'prompt-hypothesis_con.txt',
    'idea_update': 'prompt-idea_update.txt',
    'idea_no_inspiration': 'prompt-idea_no_inspiration.txt',
    'novelty': 'prompt-novelty.txt',
    'quality': 'prompt-quality.txt',
    'evaluation': 'prompt-evaluation.txt',
    'extraction': 'prompt-extraction.txt',
    'contradiction': 'prompt-contradiction.txt',
}


@lru_cache(maxsize=64)
def _load_prompt(name: str) -> str:
    if not PROMPT_DIR.exists():
        return '{content}'
    fname = KEY_TO_FILE.get(name)
    if fname:
        p = PROMPT_DIR / fname
        if p.exists():
            return p.read_text(encoding='utf-8')
    # fallback fuzzy match
    for p in PROMPT_DIR.glob(f'*{name}*.txt'):
        return p.read_text(encoding='utf-8')
    return '{content}'


def template(name: str, **kwargs):
    text = _load_prompt(name)
    for k, v in kwargs.items():
        text = text.replace('{' + k + '}', str(v))
    return [{'role': 'user', 'content': text}]
