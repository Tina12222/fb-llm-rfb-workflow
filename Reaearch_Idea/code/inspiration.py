import argparse
import json
import logging
import os
import random
import re
from pathlib import Path
from typing import List, Union

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.logger_utils import init_logger
from Reaearch_Idea.code.query_process import gpt_query, query_Gemini

NUM_SELECTION_ROUNDS = 100
BATCH_SIZE = 10
SECOND_BATCH_SIZE = 10
MODEL_DEFAULT = 'o3'


def safe_json_int_list(text) -> List[int]:
    if isinstance(text, list):
        return [int(x) for x in text if str(x).isdigit()]
    if isinstance(text, (bytes, bytearray)):
        text = text.decode('utf-8', errors='ignore')
    cleaned = re.sub(r'^```[\w]*\s*|\s*```$', '', str(text).strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [int(str(x)) for x in data if str(x).isdigit()]
    except json.JSONDecodeError:
        pass
    m = re.search(r'\[([^\]]+)\]', cleaned, flags=re.S)
    target = m.group(0) if m else cleaned
    return [int(s) for s in re.findall(r'\d+', target)]


def safe_json_str_list(text) -> List[Union[str, dict]]:
    if isinstance(text, list):
        return list(text)
    if isinstance(text, (bytes, bytearray)):
        text = text.decode('utf-8', errors='ignore')
    cleaned = re.sub(r'^```[\w]*\s*|\s*```$', '', str(text).strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


def load_dataframe(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, engine='openpyxl')
    for col in ('title', 'abstract'):
        if col not in df.columns:
            raise ValueError(f'Missing required column: {col}')
    df['title'] = df['title'].fillna('').astype(str)
    df['abstract'] = df['abstract'].fillna('').astype(str)
    return df


def answer_selection(model: str, bg: str, candidates: str, allowed_indices: List[int]) -> List[int]:
    msgs = pmt.template('selection', background=bg, abstracts=candidates, allowed_indices=json.dumps(sorted(set(allowed_indices))))
    resp = query_Gemini(msgs, model=model) if 'gemini' in model.lower() else gpt_query(msgs, model=model)
    return safe_json_int_list(resp)


def answer_extraction(model: str, bg: str, candidates: str) -> List[Union[str, dict]]:
    msgs = pmt.template('interaction', background=bg, abstracts=candidates)
    resp = query_Gemini(msgs, model=model) if 'gemini' in model.lower() else gpt_query(msgs, model=model)
    return safe_json_str_list(resp)


def run_selection(df: pd.DataFrame, background: str, model: str, out_dir: Path) -> List[int]:
    selected: List[int] = []
    indices = list(df.index)
    for r in range(NUM_SELECTION_ROUNDS):
        if len(indices) < BATCH_SIZE:
            break
        batch_inds = random.sample(indices, BATCH_SIZE)
        cand_lines = [f'Index: {idx}\nTitle: {df.at[idx, "title"]}\nAbstract: {df.at[idx, "abstract"]}' for idx in batch_inds]
        raw_sel = answer_selection(model, background, '\n\n'.join(cand_lines), allowed_indices=batch_inds)
        kept = sorted({int(x) for x in raw_sel if int(x) in set(batch_inds)})
        (out_dir / f'selected_indices_round{r+1}.txt').write_text('\n'.join(map(str, kept)), encoding='utf-8')
        selected.extend(kept)
        indices = [i for i in indices if i not in batch_inds]
    return sorted(set(selected))


def run_extraction(df: pd.DataFrame, indices: List[int], background: str, model: str, out_dir: Path) -> List[dict]:
    inspirations: List[dict] = []
    pool = indices.copy()
    round_id = 0
    while pool:
        round_id += 1
        batch_inds = random.sample(pool, min(SECOND_BATCH_SIZE, len(pool)))
        cand_str = '\n\n'.join([f'Index: {idx}\nTitle: {df.at[idx, "title"]}\nAbstract: {df.at[idx, "abstract"]}' for idx in batch_inds])
        resp_list = answer_extraction(model, background, cand_str)
        (out_dir / f'inspirations_round{round_id}.txt').write_text(json.dumps(resp_list, ensure_ascii=False, indent=2), encoding='utf-8')
        inspirations.extend(resp_list)
        pool = [i for i in pool if i not in batch_inds]
    return inspirations


def save_results(out_dir: Path, indices: List[int], inspirations: List[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'selected_indices_all.txt').write_text('\n'.join(map(str, indices)), encoding='utf-8')
    payload = json.dumps(inspirations, ensure_ascii=False, indent=2)
    (out_dir / 'inspirations_all.txt').write_text(payload, encoding='utf-8')
    (out_dir / 'inspirations_all.json').write_text(payload, encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract inspirations from abstracts.')
    parser.add_argument('--workspace', default=os.getenv('PIPELINE_WORKSPACE', 'default'))
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', MODEL_DEFAULT))
    parser.add_argument('--excel-path', default=os.getenv('EXCEL_PATH', str(PROJECT_DIR / 'data' / 'abstract_2023.xlsx')))
    args = parser.parse_args()

    log_dir = PROJECT_DIR / 'test' / args.workspace
    out_dir = log_dir / 'inspiration_ex'
    out_dir.mkdir(parents=True, exist_ok=True)
    logger = init_logger(log_dir=out_dir, logger_name=__name__, log_filename='inspiration_extract.log')

    background_path = log_dir / 'background' / f'background_{args.workspace}.txt'
    if not background_path.exists():
        logger.error('Background file missing: %s', background_path)
        return

    background = background_path.read_text(encoding='utf-8').strip()
    df = load_dataframe(Path(args.excel_path))

    selected = run_selection(df, background, args.model, out_dir)
    inspirations = run_extraction(df, selected, background, args.model, out_dir)
    save_results(out_dir, selected, inspirations)
    logger.info('Saved inspiration outputs to %s', out_dir)


if __name__ == '__main__':
    main()
