"""Extract theme JSON from chunk text files via LLM."""
from __future__ import annotations

import argparse
import logging
import os
import re
from pathlib import Path
from typing import List

import openai
from dotenv import load_dotenv
from multask import batch_query_openai

BASE_DIR = Path(__file__).resolve().parent
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_base = os.getenv("OPENAI_BASE_URL", None)
os.environ["TF_ENABLE_ONEDNN_OPTS"] = os.getenv("TF_ENABLE_ONEDNN_OPTS", "0")

DEFAULT_MODEL = "gpt-4o"

TEMPLATE = """
You are an assistant for the information distillation. Your task is to distill research questions or analytical themes from the provided text.

- Please provide no more than 5 pieces of research questions or analytical themes from the provided text.
- The research questions or analytical themes should be statements instead of questions or queries.
- Ensure that each pieces of research questions or analytical themes is concise and can stand alone.
- Provide only the rewritten results without unnecessary explanations or additional text beforehand.
- Do not fabricate any information.
- Please output the results in JSON format with the following structure:
```json
{
    "research questions or themes": [
        "theme 1",
        "theme 2",
        "theme 3",
        "theme 4",
        "theme 5"
    ]
}
```
<|user|>Article:\n{}
"""


def _batch_requests(template: str, params_list: List[str], model: str):
    sys_tmpl, user_tmpl = template.split("<|user|>")
    messages = [
        [{"role": "system", "content": sys_tmpl}, {"role": "user", "content": user_tmpl.format(text)}]
        for text in params_list
    ]
    return batch_query_openai(messages=messages, model=model)


def _natural_sort_key(name: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def _process_txt_folder(src_folder: Path, dest_root: Path, model: str):
    txt_files = sorted([p for p in src_folder.iterdir() if p.suffix == ".txt"], key=lambda p: _natural_sort_key(p.name))
    if not txt_files:
        return

    params = [p.read_text(encoding="utf-8", errors="ignore") for p in txt_files]
    results = _batch_requests(TEMPLATE, params, model=model)

    out_dir = dest_root / src_folder.name
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, resp in results:
        (out_dir / f"{txt_files[idx].stem}_theme.txt").write_text(resp, encoding="utf-8")


def process_all_txt_folders(input_root: str | Path, output_root: str | Path, model: str = DEFAULT_MODEL):
    input_root = Path(input_root).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()

    logging.info("Theme extraction input=%s output=%s", input_root, output_root)
    for sub in input_root.iterdir():
        if sub.is_dir():
            logging.info("Processing %s", sub.name)
            _process_txt_folder(sub, output_root, model=model)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch extract research themes")
    parser.add_argument("--input_root", default="./chunks", help="chunks root")
    parser.add_argument("--output_root", default="./themes", help="themes root")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    process_all_txt_folders(
        input_root=(BASE_DIR / args.input_root).resolve(),
        output_root=(BASE_DIR / args.output_root).resolve(),
        model=args.model,
    )


if __name__ == "__main__":
    main()
