"""Extract statement JSON from chunk text files via LLM."""
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

TEMPLATE = """
You are an assistant for the information extraction. Your task is to extract key domain knowledge from the provided text.
- Please provide no more than 5 pieces of domain knowledge from the provided text.
- Ensure each pieces of domain knowledge contains a clear subject for easy retrieval.
- Do not fabricate any information.
- Ensure that each pieces of domain knowledge is concise and can stand alone for independent searching.
- Provide only the rewritten results without unnecessary explanations or additional text beforehand.
- Please output the results in JSON format with the following structure:

```json
{
    "descriptions": [
        "domain knowledge 1",
        "domain knowledge 2",
        "domain knowledge 3",
        "domain knowledge 4",
        "domain knowledge 5"
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
        (out_dir / f"{txt_files[idx].stem}_result.txt").write_text(resp, encoding="utf-8")


def process_all_txt_folders(input_root: str | Path, output_root: str | Path, model: str = "gpt-4o"):
    input_root = Path(input_root).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()

    logging.info("Statement extraction input=%s output=%s", input_root, output_root)
    for sub in input_root.iterdir():
        if sub.is_dir():
            logging.info("Processing %s", sub.name)
            _process_txt_folder(sub, output_root, model=model)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch extract statements")
    parser.add_argument("--input_root", default="./chunks", help="chunks root")
    parser.add_argument("--output_root", default="./statements", help="statements root")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    process_all_txt_folders(
        input_root=(BASE_DIR / args.input_root).resolve(),
        output_root=(BASE_DIR / args.output_root).resolve(),
        model=args.model,
    )


if __name__ == "__main__":
    main()
