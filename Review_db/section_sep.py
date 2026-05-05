"""Split review paper text files into section files."""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def split_text_file(input_path: Path, output_dir: Path, section_delim: str = "**") -> int:
    try:
        text = input_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        logging.warning("Skip decode error %s: %s", input_path, exc)
        return 0

    if re.search(r"[\\\[\^\$\.\|\?\*\+\(\)]", section_delim):
        sections = re.split(section_delim, text)
    else:
        sections = text.split(section_delim)

    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for idx, sec in enumerate(sections):
        sec = sec.strip()
        if not sec:
            continue
        (output_dir / f"section_{idx}.txt").write_text(sec, encoding="utf-8")
        written += 1
    return written


def process_all_files(input_folder: str | Path, output_base_folder: str | Path, section_delim: str = "**") -> int:
    input_folder = Path(input_folder)
    output_base_folder = Path(output_base_folder)

    total = 0
    for input_file in sorted(input_folder.glob("*.txt")):
        output_dir = output_base_folder / input_file.stem
        total += split_text_file(input_file, output_dir, section_delim=section_delim)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Split papers into sections")
    parser.add_argument("--input_dir", default="./review_text", help="Input .txt folder")
    parser.add_argument("--output_dir", default="./sections", help="Output sections root")
    parser.add_argument("--section_delim", default="**", help="Section delimiter or regex")
    args = parser.parse_args()

    input_dir = (BASE_DIR / args.input_dir).resolve()
    output_dir = (BASE_DIR / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    total = process_all_files(input_dir, output_dir, section_delim=args.section_delim)
    logging.info("Done, wrote %d section files", total)


if __name__ == "__main__":
    main()
