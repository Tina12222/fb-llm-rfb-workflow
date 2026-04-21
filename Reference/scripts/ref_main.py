#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CFG = SCRIPT_DIR / "config.yaml"

from Reference.scripts import combine as comb_mod
from Reference.scripts import crossref_ref as cr_mod
from Reference.scripts import dedup as dedup_mod
from Reference.scripts import fill_missing as align_mod
from Reference.scripts import readcube_ab_extract as ab_mod
from Reference.scripts import readcube_ref as rc_mod


def _resolve(path_str: str, cfg_dir: Path) -> Path:
    p = Path(path_str).expanduser()
    return p if p.is_absolute() else (cfg_dir / p).resolve()


def load_config(config_path: Path) -> dict:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cfg_dir = config_path.parent
    path_keys = [
        "raw_readcube_dir",
        "raw_crossref_dir",
        "aligned_dir",
        "merged_file",
        "dedup_file",
        "review_meta_json",
    ]
    for k in path_keys:
        cfg[k] = _resolve(str(cfg[k]), cfg_dir)
    cfg["max_workers"] = int(cfg.get("max_workers", 8))
    cfg["abstract_concurrency"] = int(cfg.get("abstract_concurrency", 5))
    return cfg


async def async_fetch_readcube(executor, doi, title, out_dir: Path):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, rc_mod.fetch_readcube_refs, doi, title, out_dir)


async def async_fetch_crossref(executor, doi, title, out_dir: Path):
    loop = asyncio.get_running_loop()
    refs = await loop.run_in_executor(executor, cr_mod.fetch_references, doi)
    if refs:
        await loop.run_in_executor(executor, cr_mod.save_references, title, refs, out_dir)
    return refs is not None


async def run_async_io(meta_list, cfg: dict):
    cfg["raw_readcube_dir"].mkdir(parents=True, exist_ok=True)
    cfg["raw_crossref_dir"].mkdir(parents=True, exist_ok=True)

    tasks = []
    with ThreadPoolExecutor(max_workers=cfg["max_workers"]) as executor:
        for rec in meta_list:
            doi = rec.get("DOI") or rec.get("doi")
            title = rec.get("title")
            if not doi or not title:
                continue

            rc_json = cfg["raw_readcube_dir"] / f"{rc_mod.slugify(title)}.json"
            if not rc_json.exists():
                tasks.append(async_fetch_readcube(executor, doi, title, cfg["raw_readcube_dir"]))

            cr_json = cfg["raw_crossref_dir"] / f"{cr_mod.sanitize_filename(title)}.json"
            if not cr_json.exists():
                tasks.append(async_fetch_crossref(executor, doi, title, cfg["raw_crossref_dir"]))

        if tasks:
            await asyncio.gather(*tasks)


def run_pipeline(cfg: dict) -> None:
    meta_path = cfg["review_meta_json"]
    if not meta_path.exists():
        raise FileNotFoundError(f"Meta file not found: {meta_path}")

    if meta_path.suffix in {".yml", ".yaml"}:
        meta_list = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    else:
        meta_list = json.loads(meta_path.read_text(encoding="utf-8"))

    logging.info("=== [Step-1] Fetch ReadCube & Crossref ===")
    asyncio.run(run_async_io(meta_list, cfg))

    logging.info("=== [Step-2] Align and fill DOI ===")
    align_mod.process_folders(
        str(cfg["raw_readcube_dir"]),
        str(cfg["raw_crossref_dir"]),
        str(cfg["aligned_dir"]),
        prefix_length=30,
    )

    logging.info("=== [Step-3] Merge references ===")
    comb_mod.merge_references(str(cfg["aligned_dir"]), str(cfg["merged_file"]))

    logging.info("=== [Step-4] Deduplicate ===")
    all_refs = dedup_mod.load_from_json(str(cfg["merged_file"]))
    uniq, dup = dedup_mod.deduplicate_references(all_refs)
    dedup_mod.save_refs(uniq, cfg["dedup_file"])
    dedup_mod.save_refs(dup, cfg["dedup_file"].parent / "dup_log.json", key="duplicates")

    logging.info("=== [Step-5] Extract abstracts ===")
    processed_json = cfg["dedup_file"].parent / "processed_dois.json"
    asyncio.run(
        ab_mod.run_update(
            str(cfg["dedup_file"]),
            str(cfg["dedup_file"].parent / "abstracts.json"),
            str(processed_json),
            cfg["abstract_concurrency"],
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Reference pipeline")
    parser.add_argument("--config", type=Path, default=DEFAULT_CFG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if not args.config.exists():
        logging.error("Config not found: %s", args.config)
        return 1

    cfg = load_config(args.config)

    if args.dry_run:
        print("[dry-run] reference pipeline checks")
        for k, v in cfg.items():
            print(f"{k}={v}")
        return 0

    run_pipeline(cfg)
    logging.info("Reference pipeline completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
