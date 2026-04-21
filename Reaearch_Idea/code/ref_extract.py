from __future__ import annotations
import argparse
import hashlib
import json
import logging
import os
import re
import unicodedata
from pathlib import Path

import requests
from requests.exceptions import JSONDecodeError, RequestException


def _load_cookies_from_env() -> dict:
    raw = os.getenv('READCUBE_COOKIES_JSON', '').strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


DEFAULT_COOKIES = _load_cookies_from_env()
DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'}


def build_url(doi: str) -> str:
    return (
        'https://services.readcube.com:443/reader/metadata'
        '?client=web_reader'
        '&client_id=041a907f-445e-4f07-9cd7-d7fcdca7d9b4'
        '&client_version=26.13.0'
        f'&doi={doi}'
    )


def slugify(text: str, max_len: int = 120) -> str:
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'[\\/:*?"<>|]', '_', text)
    text = re.sub(r'\s+', ' ', text).strip().rstrip('.')
    return text[:max_len] if len(text) > max_len else text


def _name_with_doi(title: str, doi: str) -> str:
    h = hashlib.md5(doi.lower().encode('utf-8')).hexdigest()[:8]
    return f'{slugify(title)}_{h}'


def fetch_readcube_refs(doi: str, title: str, out_dir: str, headers: dict | None = None, cookies: dict | None = None, timeout: int = 20, force: bool = False) -> Path | None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    path = out / f"{_name_with_doi(title, doi)}.json"
    if path.exists() and not force:
        return path

    hdr = DEFAULT_HEADERS | (headers or {})
    cks = DEFAULT_COOKIES | (cookies or {})

    data = None
    for _ in range(3):
        try:
            resp = requests.get(build_url(doi), headers=hdr, cookies=cks, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RequestException(f'server {resp.status_code}')
            resp.raise_for_status()
            data = resp.json()
            break
        except JSONDecodeError:
            return None
        except RequestException:
            continue

    if not isinstance(data, dict):
        return None

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch ReadCube reference JSON by DOI')
    parser.add_argument('--doi', default='10.1016/j.memsci.2024.122968')
    parser.add_argument('--title', default='JMC')
    project_dir = Path(__file__).resolve().parent.parent
    parser.add_argument('-o', '--out_dir', default=str(project_dir / 'test' / 'default' / 'ref'))
    parser.add_argument('--force', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    ok = fetch_readcube_refs(args.doi, args.title, args.out_dir, force=args.force)
    raise SystemExit(0 if ok else 1)
