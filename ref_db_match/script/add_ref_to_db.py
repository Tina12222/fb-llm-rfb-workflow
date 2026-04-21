import argparse
import logging
import os
import json
import pandas as pd


def update_references_in_xlsx(xlsx_path: str, json_folder: str, output_suffix: str = '_updated') -> str:
    """Update an Excel file by injecting reference details from JSON files in a folder.

    Args:
        xlsx_path: Path to the source .xlsx file.
        json_folder: Folder containing JSON files with reference entries.
        output_suffix: Suffix to append before the .xlsx extension for the output file.

    Returns:
        The path of the updated Excel file.
    """
    # Load the Excel file
    df = pd.read_excel(xlsx_path, engine='openpyxl')

    # Process each JSON in the folder
    for filename in os.listdir(json_folder):
        if not filename.lower().endswith('.json'):
            continue
        file_path = os.path.join(json_folder, filename)

        with open(file_path, 'r', encoding='utf-8') as f:
            records = json.load(f)

        for entry in records:
            article_id = entry.get('article_id')
            # support both 'chunk ID' and 'chunk_id'
            chunk_id = entry.get('chunk ID') or entry.get('chunk_id')

            # Skip if key information missing
            if article_id is None or chunk_id is None:
                logging.warning(f"Skipping entry without article_id or chunk_id: {entry}")
                continue

            # Build mask for matching rows in DataFrame
            mask = (df['articleID'] == article_id) & (df['chunkID'] == chunk_id)
            if not mask.any():
                logging.warning(f"No match found for article_id={article_id}, chunk_id={chunk_id}")
                continue

            # References list -> single cell, separated by newline
            refs = entry.get('References used') or []
            if isinstance(refs, list):
                df.loc[mask, 'reference'] = "\n".join(refs)
            else:
                df.loc[mask, 'reference'] = refs

            # Abstracts (may be list or single string)
            abstract_val = entry.get('abstracts') or entry.get('abstract') or ''
            if isinstance(abstract_val, list):
                df.loc[mask, 'abstract'] = "\n\n".join(abstract_val)
            else:
                df.loc[mask, 'abstract'] = abstract_val

            # Ref IDs list -> single cell, separated by newline
            ref_ids = entry.get('ref_ids') or []
            if isinstance(ref_ids, list):
                df.loc[mask, 'ref_ids'] = "\n".join(ref_ids)
            else:
                df.loc[mask, 'ref_ids'] = ref_ids

    # Save updated DataFrame back to Excel
    output_path = xlsx_path.replace('.xlsx', f'{output_suffix}.xlsx')
    df.to_excel(output_path, index=False, engine='openpyxl')
    logging.info(f"Update complete: {output_path}")
    return output_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Update references in XLSX from JSON folder entries'
    )
    parser.add_argument(
        "-x", '--xlsx_path', default=r"Review_db\db_change_chunkid.xlsx",help='Path to the original Excel (.xlsx) file'
    )
    parser.add_argument(
        "-j", '--json_folder',default=r"ref_db_match\transformed", help='Path to the directory containing JSON files'
    )
    parser.add_argument(
        "-o", '--output_suffix', default='_updated',
        help='Suffix to append to the output file name before .xlsx'
    )
    args = parser.parse_args()

    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s'
    )

    update_references_in_xlsx(
        xlsx_path=args.xlsx_path,
        json_folder=args.json_folder,
        output_suffix=args.output_suffix
    )
