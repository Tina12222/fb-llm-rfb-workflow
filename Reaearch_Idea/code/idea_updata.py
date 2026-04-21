import argparse
import json
import logging
import os
import re
from math import ceil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.logger_utils import init_logger
from Reaearch_Idea.code.query_process import gpt_query, query_Gemini


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate next-round ideas from previous assessments.')
    parser.add_argument('-r', '--round', type=int, default=2)
    parser.add_argument('--workspace', default=os.getenv('PIPELINE_WORKSPACE', 'default'))
    parser.add_argument('--base-dir', default='test')
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', 'o3'))
    parser.add_argument('--batch-num', type=int, default=2)
    return parser.parse_args()


def call_llm(model: str, background: str, motivation: str, idea_batch: list[dict]) -> str:
    idea_packs_str = json.dumps(idea_batch, ensure_ascii=False, separators=(',', ':'))
    messages = pmt.template('idea_update', background=background, motivation=motivation, idea_packs=idea_packs_str)
    if 'gemini' in model.lower():
        return query_Gemini(messages, model=model)
    return gpt_query(messages, model=model)


def try_parse_json(text: str):
    try:
        return json.loads(text), None
    except Exception as e:
        return None, e


def extract_first_json_snippet(text: str):
    for pat in [r'(\[.*\])', r'(\[.*?\])', r'(\{.*\})', r'(\{.*?\})']:
        for m in re.finditer(pat, text, flags=re.S):
            parsed, _ = try_parse_json(m.group(1))
            if parsed is not None:
                return parsed, None
    return None, 'no_json_found'


def main():
    args = parse_args()
    log_dir = PROJECT_DIR / args.base_dir / args.workspace / 'ref'
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = init_logger(log_dir=log_dir, logger_name='idea_updater', log_filename='idea_update.log')

    background_path = log_dir / 'background' / f'background_{args.workspace}.txt'
    input_path = log_dir / 'hypothesis' / f'novelty_judgement_results_round{args.round}.json'
    if not background_path.exists() or not input_path.exists():
        logger.error('Required inputs not found: %s | %s', background_path, input_path)
        return

    research_background = background_path.read_text(encoding='utf-8').strip()
    idea_packs_json = json.loads(input_path.read_text(encoding='utf-8'))
    if not isinstance(idea_packs_json, list):
        logger.error('Input idea pack must be a list.')
        return

    motivation = input('请输入研究动机或主题: ').strip()
    total = len(idea_packs_json)
    batch_size = ceil(total / max(1, args.batch_num))
    all_new_ideas = []

    for b_idx in range(args.batch_num):
        start = b_idx * batch_size
        end = min((b_idx + 1) * batch_size, total)
        if start >= end:
            break
        batch = idea_packs_json[start:end]
        raw_output = call_llm(args.model, research_background, motivation, batch)

        clean_output = re.sub(r'^```(?:json)?\s*', '', (raw_output or '').strip(), flags=re.I)
        clean_output = re.sub(r'\s*```$', '', clean_output)

        parsed_output, _ = try_parse_json(clean_output)
        if parsed_output is None:
            parsed_output, _ = extract_first_json_snippet(clean_output)

        if parsed_output is None:
            all_new_ideas.append({'source_round': args.round + 1, 'source_batch': b_idx + 1, 'raw_output': clean_output})
        elif isinstance(parsed_output, list):
            all_new_ideas.extend(parsed_output)
        else:
            all_new_ideas.append(parsed_output)

    out_path = input_path.parent / f'update_ideas{args.round + 1}.json'
    out_path.write_text(json.dumps(all_new_ideas, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info('Saved next round ideas to %s', out_path)


if __name__ == '__main__':
    main()
