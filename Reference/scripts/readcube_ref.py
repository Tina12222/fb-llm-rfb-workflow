from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Iterable, Optional

import requests
from requests.exceptions import RequestException


def _load_cookies_from_env() -> dict:
    raw = os.getenv("READCUBE_COOKIES_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        logging.warning("Invalid READCUBE_COOKIES_JSON, use empty cookies.")
        return {}


DEFAULT_COOKIES = _load_cookies_from_env()
DEFAULT_HEADERS = {
    "Accept": "*/*",
    "Origin": "https://www.readcube.com",
    "Referer": "https://www.readcube.com/",
    "User-Agent": "Mozilla/5.0",
}


def build_url(doi: str) -> str:
    return (
        "https://services.readcube.com:443/reader/metadata"
        "?client=web_reader"
        "&client_id=041a907f-445e-4f07-9cd7-d7fcdca7d9b4"
        "&client_version=26.13.0"
        f"&doi={doi}"
    )


def slugify(text: str, max_len: int = 120) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    cleaned = re.sub(r"[\\/:*?\"<>|]", "_", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len] if len(cleaned) > max_len else cleaned


def fetch_readcube_refs(
    doi: str,
    title: str,
    out_dir: str | Path = "read_cube_ref",
    headers: Optional[dict] = None,
    cookies: Optional[dict] = None,
    timeout: int = 20,
) -> Optional[Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    safe_name = slugify(title)
    json_path = out_path / f"{safe_name}.json"
    if json_path.exists():
        logging.info("[ReadCube] exists, skip: %s", json_path.name)
        return json_path

    url = build_url(doi)
    hdr = DEFAULT_HEADERS | (headers or {})
    cks = DEFAULT_COOKIES | (cookies or {})

    try:
        resp = requests.get(url, headers=hdr, cookies=cks, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except RequestException as exc:
        logging.error("[ReadCube] request failed for DOI %s: %s", doi, exc)
        return None
    except ValueError:
        logging.warning("[ReadCube] non-JSON response for DOI %s", doi)
        return None

    try:
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.info("[ReadCube] saved: %s", json_path)
        return json_path
    except OSError as exc:
        logging.error("[ReadCube] write failed %s: %s", json_path, exc)
        return None


def _iter_meta_records(records: Iterable[dict]) -> Iterable[tuple[str, str]]:
    for rec in records:
        doi = rec.get("DOI") or rec.get("doi")
        title = rec.get("title")
        if doi and title:
            yield doi, title


def fetch_from_metadata(metadata_path: str | Path, out_dir: str | Path = "read_cube_ref", max_workers: int = 10) -> None:
    records = json.loads(Path(metadata_path).read_text(encoding="utf-8"))

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            tasks = [
                loop.run_in_executor(pool, fetch_readcube_refs, doi, title, out_dir)
                for doi, title in _iter_meta_records(records)
            ]
            if tasks:
                await asyncio.gather(*tasks)

    asyncio.run(_run())


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    reference_dir = project_root / "Reference"

    parser = argparse.ArgumentParser(description="Fetch ReadCube reference JSON (single DOI or metadata batch).")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--doi", help="Single DOI")
    group.add_argument("--meta", type=Path, default=reference_dir / "doi_metadata.json", help="Metadata JSON path for batch mode")
    parser.add_argument("--title", help="Required when using --doi")
    parser.add_argument("-o", "--out-dir", type=Path, default=reference_dir / "read_cube_ref")
    parser.add_argument("--max-workers", type=int, default=10)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    if args.dry_run:
        print("[dry-run] readcube_ref checks")
        print(f"mode={'single' if args.doi else 'batch'}")
        print(f"meta={args.meta}")
        print(f"out_dir={args.out_dir}")
        return 0

    if args.doi:
        if not args.title:
            logging.error("--title is required when using --doi")
            return 2
        ok = fetch_readcube_refs(args.doi, args.title, args.out_dir)
        return 0 if ok else 1

    if not args.meta.exists():
        logging.error("Metadata file not found: %s", args.meta)
        return 2

    fetch_from_metadata(args.meta, args.out_dir, max_workers=args.max_workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
