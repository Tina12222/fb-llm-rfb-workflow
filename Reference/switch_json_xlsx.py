import json
import os
from pathlib import Path

import pandas as pd


def json_to_excel(json_file: str, excel_file: str) -> None:
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data if isinstance(data, list) else data.get("references", [])
    if not isinstance(entries, list):
        raise ValueError(f"Expected list data, got {type(entries)}")

    df = pd.json_normalize(entries)
    out_path = Path(excel_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_path, index=False, engine="openpyxl")
    print(f"Excel generated: {out_path}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    default_json = Path(
        os.getenv(
            "REFERENCE_ABSTRACT_JSON",
            str(project_root / "Reference" / "abstract_with_publishers.json"),
        )
    )
    default_xlsx = Path(
        os.getenv(
            "REFERENCE_ABSTRACT_XLSX",
            str(project_root / "Reference" / "abstract_with_publishers.xlsx"),
        )
    )
    json_to_excel(str(default_json), str(default_xlsx))
