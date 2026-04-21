#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

import pandas as pd


def filter_by_year_and_abstract(input_path: str, output_path: str, max_year: int, sheet_name=0):
    df = pd.read_excel(input_path, sheet_name=sheet_name)
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df_filtered = df[df['year'].notna() & (df['year'] <= max_year)]
    df_filtered = df_filtered[df_filtered['abstract'].notna()]
    df_filtered['abstract'] = df_filtered['abstract'].astype(str).str.strip()
    df_filtered = df_filtered[df_filtered['abstract'] != '']
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_filtered.to_excel(output_path, index=False)
    print(f'Filtered rows: {len(df_filtered)} -> {output_path}')


def main():
    project_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description='Filter Excel by year and abstract availability.')
    parser.add_argument('-i', '--input', default=str(project_dir / 'data' / 'dedup_ref_abstract_del.xlsx'))
    parser.add_argument('-o', '--output', default=str(project_dir / 'data' / 'abstract_2023.xlsx'))
    parser.add_argument('-y', '--year', default=2023, type=int)
    parser.add_argument('-s', '--sheet', default=0)
    args = parser.parse_args()
    filter_by_year_and_abstract(args.input, args.output, args.year, args.sheet)


if __name__ == '__main__':
    main()
