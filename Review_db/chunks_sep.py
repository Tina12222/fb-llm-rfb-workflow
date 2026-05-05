import argparse
import logging
import re
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent


def count_words(text: str) -> int:
    return len(text.split())


def contains_table(text: str) -> bool:
    return bool(re.search(r"<table.*?>.*?</table>", text, re.DOTALL))


def split_text_into_chunks(text: str, max_words: int = 500, log: logging.Logger | None = None) -> List[str]:
    if log:
        log.debug("split_text_into_chunks max_words=%d", max_words)

    text = text.replace("\n\n--\n\n", "<PAGE>")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks, current_chunk = [], []
    for para in paragraphs:
        if contains_table(para):
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
            chunks.append(para)
            continue

        if sum(count_words(p) for p in current_chunk) + count_words(para) > max_words:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
        else:
            current_chunk.append(para)

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def process_section_file(
    input_file: Path,
    output_dir: Path,
    max_words: int = 600,
    min_words: int = 30,
    logger: logging.Logger | None = None,
) -> None:
    text = input_file.read_text(encoding="utf-8")
    subsections = re.split(r"\n\s*\*\*\*\s*", text)
    base_name = input_file.stem

    chunk_idx = 1
    for sub in subsections:
        parts = re.split(r"\n\s*\*\*\s*", sub) if "**" in sub else [sub]
        for part in parts:
            if not part.strip():
                continue

            wc = count_words(part)
            if wc < min_words:
                continue

            if wc <= max_words:
                (output_dir / f"{base_name}_chunk{chunk_idx}.txt").write_text(part.strip(), encoding="utf-8")
                chunk_idx += 1
            else:
                for chunk in split_text_into_chunks(part, max_words, logger):
                    (output_dir / f"{base_name}_chunk{chunk_idx}.txt").write_text(chunk, encoding="utf-8")
                    chunk_idx += 1


def process_all_sections(
    sections_root: str | Path,
    chunks_root: str | Path,
    max_words: int = 600,
    min_words: int = 30,
) -> None:
    logger = logging.getLogger("chunks_sep")
    sections_root = Path(sections_root)
    chunks_root = Path(chunks_root)

    for paper_dir in sections_root.iterdir():
        if not paper_dir.is_dir():
            continue

        out_dir = chunks_root / paper_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)

        for sec_file in sorted(paper_dir.glob("section*.txt")):
            process_section_file(sec_file, out_dir, max_words=max_words, min_words=min_words, logger=logger)


def main() -> None:
    parser = argparse.ArgumentParser(description="Split section-level txt into chunk-level txt")
    parser.add_argument("--input", default="./sections", help="sections root")
    parser.add_argument("--output", default="./chunks", help="chunks root")
    parser.add_argument("--max_words", type=int, default=600)
    parser.add_argument("--min_words", type=int, default=30)
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s - %(levelname)s - %(message)s")
    process_all_sections(
        sections_root=(BASE_DIR / args.input).resolve(),
        chunks_root=(BASE_DIR / args.output).resolve(),
        max_words=args.max_words,
        min_words=args.min_words,
    )


if __name__ == "__main__":
    main()
