from __future__ import annotations
import argparse
import json
import logging
import re
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', ' ', str(name)).strip()


def make_session(max_retries: int = 3, backoff: float = 0.5) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=max_retries, backoff_factor=backoff, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'], raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.headers.update({'User-Agent': 'crossref-ref-fetcher/1.0'})
    return session


def fetch_references(doi: str, session: requests.Session | None = None) -> list[dict] | None:
    if not doi:
        return None
    session = session or make_session()
    try:
        resp = session.get(f'https://api.crossref.org/works/{doi}', timeout=20)
        if resp.status_code != 200:
            logging.warning('Crossref request failed for DOI=%s status=%s', doi, resp.status_code)
            return None
        return resp.json().get('message', {}).get('reference', [])
    except Exception as e:
        logging.error('Crossref request error for DOI=%s: %s', doi, e)
        return None


def save_references(title_or_doi: str, refs: list[dict], out_dir: Path | str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fpath = out / f"{sanitize_filename(title_or_doi) or 'untitled'}.json"
    fpath.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding='utf-8')
    return fpath


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Fetch references for one DOI from Crossref.')
    p.add_argument('--doi', default='10.1016/j.memsci.2024.122968')
    p.add_argument('--title', default='JMC')
    project_dir = Path(__file__).resolve().parent.parent
    p.add_argument('-o', '--out-dir', default=str(project_dir / 'test' / 'default' / 'ref'))
    p.add_argument('--print', action='store_true')
    p.add_argument('-v', '--verbose', action='store_true')
    return p


if __name__ == '__main__':
    args = _build_argparser().parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
    refs = fetch_references(args.doi)
    if refs is None:
        raise SystemExit(1)
    out = save_references(args.title.strip() or args.doi, refs, args.out_dir)
    logging.info('Saved %d references to %s', len(refs), out)
    if args.print:
        print(json.dumps(refs, ensure_ascii=False, indent=2))
