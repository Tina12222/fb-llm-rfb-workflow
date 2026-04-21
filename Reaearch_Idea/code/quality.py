from __future__ import annotations
import argparse
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.query_process import gpt_query, query_Gemini


def _clean_json_text(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text


def _to_text_from_item(item: Dict) -> str:
    val = item.get('ideas')
    if val is None:
        val = item.get('idea')
    if isinstance(val, str):
        return val.strip()
    if val is None:
        return ''
    try:
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return str(val)


def load_items_from_json(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    obj = json.loads(_clean_json_text(path.read_text(encoding='utf-8')))
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ('ideas', 'data', 'items'):
            if isinstance(obj.get(key), list):
                return [x for x in obj[key] if isinstance(x, dict)]
    return []


def append_target_idea(items: List[Dict], target_text: str) -> List[Dict]:
    if target_text.strip():
        items.append({'ideas': target_text.strip(), '_is_target': True})
    return items


def enumerate_ideas_lines(items: List[Dict]) -> Tuple[str, List[Dict]]:
    lines, mapping = [], []
    idx = 0
    for it in items:
        text = _to_text_from_item(it)
        if not text:
            continue
        idx += 1
        lines.append(f'{idx}. {text}')
        mapping.append({'rank_id': idx, 'is_target': bool(it.get('_is_target', False)), 'idea': text})
    return '\n'.join(lines), mapping


def parse_llm_json(raw: str) -> Dict:
    raw = _clean_json_text(raw)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            return {'items': obj}
    except Exception:
        m = re.search(r'(\{.*\}|\[.*\])', raw, flags=re.S)
        if m:
            try:
                obj = json.loads(m.group(1))
                return obj if isinstance(obj, dict) else {'items': obj}
            except Exception:
                pass
    return {'items': [], 'error': 'invalid_json', 'raw': raw}


def answer_ranking(model_name: str, idea_text: str, quality_indicator: str) -> str:
    messages = pmt.template('quality', Idea=idea_text, quality_indicator=quality_indicator)
    if 'gemini' in model_name.lower():
        return query_Gemini(messages, model=model_name)
    return gpt_query(messages, model=model_name)


def main():
    parser = argparse.ArgumentParser(description='Rank ideas by quality indicator.')
    parser.add_argument('--workspace', default=os.getenv('PIPELINE_WORKSPACE', 'default'))
    parser.add_argument('--base-dir', default='test')
    parser.add_argument('--model', default=os.getenv('MODEL_NAME', 'o3'))
    parser.add_argument('--input-json', default='update_ideas4.json')
    parser.add_argument('--quality-indicator', default='Novelty')
    parser.add_argument('--target-idea', default='')
    args = parser.parse_args()

    log_dir = PROJECT_DIR / args.base_dir / args.workspace / 'ref' / 'hypothesis'
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', handlers=[logging.FileHandler(log_dir / 'ranking.log', encoding='utf-8'), logging.StreamHandler()])

    input_json = log_dir / args.input_json
    output_file = log_dir / 'quality' / f"ranking_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    items = append_target_idea(load_items_from_json(input_json), args.target_idea)
    if not items:
        output_file.write_text(json.dumps({'quality_indicator': args.quality_indicator, 'n': 0, 'items': []}, ensure_ascii=False, indent=2), encoding='utf-8')
        return

    numbered_text, mapping = enumerate_ideas_lines(items)
    result = parse_llm_json(answer_ranking(args.model, numbered_text, args.quality_indicator))

    id2target = {m['rank_id']: m['is_target'] for m in mapping}
    for it in result.get('items', []):
        rid = it.get('id') or it.get('rank_id')
        if isinstance(rid, str) and rid.isdigit():
            rid = int(rid)
        if isinstance(rid, int):
            it['is_target'] = bool(id2target.get(rid, False))

    result.setdefault('quality_indicator', args.quality_indicator)
    result.setdefault('n', len(mapping))
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
