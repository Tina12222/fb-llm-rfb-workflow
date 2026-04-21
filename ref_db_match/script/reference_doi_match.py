import os
import json
import argparse
import logging

def load_json_file(file_path):
    """加载json文件并返回数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json_file(file_path, data):
    """保存数据到json文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def match_references(article_json, reference_library):
    """
    给定一篇文章的json数据，和参考文献库，匹配cited_ids并将匹配的参考文献添加到文章数据中
    """
    for article in article_json:
        matched_references = []  # 用于存储匹配的参考文献
        if 'cited_ids' in article:  # 确保有cited_ids
            for cited_id in article['cited_ids']:
                # 在文献库中查找与cited_id匹配的文献
                matching_reference = next((ref for ref in reference_library["references"] if ref['doi'] == cited_id), None)
                if matching_reference:
                    matched_references.append(matching_reference)
        
        # 如果匹配到了参考文献，将它们添加到文章字典中的matched_reference
        if matched_references:
            article['matched_references'] = matched_references
    
    return article_json

def process_json_files(input_folder, output_folder, reference_library_path):
    """
    遍历文件夹下的每个json文件，匹配引用的文献，并保存到新的文件夹
    """
    # 加载文献库
    reference_library = load_json_file(reference_library_path)
    
    # 遍历输入文件夹中的所有json文件
    for filename in os.listdir(input_folder):
        if filename.endswith('.json'):
            input_file_path = os.path.join(input_folder, filename)
            output_file_path = os.path.join(output_folder, filename)
            
            # 加载每个json文件
            article_json = load_json_file(input_file_path)
            
            # 匹配参考文献
            updated_article_json = match_references(article_json, reference_library)
            
            # 保存更新后的json文件到输出文件夹
            save_json_file(output_file_path, updated_article_json)

def main():
    parser = argparse.ArgumentParser(
        description="Match cited references in article JSON files against a reference library."
    )
    parser.add_argument(
        "--input_folder", "-i", default=r"ref_db_match\index_to_doi",
        help="Folder containing JSON files with articles to process."
    )
    parser.add_argument(
        "--output_folder", "-o", default=r"ref_db_match\matched",
        help="Folder to save updated JSON files with matched references."
    )
    parser.add_argument(
        "--reference_library_path", "-r", default=r"Reference\dedup_ref_abstract.json",
        help="Path to reference library JSON file."
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    process_json_files(args.input_folder, args.output_folder, args.reference_library_path)

if __name__ == "__main__":
    main()
