import argparse
import json
import logging
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.logger_utils import init_logger
from Reaearch_Idea.code.query_process import gpt_query, query_Gemini


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate hypothesis from extracted inspirations.')
    parser.add_argument('--workspace', default=os.getenv('PIPELINE_WORKSPACE', 'default'))
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', 'o3'))
    return parser.parse_args()


def answer_gpt4(model: str, background: str, motivation: str, insp_pairs_json: str) -> str:
    messages = pmt.template('hypothesis', background=background, motivation=motivation, inspirations=insp_pairs_json)
    if 'gemini' in model.lower():
        return query_Gemini(messages, model=model)
    return gpt_query(messages, model=model)


def main():
    args = parse_args()
    log_dir = PROJECT_DIR / 'test' / args.workspace
    out_dir = log_dir / 'hypothesis'
    out_dir.mkdir(parents=True, exist_ok=True)

    logger = init_logger(log_dir=log_dir, logger_name=__name__, log_filename='hypothesis.log')

    background_path = log_dir / 'background' / f'background_{args.workspace}.txt'
    inspiration_file = log_dir / 'inspiration_ex' / 'inspirations_all.txt'
    if not background_path.exists() or not inspiration_file.exists():
        logger.error('Required input files not found: %s | %s', background_path, inspiration_file)
        return

    motivation = input('请输入研究动机或主题: ').strip()
    if not motivation:
        logger.error('Motivation is empty.')
        return

    background = background_path.read_text(encoding='utf-8')
    content = json.loads(inspiration_file.read_text(encoding='utf-8'))
    if not isinstance(content, list):
        logger.error('Inspiration file must be a JSON list.')
        return

    insp_pairs = []
    for item in content:
        if not isinstance(item, dict):
            continue
        insp = (item.get('inspiration') or '').strip()
        why = (item.get('why_extract') or '').strip()
        mechanism_fragments = item.get('mechanism_fragments') or item.get('Mechanism_fragments') or {}
        if not insp or not why or not mechanism_fragments:
            continue
        insp_pairs.append({
            'inspiration': insp,
            'component': (item.get('Component') or item.get('component') or '').strip(),
            'why_extract': why,
            'mechanism_fragments': mechanism_fragments,
        })

    if not insp_pairs:
        logger.error('No valid inspirations parsed.')
        return

    hypothesis = answer_gpt4(args.model, background, motivation, json.dumps(insp_pairs, ensure_ascii=False, indent=2))
    hypothesis_list = [x.strip() for x in str(hypothesis).splitlines() if x.strip()]
    (out_dir / 'combined_inspirations_hypothesis.txt').write_text(hypothesis, encoding='utf-8')
    (out_dir / 'combined_inspirations_hypothesis.json').write_text(json.dumps(hypothesis_list, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info('Saved hypothesis outputs to %s', out_dir)


if __name__ == '__main__':
    main()
