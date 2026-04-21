import argparse
import json
import logging
import os
from pathlib import Path


def process_references(new_json_folder, reference_db_folder, output_folder):
    new_json_path = Path(new_json_folder)
    reference_db_path = Path(reference_db_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    new_json_files = list(new_json_path.glob("*.json"))
    if not new_json_files:
        print(f"No JSON files found in '{new_json_path}'.")
        return

    for new_json_file in new_json_files:
        print(f"Processing file: {new_json_file.name}")
        prefix = new_json_file.stem[:50]
        candidates = list(reference_db_path.glob(f"{prefix}*"))
        if not candidates:
            print(f"Warning: no reference DB file starts with '{prefix}', skipped.")
            continue
        if len(candidates) > 1:
            print(f"Warning: multiple candidates for '{prefix}', using first: {[p.name for p in candidates]}")
        reference_db_file = candidates[0]

        try:
            new_data = json.loads(new_json_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Warning: failed to load '{new_json_file.name}': {e}")
            continue

        try:
            reference_data = json.loads(reference_db_file.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning("Failed to load DB file %s: %s", reference_db_file.name, e)
            continue

        if "references" not in reference_data:
            print(f"Warning: file '{reference_db_file.name}' has no 'references' key.")
            continue

        references_db = reference_data["references"]
        output_data = []

        for idx, item in enumerate(new_data, start=1):
            if not isinstance(item, dict):
                print(f"Warning: item #{idx} in '{new_json_file.name}' is not dict, skipped.")
                continue

            article_id = item.get("article_id", "N/A")
            chunk_id = item.get("chunk ID", "N/A")
            references = item.get("references", [])
            if not isinstance(references, list):
                print(f"Warning: item #{idx} has non-list 'references', skipped.")
                continue

            cited_ids = []
            for ref_id in references:
                for reference in references_db:
                    label = reference.get("ordinal")
                    unique_id = reference.get("doi")
                    if label is None or unique_id is None:
                        continue
                    if ref_id == label:
                        cited_ids.append(unique_id)
                        break

            output_data.append(
                {
                    "article_id": article_id,
                    "chunk ID": chunk_id,
                    "references": references,
                    "cited_ids": cited_ids,
                }
            )

        output_file = output_path / new_json_file.name
        output_file.write_text(json.dumps(output_data, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"Saved: {output_file}")
        print("-" * 50)

    print("All files processed.")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Map reference ordinals to DOI.")
    parser.add_argument(
        "-n",
        "--new_json_folder",
        default=os.getenv("REF_MATCH_NEW_JSON_DIR", str(project_root / "ref_db_match" / "re_idx")),
        help="Folder containing new JSON files.",
    )
    parser.add_argument(
        "-r",
        "--reference_db_folder",
        default=os.getenv("REF_MATCH_DB_DIR", str(project_root / "Reference" / "aligned_ref")),
        help="Reference DB folder.",
    )
    parser.add_argument(
        "-o",
        "--output_folder",
        default=os.getenv("REF_MATCH_OUTPUT_DIR", str(project_root / "ref_db_match" / "index_to_doi")),
        help="Output folder.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    process_references(args.new_json_folder, args.reference_db_folder, args.output_folder)
