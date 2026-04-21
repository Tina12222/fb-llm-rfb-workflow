import argparse
import json
import os
import re
import socket
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault('TORCH_COMPILE_DISABLE', '1')
os.environ.setdefault('TORCH_DYNAMO_DISABLE', '1')
os.environ.setdefault('HF_DATASETS_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.abstract_retrieval import abstract_retrieval
from Reaearch_Idea.code.logger_utils import init_logger
from Reaearch_Idea.code.query_process import gpt_query, get_keywords, query_Gemini
from Reaearch_Idea.code.text_processing import preprocess_text
from FlagEmbedding.inference.embedder.encoder_only import BGEM3FlagModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Judge novelty and feasibility for each idea in one round.')
    parser.add_argument('-r', '--round', type=int, default=2)
    parser.add_argument('--workspace', default=os.getenv('PIPELINE_WORKSPACE', 'default'))
    parser.add_argument('--base-dir', default='test')
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', 'o3'))
    parser.add_argument('--ref-faiss', default=os.getenv('REF_FAISS_INDEX_PATH', str(PROJECT_DIR / 'data' / 'abstract_embedding_cosip2023.index')))
    parser.add_argument('--ref-bm25', default=os.getenv('REF_BM25_MODEL_PATH', str(PROJECT_DIR / 'data' / 'ab_2023_bm25_model.pkl')))
    parser.add_argument('--ref-xlsx', default=os.getenv('REF_XLSX_PATH', str(PROJECT_DIR / 'data' / 'abstract_2023.xlsx')))
    return parser.parse_args()


def get_embedding(text: str, model: BGEM3FlagModel) -> np.ndarray:
    if not text.strip():
        return np.nan
    return model.encode([text], batch_size=32, return_sparse=False)['dense_vecs']


def load_ideas(path: Path):
    clean = re.sub(r'^json\s*', '', path.read_text(encoding='utf-8'))
    return json.loads(clean)


def answer_judgment(model_name: str, idea: str, reason: str, abstracts: str) -> str:
    messages = pmt.template('novelty', IDEA=idea, reason=reason, similar_abstract=abstracts)
    if 'gemini' in model_name.lower():
        return query_Gemini(messages, model=model_name)
    return gpt_query(messages, model=model_name)


def process_idea(item: dict, model_name: str, embed_model: BGEM3FlagModel, ref_dataframe: pd.DataFrame, ref_bm25: str, ref_faiss: str) -> dict:
    idea = item.get('hypothesis', '')
    reason_dict = {k: v for k, v in item.items() if k not in ('hypothesis', 'inspiration_index')}

    vec = get_embedding(idea, embed_model)
    if isinstance(vec, float) and np.isnan(vec):
        hits = []
    else:
        vec = vec.reshape(1, -1)
        keywords = get_keywords(idea)
        tokens_nested = [preprocess_text(kw) for kw in keywords]
        tokenized = list(dict.fromkeys(t for sub in tokens_nested for t in sub))
        hits = abstract_retrieval(tokenized, vec, ref_bm25, ref_faiss, ref_dataframe, final_k=20)

    abstracts = [ab for _, ab, _ in hits]
    raw = answer_judgment(model_name, idea, json.dumps(reason_dict, ensure_ascii=False, indent=2), '\n\n---\n\n'.join(abstracts))

    sanitized = raw.replace('```json', '').replace('```', '').strip()
    m = re.search(r'\[.*\]|\{.*\}', sanitized, flags=re.S)
    json_text = m.group(0) if m else sanitized
    try:
        parsed = json.loads(json_text)
        assessment = parsed[0] if isinstance(parsed, list) else parsed
    except Exception:
        assessment = {'Feasibility assessment': None, 'Novelty assessment': None, 'Improvement suggestions': None}

    return {'hypothesis': idea, 'reason': reason_dict, 'abstracts': abstracts, **assessment}


def main():
    args = parse_args()
    log_dir = PROJECT_DIR / args.base_dir / args.workspace / 'ref' / 'hypothesis'
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = init_logger(log_dir=log_dir, logger_name='novelty_logger', log_filename='novelty.log')

    idea_file = log_dir / f'update_ideas{args.round}.json'
    output_file = log_dir / f'novelty_judgement_results_round{args.round}.json'
    if not idea_file.exists():
        logger.error('Idea file not found: %s', idea_file)
        return

    ref_xlsx = Path(args.ref_xlsx)
    if not ref_xlsx.exists():
        logger.error('Reference xlsx not found: %s', ref_xlsx)
        return

    ref_dataframe = pd.read_excel(ref_xlsx)
    socket.setdefaulttimeout(60)
    embed_model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, device='cpu', trust_remote_code=True)

    ideas = load_ideas(idea_file)
    results = []
    for item in ideas:
        try:
            results.append(process_idea(item, args.model, embed_model, ref_dataframe, str(args.ref_bm25), str(args.ref_faiss)))
        except Exception as e:
            logger.error('Failed to process one idea: %s', e, exc_info=True)

    output_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info('Saved novelty results to: %s', output_file)


if __name__ == '__main__':
    main()
