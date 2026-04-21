import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def transform_matched_references(input_folder: str, output_folder: str) -> None:
    """
    遍历 input_folder 中所有 JSON 文件，将 'matched_references' 转为格式化的
    'References used'，并收集 'abstracts' 和 'ref_ids'，最后保存到 output_folder。

    :param input_folder: 包含匹配结果 JSON 文件的文件夹路径
    :param output_folder: 用于保存转换后 JSON 文件的文件夹路径
    """
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    json_files = list(input_path.glob("*.json"))
    if not json_files:
        logger.warning("在文件夹 '%s' 中未找到任何 JSON 文件。", input_path)
        return

    for json_file in json_files:
        logger.info("处理文件: %s", json_file.name)
        try:
            data = json.loads(json_file.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.warning("无法解析文件 '%s'：%s", json_file.name, e)
            continue
        except Exception as e:
            logger.warning("读取文件 '%s' 时出错：%s", json_file.name, e)
            continue

        if not isinstance(data, list):
            logger.warning("文件 '%s' 的内容不是列表，已跳过。", json_file.name)
            continue

        for idx, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                logger.warning("文件 '%s' 中第 %d 个条目不是字典，已跳过。", json_file.name, idx)
                continue

            matched = item.get('matched_references')
            # 初始化三项
            references_used = []
            abstracts = []
            ref_ids = []

            if isinstance(matched, list) and matched:
                for ref in matched:
                    if not isinstance(ref, dict):
                        logger.warning("文件 '%s' 中第 %d 个条目的某个引用不是字典，已跳过。", json_file.name, idx)
                        continue

                    parts = []
                    # authors
                    auth = ref.get('authors')
                    if auth:
                        parts.append(", ".join(auth) if isinstance(auth, list) else str(auth))
                    # journal/year/volume/pagination
                    jp = []
                    for k in ('journal','year','volume','pagination'):
                        v = ref.get(k)
                        if v:
                            jp.append(str(v))
                    if jp:
                        parts.append(f"({' '.join(jp)})")
                    # title
                    parts.append(ref.get('title','N/A'))
                    # doi/url
                    if ref.get('doi'):
                        parts.append(f"DOI: {ref['doi']}")
                    if ref.get('article_url'):
                        parts.append(ref['article_url'])

                    if parts:
                        references_used.append("- " + ", ".join(parts))
                    else:
                        logger.warning("文件 '%s' 中第 %d 个条目的引用字段全缺失，无法格式化。", json_file.name, idx)

                    # abstracts & ref_ids
                    if ref.get('abstract'):
                        abstracts.append(ref['abstract'])
                    if ref.get('doi'):
                        ref_ids.append(ref['doi'])

            else:
                if matched is None:
                    logger.debug("文件 '%s' 第 %d 条未包含 'matched_references'。", json_file.name, idx)
                else:
                    logger.debug("文件 '%s' 第 %d 条 'matched_references' 为空或类型不对。", json_file.name, idx)

            item['References used'] = references_used
            item['abstracts'] = abstracts
            item['ref_ids'] = ref_ids

            # 安全移除旧字段
            for key in ('matched_references','cited_ids','references'):
                item.pop(key, None)

        # 写出到 output_folder
        out_file = output_path / json_file.name
        try:
            out_file.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')
            logger.info("已保存: %s", out_file)
        except Exception as e:
            logger.warning("无法保存 '%s'：%s", out_file.name, e)

    logger.info("所有文件处理完成。")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="格式化 matched_references 并生成新的 JSON 文件"
    )
    parser.add_argument("-i","--input_folder",default=r"ref_db_match\matched", help="输入 JSON 文件夹路径")
    parser.add_argument("-o","--output_folder",default=r"ref_db_match\transformed", help="输出 JSON 文件夹路径")
    args = parser.parse_args()

    transform_matched_references(args.input_folder, args.output_folder)
