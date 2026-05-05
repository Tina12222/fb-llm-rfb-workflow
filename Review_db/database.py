"""Build the final review database from chunks/statements/themes."""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def clean_json_string(json_string: str) -> str:
    def replace_invalid_escape(match: re.Match[str]) -> str:
        byte_seq = bytes.fromhex(match.group()[2:])
        return byte_seq.decode("latin-1")

    return re.sub(r"\\x[0-9a-fA-F]{2}", replace_invalid_escape, json_string)


def get_json(raw: str, path: str):
    fenced = re.match(r"(?s)```(?:json)?\s*(.*?)\s*```", raw, flags=re.I)
    json_str = fenced.group(1) if fenced else raw
    json_str = clean_json_string(json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logging.error("JSON parse error at %s: %s", path, exc)
        return None


def read_chunks_from_directory(directory: str | Path, folder_b: str | Path, folder_d: str | Path) -> pd.DataFrame:
    directory = Path(directory)
    folder_b = Path(folder_b)
    folder_d = Path(folder_d)

    data: list[dict] = []
    for article_dir in directory.iterdir():
        if not article_dir.is_dir():
            continue
        article_id = article_dir.name

        for chunk_file in sorted(article_dir.glob("*.txt")):
            parts = chunk_file.name.split("_")
            if len(parts) < 3 or not parts[0].startswith("section"):
                continue

            section_id = parts[1]
            chunk_id = parts[2].split(".")[0]
            chunk_id_number = int("".join(filter(str.isdigit, chunk_id)))

            statement_path = folder_b / article_id / chunk_file.name.replace(".txt", "_result.txt")
            theme_path = folder_d / article_id / chunk_file.name.replace(".txt", "_theme.txt")

            try:
                chunk_content = chunk_file.read_text(encoding="utf-8")
            except FileNotFoundError:
                logging.error("Missing chunk: %s", chunk_file)
                continue

            try:
                statement_raw = statement_path.read_text(encoding="utf-8")
                statement_json = get_json(statement_raw, str(statement_path)) or {}
                statements = statement_json.get("descriptions", [])
            except FileNotFoundError:
                logging.error("Missing statement: %s", statement_path)
                continue

            try:
                theme_raw = theme_path.read_text(encoding="utf-8")
                theme_json = get_json(theme_raw, str(theme_path))
                if theme_json is None:
                    continue
                themes = theme_json.get("research questions or themes", [])
            except FileNotFoundError:
                logging.error("Missing theme: %s", theme_path)
                continue

            if len(statements) < 5:
                logging.warning("Insufficient statements for %s", chunk_file.name)
                continue

            data.append(
                {
                    "articleID": article_id,
                    "sectionID": int(section_id),
                    "chunkID": int(chunk_id_number),
                    "chunkContent": chunk_content,
                    "statementContent1": statements[0],
                    "statementContent2": statements[1],
                    "statementContent3": statements[2],
                    "statementContent4": statements[3],
                    "statementContent5": statements[4],
                    "theme1": themes[0] if len(themes) > 0 else None,
                    "theme2": themes[1] if len(themes) > 1 else None,
                    "theme3": themes[2] if len(themes) > 2 else None,
                    "theme4": themes[3] if len(themes) > 3 else None,
                    "theme5": themes[4] if len(themes) > 4 else None,
                }
            )

    df = pd.DataFrame(data)
    if not df.empty:
        df.sort_values(by=["articleID", "sectionID", "chunkID"], inplace=True)
    return df


def process_all_chunks(folder_a: str | Path, folder_b: str | Path, folder_d: str | Path, output_pkl: str | Path) -> None:
    df_chunks = read_chunks_from_directory(folder_a, folder_b, folder_d)
    output_pkl = Path(output_pkl)
    output_pkl.parent.mkdir(parents=True, exist_ok=True)
    df_chunks.to_pickle(output_pkl)
    logging.info("Saved %s", output_pkl)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build review database pkl")
    parser.add_argument("--folder_A", default="./chunks", help="chunks folder")
    parser.add_argument("--folder_B", default="./statements", help="statements folder")
    parser.add_argument("--folder_D", default="./themes", help="themes folder")
    parser.add_argument("--output_pkl", default="./review_database.pkl", help="output pkl path")
    args = parser.parse_args()

    folder_a = (BASE_DIR / args.folder_A).resolve()
    folder_b = (BASE_DIR / args.folder_B).resolve()
    folder_d = (BASE_DIR / args.folder_D).resolve()
    output_pkl = (BASE_DIR / args.output_pkl).resolve()

    process_all_chunks(folder_a, folder_b, folder_d, output_pkl)


if __name__ == "__main__":
    main()
