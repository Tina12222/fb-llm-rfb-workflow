"""Run the end-to-end Review_db pipeline.

Flow:
review_text -> sections -> chunks -> statements/themes -> review_database.pkl/csv
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import chunks_sep as chks
import database as build
import section_sep as sect
import statement_ex as stmt
import theme_ex as them

BASE_DIR = Path(__file__).resolve().parent


def ensure_dirs(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def run_pipeline(input_root: Path, workspace: Path) -> None:
    logging.info("INPUT=%s", input_root)
    logging.info("WORKSPACE=%s", workspace)
    t0 = time.time()

    sections_dir = workspace / "sections"
    chunks_dir = workspace / "chunks"
    statements_dir = workspace / "statements"
    themes_dir = workspace / "themes"
    ensure_dirs(sections_dir, chunks_dir, statements_dir, themes_dir)

    logging.info("Step 1/5 split sections")
    sect.process_all_files(input_root, sections_dir)

    logging.info("Step 2/5 split chunks")
    chks.process_all_sections(sections_dir, chunks_dir)

    logging.info("Step 3/5 extract statements")
    stmt.process_all_txt_folders(chunks_dir, statements_dir)

    logging.info("Step 4/5 extract themes")
    them.process_all_txt_folders(chunks_dir, themes_dir)

    logging.info("Step 5/5 build database")
    df = build.read_chunks_from_directory(chunks_dir, statements_dir, themes_dir)

    out_pkl = workspace / "review_database.pkl"
    out_csv = workspace / "review_database.csv"
    df.to_pickle(out_pkl)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    logging.info("Saved: %s", out_pkl)
    logging.info("Saved: %s", out_csv)
    logging.info("Elapsed %.1fs", time.time() - t0)


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command Review_db pipeline")
    parser.add_argument(
        "--input_root",
        default="./review_text",
        help="Input folder with raw .txt review papers (relative to Review_db).",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace output root (relative to Review_db).",
    )
    args = parser.parse_args()

    input_root = (BASE_DIR / args.input_root).resolve()
    workspace = (BASE_DIR / args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=str(workspace / "main_review.log"),
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        force=True,
    )

    if not input_root.is_dir():
        raise SystemExit(f"Input folder not found: {input_root}")

    run_pipeline(input_root, workspace)


if __name__ == "__main__":
    main()
