import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault('HF_DATASETS_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.logger_utils import init_logger
from Reaearch_Idea.code.query_process import gpt_query, get_keywords, preprocess_user_query, query_Gemini
from Reaearch_Idea.code.review_retrieval import review_retrieval
from Reaearch_Idea.code.text_processing import preprocess_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate background from retrieved review chunks.')
    parser.add_argument('--workspace', default=os.getenv('PIPELINE_WORKSPACE', 'default'))
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', 'o3'))
    parser.add_argument('--db-path', default=os.getenv('DB_PATH', str(PROJECT_DIR / 'data' / 'db_change_chunkid_updated.xlsx')))
    parser.add_argument('--chunk-faiss', default=os.getenv('CHUNK_FAISS_INDEX_PATH', str(PROJECT_DIR.parent / 'RAG' / 'faiss_bm25' / 'chunkContent_embedding_faiss.index')))
    parser.add_argument('--theme-faiss', default=os.getenv('THEME_FAISS_INDEX_PATH', str(PROJECT_DIR.parent / 'RAG' / 'faiss_bm25' / 'theme_embedding_faiss.index')))
    parser.add_argument('--chunk-bm25', default=os.getenv('CHUNK_BM25_PATH', str(PROJECT_DIR.parent / 'RAG' / 'faiss_bm25' / 'bm25_chunk.pkl')))
    parser.add_argument('--theme-bm25', default=os.getenv('THEME_BM25_PATH', str(PROJECT_DIR.parent / 'RAG' / 'faiss_bm25' / 'bm25_theme.pkl')))
    parser.add_argument('--top-k', type=int, default=15)
    parser.add_argument('--dry-run', action='store_true', help='Validate imports and paths only.')
    return parser.parse_args()


def build_logger(workspace: str):
    background_dir = PROJECT_DIR / 'test' / workspace / 'background'
    logger = init_logger(
        log_dir=background_dir,
        logger_name='main_logger',
        log_filename='bk_retrieval.log',
    )
    return logger, background_dir


FLAG_MODEL = None


def get_flag_model():
    global FLAG_MODEL
    if FLAG_MODEL is None:
        from FlagEmbedding import BGEM3FlagModel

        FLAG_MODEL = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True, device='cpu')
    return FLAG_MODEL


def get_embedding(text: str, logger) -> np.ndarray:
    if not text.strip():
        logger.warning('Empty input text, embedding skipped.')
        return np.nan
    try:
        embeddings = get_flag_model().encode([text], batch_size=32, return_sparse=False)['dense_vecs']
        return embeddings
    except Exception as e:
        logger.error('Embedding failed: %s', e)
        return np.nan


def answer_llm(model: str, final_top_k_documents: str, topic: str) -> str:
    messages = pmt.template(
        'background',
        final_top_k_documents=final_top_k_documents,
        topic=topic,
    )
    if 'gemini' in model.lower():
        return query_Gemini(messages, model=model)
    return gpt_query(messages, model=model)


def main() -> None:
    args = parse_args()
    logger, background_dir = build_logger(args.workspace)

    if args.dry_run:
        print('[dry-run] background checks')
        print(f'db_path={args.db_path}')
        print(f'chunk_faiss={args.chunk_faiss}')
        print(f'theme_faiss={args.theme_faiss}')
        print(f'chunk_bm25={args.chunk_bm25}')
        print(f'theme_bm25={args.theme_bm25}')
        return

    df_path = Path(args.db_path)
    if not df_path.exists():
        logger.error('Database file not found: %s', df_path)
        return

    dataframe = pd.read_excel(df_path, engine='openpyxl')
    query = input('请输入您的问题: ').strip()
    if not query:
        logger.error('Empty query, abort.')
        return

    final_query = preprocess_user_query(query)
    keywords = get_keywords(final_query)
    tokens_nested = [preprocess_text(kw) for kw in keywords]
    tokenized = list(dict.fromkeys(t for sub in tokens_nested for t in sub))

    query_vector = get_embedding(final_query, logger)
    if query_vector is np.nan:
        logger.error('Query embedding generation failed.')
        return
    query_vector = query_vector.reshape(1, -1).astype(np.float32)

    review_data = review_retrieval(
        tokenized,
        query_vector,
        dataframe,
        args.chunk_faiss,
        args.theme_faiss,
        args.chunk_bm25,
        args.theme_bm25,
        top_k=args.top_k,
    )

    _, _, doc_contents, _, _ = review_data
    if not doc_contents:
        logger.warning('No review content retrieved.')
        return

    combined_docs = '\n\n---\n\n'.join(doc_contents)
    answer = answer_llm(args.model, combined_docs, query)

    out_file = background_dir / f'background_{args.workspace}.txt'
    out_file.write_text(answer, encoding='utf-8')
    logger.info('Background saved to: %s', out_file)


if __name__ == '__main__':
    main()
