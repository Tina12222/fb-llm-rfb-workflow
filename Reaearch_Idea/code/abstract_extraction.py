import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.abstract_retrieval import abstract_retrieval
from Reaearch_Idea.code.logger_utils import init_logger
from Reaearch_Idea.code.query_process import gpt_query, preprocess_user_query, query_Gemini
from Reaearch_Idea.code.text_processing import preprocess_text

from FlagEmbedding import BGEM3FlagModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Retrieve abstracts and generate first idea draft.')
    parser.add_argument('--workspace', default=os.getenv('PIPELINE_WORKSPACE', 'default'))
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', 'o3'))
    parser.add_argument('--ref-faiss', default=os.getenv('REF_FAISS_INDEX_PATH', str(PROJECT_DIR / 'data' / 'abstract_embedding_faiss.index')))
    parser.add_argument('--ref-bm25', default=os.getenv('REF_BM25_MODEL_PATH', str(PROJECT_DIR / 'data' / 'ref_bm25_model.pkl')))
    parser.add_argument('--ref-path', default=os.getenv('REF_XLSX_PATH', str(PROJECT_DIR / 'data' / 'abstract_year.xlsx')))
    return parser.parse_args()


def answer_llm(model: str, research_background: str, relevant_abstract: str) -> str:
    messages = pmt.template(
        'first_idea',
        research_background=research_background,
        relevant_abstract=relevant_abstract,
    )
    if 'gemini' in model.lower():
        return query_Gemini(messages, model=model)
    return gpt_query(messages, model=model)


FLAG_MODEL = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True, device='cpu')


def get_embedding(text: str, logger) -> np.ndarray:
    if not text.strip():
        logger.warning('Empty input text, embedding skipped.')
        return np.nan
    try:
        embeddings = FLAG_MODEL.encode([text], batch_size=32, return_sparse=False)['dense_vecs']
        return embeddings
    except Exception as e:
        logger.error('Embedding failed: %s', e)
        return np.nan


def main() -> None:
    args = parse_args()
    work_dir = PROJECT_DIR / 'test' / args.workspace
    idea_dir = work_dir / 'idea'
    idea_dir.mkdir(parents=True, exist_ok=True)

    logger = init_logger(
        log_dir=idea_dir,
        logger_name='abstract_extract_logger',
        log_filename='idea.log',
    )

    ref_path = Path(args.ref_path)
    bg_path = work_dir / 'background' / f'background_{args.workspace}.txt'

    if not ref_path.exists():
        logger.error('Reference file not found: %s', ref_path)
        return
    if not bg_path.exists():
        logger.error('Background file not found: %s', bg_path)
        return

    ref_dataframe = pd.read_excel(ref_path)
    background = bg_path.read_text(encoding='utf-8')

    query = input('请输入您的问题: ').strip()
    if not query:
        logger.error('Empty query, abort.')
        return

    final_query = preprocess_user_query(query)
    tokenized_query = preprocess_text(final_query)

    query_vector = get_embedding(final_query, logger)
    if query_vector is np.nan:
        logger.error('Query embedding generation failed.')
        return
    query_vector = query_vector.reshape(1, -1).astype(np.float32)

    abstract_results = abstract_retrieval(
        tokenized_query,
        query_vector,
        args.ref_bm25,
        args.ref_faiss,
        ref_dataframe,
        final_k=10,
    )
    if not abstract_results:
        logger.warning('No abstracts retrieved.')
        return

    combined_docs = '\n\n---\n\n'.join([ab for (_, ab, _) in abstract_results])
    answer = answer_llm(args.model, background, combined_docs)

    out_file = idea_dir / 'idea_first.txt'
    out_file.write_text(answer, encoding='utf-8')
    logger.info('Idea saved to: %s', out_file)


if __name__ == '__main__':
    main()
