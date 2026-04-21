from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, Union
from urllib.parse import quote_plus

try:
    import aiofiles
    import aiohttp
except ImportError:
    aiofiles = None
    aiohttp = None


def build_url(doi: str) -> str:
    encoded = quote_plus(doi)
    return (
        "https://services.readcube.com:443/reader/metadata"
        "?client=web_reader"
        "&client_id=041a907f-445e-4f07-9cd7-d7fcdca7d9b4"
        "&client_version=26.13.0"
        f"&doi={encoded}"
    )


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


async def fetch_abstract(session: "aiohttp.ClientSession", doi: str) -> str:
    url = build_url(doi)
    try:
        async with session.get(url, headers=DEFAULT_HEADERS, cookies=DEFAULT_COOKIES) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("meta", {}).get("abstract") or ""
    except Exception as exc:
        logging.error("Error fetching abstract for %s: %s", doi, exc)
        return ""


async def enrich_abstracts(input_file: Union[str, Path], output_file: Union[str, Path]) -> None:
    if aiofiles is None or aiohttp is None:
        raise RuntimeError("Missing dependency: aiofiles or aiohttp")

    in_path = Path(input_file)
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(in_path, "r", encoding="utf-8") as f:
        obj: Dict = json.loads(await f.read())

    refs = obj.get("references", [])
    if not isinstance(refs, list):
        raise ValueError("Input JSON must contain a list field 'references'.")

    async with aiohttp.ClientSession() as session:
        for ref in refs:
            if ref.get("abstract"):
                continue
            doi = ref.get("doi")
            if not doi:
                continue
            abstract = await fetch_abstract(session, doi)
            if abstract:
                ref["abstract"] = abstract
                logging.info("Updated abstract for DOI %s", doi)

    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    reference_dir = project_root / "Reference"

    parser = argparse.ArgumentParser(description="Fill missing abstracts in references JSON.")
    parser.add_argument("-i", "--input", type=Path, default=reference_dir / "dedup_ref_abstract.json")
    parser.add_argument("-o", "--output", type=Path, default=reference_dir / "abstract.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    if args.dry_run:
        print("[dry-run] supply_ab checks")
        print(f"input={args.input}")
        print(f"output={args.output}")
        print(f"aiohttp_installed={aiohttp is not None}")
        print(f"aiofiles_installed={aiofiles is not None}")
        return 0

    if not args.input.exists():
        logging.error("Input file not found: %s", args.input)
        return 1

    asyncio.run(enrich_abstracts(args.input, args.output))
    logging.info("Saved enriched JSON to %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
