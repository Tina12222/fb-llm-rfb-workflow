import argparse
import json
import logging
import os
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def merge_references(input_folder: Union[str, Path], output_file: Union[str, Path]) -> int:
    input_path = Path(input_folder)
    output_path = Path(output_file)
    all_references = []

    json_files = list(input_path.glob("*.json"))
    if not json_files:
        logger.warning("No JSON files found in folder: %s", input_path)
        return 0

    for json_file in json_files:
        logger.info("Processing file: %s", json_file.name)
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON '%s': %s", json_file.name, e)
            continue
        except Exception as e:
            logger.warning("Failed to read '%s': %s", json_file.name, e)
            continue

        refs = data.get("references")
        if not isinstance(refs, list):
            logger.warning("File '%s' has no list field 'references'.", json_file.name)
            continue
        all_references.extend(refs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"references": all_references}, ensure_ascii=False, indent=4), encoding="utf-8")
    logger.info("Merged %d references -> %s", len(all_references), output_path)
    return len(all_references)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    project_root = Path(__file__).resolve().parents[2]
    default_input = Path(os.getenv("REFERENCE_ALIGNED_DIR", str(project_root / "Reference" / "aligned_ref")))
    default_output = Path(os.getenv("REFERENCE_MERGED_FILE", str(project_root / "Reference" / "merged_ref.json")))

    parser = argparse.ArgumentParser(description="Merge reference JSON files.")
    parser.add_argument("--input-folder", default=str(default_input), help="Folder containing JSON files with 'references'.")
    parser.add_argument("--output-file", default=str(default_output), help="Merged output JSON file.")
    args = parser.parse_args()

    count = merge_references(args.input_folder, args.output_file)
    logging.info("Done, merged references: %d", count)
