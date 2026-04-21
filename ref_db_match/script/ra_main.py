#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from add_ref_to_db import update_references_in_xlsx
from index_to_doi import process_references
from normalization import transform_matched_references
from re_index import process_excel
from reference_doi_match import process_json_files as match_doi_to_meta

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CFG = SCRIPT_DIR / "config.yaml"


def _resolve(path_str: str, cfg_dir: Path) -> Path:
    p = Path(path_str).expanduser()
    return p if p.is_absolute() else (cfg_dir / p).resolve()


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg_dir = path.parent
    keys = [
        "input_excel",
        "references_json_folder",
        "reference_db_folder",
        "index_to_doi_folder",
        "matched_folder",
        "transformed_folder",
        "reference_db_json",
    ]
    for k in keys:
        cfg[k] = _resolve(str(cfg[k]), cfg_dir)
    return cfg


def run_pipeline(cfg: dict) -> None:
    logging.info("1) Extract references index to JSON")
    process_excel(file_path=str(cfg["input_excel"]), output_folder=str(cfg["references_json_folder"]))

    logging.info("2) Map index to DOI")
    process_references(
        new_json_folder=str(cfg["references_json_folder"]),
        reference_db_folder=str(cfg["reference_db_folder"]),
        output_folder=str(cfg["index_to_doi_folder"]),
    )

    logging.info("3) Match DOI to metadata")
    match_doi_to_meta(
        input_folder=str(cfg["index_to_doi_folder"]),
        output_folder=str(cfg["matched_folder"]),
        reference_library_path=str(cfg["reference_db_json"]),
    )

    logging.info("4) Normalize matched references")
    transform_matched_references(
        input_folder=str(cfg["matched_folder"]),
        output_folder=str(cfg["transformed_folder"]),
    )

    logging.info("5) Write back references to Excel")
    update_references_in_xlsx(
        xlsx_path=str(cfg["input_excel"]),
        json_folder=str(cfg["transformed_folder"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ref_db_match pipeline")
    parser.add_argument("--config", "-c", type=Path, default=DEFAULT_CFG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    if not args.config.exists():
        logging.error("Config not found: %s", args.config)
        return 1

    cfg = load_config(args.config)

    if args.dry_run:
        print("[dry-run] ref_db_match checks")
        for k, v in cfg.items():
            print(f"{k}={v}")
        return 0

    run_pipeline(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
