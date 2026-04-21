from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
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


def _load_cookies_from_env() -> Dict[str, str]:
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


async def fetch_abstract(
    doi: str,
    session: "aiohttp.ClientSession",
    headers: Dict[str, str] = DEFAULT_HEADERS,
    cookies: Dict[str, str] = DEFAULT_COOKIES,
) -> Optional[str]:
    url = build_url(doi)
    try:
        async with session.get(url, headers=headers, cookies=cookies) as resp:
            if resp.status != 200:
                logging.warning("DOI %s request failed: status=%s", doi, resp.status)
                return None
            data = await resp.json()
            return data.get("meta", {}).get("abstract")
    except Exception:
        logging.exception("Failed to fetch abstract for DOI %s", doi)
        return None


async def save_json(path: Union[str, Path], obj: Union[dict, list]) -> None:
    if aiofiles is None:
        raise RuntimeError("Missing dependency: aiofiles")
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(obj, ensure_ascii=False, indent=2))


async def load_processed_dois(path: Union[str, Path]) -> Set[str]:
    if aiofiles is None:
        raise RuntimeError("Missing dependency: aiofiles")
    path = Path(path)
    if not path.exists():
        return set()
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()
    return set(json.loads(content))


async def process_single(
    entry: Dict,
    session: "aiohttp.ClientSession",
    processed: Set[str],
    data: List[Dict],
    output_file: Union[str, Path],
    processed_file: Union[str, Path],
    lock: asyncio.Lock,
) -> None:
    doi = entry.get("doi")
    if not doi or doi in processed or entry.get("abstract"):
        return

    abstract = await fetch_abstract(doi, session)
    if abstract:
        entry["abstract"] = abstract

    processed.add(doi)
    async with lock:
        await save_json(output_file, data)
        await save_json(processed_file, list(processed))


async def update_abstracts(
    data: List[Dict],
    output_file: Union[str, Path],
    processed_file: Union[str, Path],
    concurrency: int = 5,
) -> List[Dict]:
    if aiohttp is None:
        raise RuntimeError("Missing dependency: aiohttp")

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


async def run_update(
    input_file: Union[str, Path],
    output_file: Union[str, Path],
    processed_file: Union[str, Path],
    concurrency: int = 5,
) -> None:
    if aiofiles is None:
        raise RuntimeError("Missing dependency: aiofiles")

    input_path = Path(input_file)
    output_path = Path(output_file)
    processed_path = Path(processed_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(input_path, "r", encoding="utf-8") as f:
        parsed = json.loads(await f.read())

    if isinstance(parsed, list):
        data = parsed
        wrapper_key = None
    elif isinstance(parsed, dict):
        wrapper_key = "references" if "references" in parsed else "data"
        data = parsed.get(wrapper_key)
        if data is None:
            raise ValueError("Input JSON must contain 'references' or 'data'.")
    else:
        raise ValueError("Unsupported JSON type.")

    updated = await update_abstracts(data, output_path, processed_path, concurrency)

    if wrapper_key is not None:
        parsed[wrapper_key] = updated
        await save_json(output_path, parsed)
    else:
        await save_json(output_path, updated)


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    reference_dir = project_root / "Reference"

    parser = argparse.ArgumentParser(description="Update abstracts in a reference JSON via ReadCube metadata API.")
    parser.add_argument("-i", "--input", type=Path, default=reference_dir / "dedup_ref.json")
    parser.add_argument("-o", "--output", type=Path, default=reference_dir / "dedup_ref_abstract.json")
    parser.add_argument("-p", "--processed", type=Path, default=reference_dir / "processed_dois.json")
    parser.add_argument("-c", "--concurrency", type=int, default=10)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    if args.dry_run:
        print("[dry-run] readcube_ab_extract checks")
        print(f"input={args.input}")
        print(f"output={args.output}")
        print(f"processed={args.processed}")
        print(f"aiohttp_installed={aiohttp is not None}")
        print(f"aiofiles_installed={aiofiles is not None}")
        return 0

    if not args.input.exists():
        logging.error("Input JSON not found: %s", args.input)
        return 1

    asyncio.run(run_update(args.input, args.output, args.processed, args.concurrency))
    logging.info("Abstract extraction completed: %s", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
