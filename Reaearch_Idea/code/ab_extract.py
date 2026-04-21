from __future__ import annotations
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
from urllib.parse import quote_plus

import aiofiles
import aiohttp


def build_url(doi: str) -> str:
    encoded = quote_plus(doi)
    return (
        'https://services.readcube.com:443/reader/metadata'
        '?client=web_reader'
        '&client_id=041a907f-445e-4f07-9cd7-d7fcdca7d9b4'
        '&client_version=26.13.0'
        f'&doi={encoded}'
    )


def _load_cookies_from_env() -> dict:
    raw = os.getenv('READCUBE_COOKIES_JSON', '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        logging.warning('Invalid READCUBE_COOKIES_JSON; using empty cookies.')
        return {}


DEFAULT_COOKIES = _load_cookies_from_env()
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*', 'Origin': 'https://www.readcube.com'}


async def fetch_abstract(doi: str, session: aiohttp.ClientSession, headers: Dict[str, str] = DEFAULT_HEADERS, cookies: Dict[str, str] = DEFAULT_COOKIES) -> Optional[str]:
    try:
        async with session.get(build_url(doi), headers=headers, cookies=cookies) as resp:
            if resp.status != 200:
                logging.warning('DOI %s request failed with status=%s', doi, resp.status)
                return None
            data = await resp.json()
            return data.get('meta', {}).get('abstract')
    except Exception:
        logging.exception('Failed to fetch abstract for DOI %s', doi)
        return None


async def save_json(path: str, obj: Union[dict, list]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(out, 'w', encoding='utf-8') as f:
        await f.write(json.dumps(obj, ensure_ascii=False, indent=2))


async def load_processed_dois(path: str) -> Set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    async with aiofiles.open(p, 'r', encoding='utf-8') as f:
        return set(json.loads(await f.read()))


async def process_single(entry: Dict, session: aiohttp.ClientSession, processed: Set[str], data: List[Dict], output_file: str, processed_file: str, lock: asyncio.Lock) -> None:
    doi = entry.get('DOI') or entry.get('doi')
    if not doi or doi in processed or entry.get('abstract'):
        return
    abstract = await fetch_abstract(doi, session)
    if abstract:
        entry['abstract'] = abstract
    processed.add(doi)
    async with lock:
        await save_json(output_file, data)
        await save_json(processed_file, sorted(processed))


async def update_abstracts(data: List[Dict], output_file: str, processed_file: str, concurrency: int = 5) -> List[Dict]:
    processed = await load_processed_dois(processed_file)
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        tasks = []
        for entry in data:
            async def sem_task(ent=entry):
                async with sem:
                    await process_single(ent, session, processed, data, output_file, processed_file, lock)
            tasks.append(asyncio.create_task(sem_task()))
        await asyncio.gather(*tasks)
    return data


async def run_update(input_file: str, output_file: str, processed_file: str, concurrency: int = 5) -> None:
    parsed = json.loads(Path(input_file).read_text(encoding='utf-8'))
    if isinstance(parsed, list):
        data = parsed
    elif isinstance(parsed, dict):
        data = parsed.get('references') or parsed.get('data')
        if data is None:
            raise ValueError("Input JSON dict must contain 'references' or 'data'.")
    else:
        raise ValueError('Unsupported input JSON type.')

    updated = await update_abstracts(data, output_file, processed_file, concurrency)
    if isinstance(parsed, dict):
        key = 'references' if 'references' in parsed else 'data'
        parsed[key] = updated
        await save_json(output_file, parsed)
    else:
        await save_json(output_file, updated)


if __name__ == '__main__':
    import argparse
    project_dir = Path(__file__).resolve().parent.parent
    default_dir = project_dir / 'test' / 'default' / 'ref'

    parser = argparse.ArgumentParser(description='Batch update abstracts for DOI items.')
    parser.add_argument('-i', '--input', default=str(default_dir / 'readcube.json'))
    parser.add_argument('-o', '--output', default=str(default_dir / 'readcube_ab.json'))
    parser.add_argument('-p', '--processed', default=str(default_dir / 'processed_dois.json'))
    parser.add_argument('-c', '--concurrency', type=int, default=10)
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
    asyncio.run(run_update(args.input, args.output, args.processed, args.concurrency))
