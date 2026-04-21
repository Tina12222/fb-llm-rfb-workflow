"""
re_chunk_ref.py
提取 Excel（列: articleID, chunkContent）中的参考文献索引号，
按 articleID 生成 JSON。供 pipeline.py 调用：
    >>> from re_chunk_ref import extract_refs_from_excel
    >>> extract_refs_from_excel("db.xlsx", "out_dir")
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------- #
# 正则：匹配 [3]、(3)、数字范围等多种引用写法
# --------------------------------------------------------------------- #
reference_pattern = r'''
    # 匹配方括号中的数字，例如 [3]
    \[(?P<bracket>\d+)\]
    |
    # 匹配圆括号中的数字，例如 (3)
    \((?P<paren>\d+)\)
    |
    # 匹配标点符号后面的数字或数字范围
    (?<!Table\s)(?<!Figure\s)(?<!Fig\.\s)(?<!Section\s)(?<!Page\s)
    (?:
        (?<!\d)\.       # 匹配 '.'，但前面不是数字（避免小数点）
        | [;,:]         # 或者匹配 ';'、','、':'
    )
    \s*                # 可选的空白字符
    (?P<range>\d+\s*[–-]\s*\d+)    # 匹配数字范围，例如 '3–6' 或 '3-6'
    (?=\W|$)           # 确保后面跟着非单词字符或字符串结束
    |
    (?<!Table\s)(?<!Figure\s)(?<!Fig\.\s)(?<!Section\s)(?<!Page\s)
    (?:
        (?<!\d)\.       # 匹配 '.'，但前面不是数字
        | [;,:]         # 或者匹配 ';'、','、':'
    )
    \s*
    (?P<single>\d+)    # 匹配单个数字，例如 '7'
    (?=\W|$)           # 确保后面跟着非单词字符或字符串结束
'''


# --------------------------------------------------------------------- #
# 核心函数
# --------------------------------------------------------------------- #
def extract_references(text):
    """
    提取一段文本中的参考文献索引号，返回一个扁平化的列表。
    """
    references = []
    
    # 使用正则表达式查找所有匹配的内容
    matches = re.finditer(reference_pattern, text, re.UNICODE | re.VERBOSE)
    
    for match in matches:
        if match.group('range'):
            # 处理引用范围，例如 '3–6' 或 '3-6'
            ref = match.group('range').replace('–', '-').replace(' ', '')
            try:
                start, end = map(int, ref.split('-'))
                if start <= end:
                    references.extend(range(start, end + 1))
                else:
                    print(f"Warning: 起始数字 {start} 大于结束数字 {end} 在引用范围 '{ref}' 中。")
            except ValueError:
                print(f"Warning: 无法解析引用范围 '{ref}'。")
        elif match.group('single'):
            # 处理单个引用，例如 '7'
            try:
                single_ref = int(match.group('single'))
                references.append(single_ref)
            except ValueError:
                print(f"Warning: 无法解析单个引用 '{match.group('single')}'。")
        elif match.group('bracket'):
            # 处理方括号中的引用，例如 '[3]'
            try:
                bracket_ref = int(match.group('bracket'))
                references.append(bracket_ref)
            except ValueError:
                print(f"Warning: 无法解析方括号引用 '{match.group('bracket')}'。")
        elif match.group('paren'):
            # 处理圆括号中的引用，例如 '(3)'
            try:
                paren_ref = int(match.group('paren'))
                references.append(paren_ref)
            except ValueError:
                print(f"Warning: 无法解析圆括号引用 '{match.group('paren')}'。")
    
    # 去除重复引用并排序（可选）
    references = sorted(set(references))
    
    return references


def extract_references_from_chunks(chunks):
    """
    从多个chunk中提取参考文献索引号，返回嵌套列表结构。
    """
    all_references = []
    
    for chunk in chunks:
        references = extract_references(chunk)
        all_references.append(references)
    
    return all_references



def process_excel(file_path, output_folder):
    """
    处理Excel文件，提取每个Article ID中的参考文献索引号，并保存为一个大的列表
    """
    # 读取Excel文件
    df = pd.read_excel(file_path)
    
    # 遍历每个artical ID
    for article_id in df['articleID'].unique():
        article_data = df[df['articleID'] == article_id]  # 获取当前article ID的所有chunk
        
        article_references = []  # 用于保存当前article ID下的所有chunk引用的参考文献
        
        # 给每个chunk分配一个从1开始的ID
        for chunk_index, (index, row) in enumerate(article_data.iterrows(), start=1):
            chunk_content = row['chunkContent']
            references = extract_references(chunk_content)  # 提取该chunk的参考文献
            article_references.append({
                "article_id": article_id,
                "chunk ID": chunk_index,  # 从1开始
                "references": references
            })
        
        # 将当前article ID的参考文献数据保存为一个JSON文件
        output_file_path = f"{output_folder}/{article_id}.json"
        with open(output_file_path, 'w', encoding='utf-8') as json_file:
            json.dump(article_references, json_file, ensure_ascii=False, indent=4)
        
        print(f"Saved references for article {article_id} to {output_file_path}")
    
    print("Processing complete.")


# --------------------------------------------------------------------- #
# 可选：脚本直接运行
# --------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    import argparse, sys

    parser = argparse.ArgumentParser(
        description="Extract reference indices from Excel and dump per‑article JSON."
    )
    parser.add_argument("excel", default=r"Review_db\db_change_chunkid.xlsx",help="Path to database_rag.xlsx")
    parser.add_argument("out_dir", default=r"ref_db_match\re_idx",help="Directory to store JSON")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    process_excel(args.excel, args.out_dir)
