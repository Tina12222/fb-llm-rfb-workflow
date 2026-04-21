from pathlib import Path
import os
SCRIPT_DIR  = Path(__file__).resolve().parent          
PROJECT_DIR = SCRIPT_DIR.parent  

import json
import logging
from Reaearch_Idea.code import bk_prompt as pmt
from Reaearch_Idea.code.query_process import query_Gemini
from Reaearch_Idea.code.logger_utils import init_logger


LOG_DIR = PROJECT_DIR / "dedupe"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "dedupe.log"

# 初始化 Logger
logger = init_logger(
    log_dir=LOG_DIR,
    logger_name=__name__,
    log_filename="dedupe.log",
    file_level=logging.DEBUG,
    stream_level=logging.INFO
)


# 假设 JSON 文件，里面存储一个字符串列表
IDEAS_JSON_FILE = PROJECT_DIR / "hypothesis" / "combined_inspirations_hypothesis.json"
if not IDEAS_JSON_FILE.exists():
    logger.error(f"未找到假设 JSON 文件：{IDEAS_JSON_FILE}")
    sys.exit(1)

# 输出路径
OUTPUT_DIR = PROJECT_DIR / "hypothesis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TXT_OUT = OUTPUT_DIR / "unique_hypotheses.txt"
JSON_OUT = OUTPUT_DIR / "unique_hypotheses.json"


MODEL = os.getenv("MODEL_NAME", "o3")


with open(IDEAS_JSON_FILE, "r", encoding="utf-8") as f:
    try:
        data = json.load(f)
        print(data)
        # 如果是字典，尝试提取常见字段
        if isinstance(data, dict) and "idea" in data:
            ideas_list = data["idea"]
        elif isinstance(data, list):
            ideas_list = data
        else:
            raise ValueError("假设 JSON 文件格式不符合要求，需要列表或包含 'hypotheses' 键的字典。")
    except Exception as e:
        logger.error(f"解析假设 JSON 失败：{e}")
        sys.exit(1)

if not ideas_list or not all(isinstance(i, str) for i in ideas_list):
    logger.error("假设列表为空或格式不正确，退出。")
    sys.exit(1)


def dedupe_ideas(ideas: list) -> list:
    """
    使用大模型检查并去除重复的研究想法。
    输入：字符串列表；输出：去重后的字符串列表。
    """
    block = "\n".join(f"- {idea}" for idea in ideas)
    messages = pmt.template("deduplication", ideas=block)
    try:
        resp = query_Gemini(messages, model=MODEL)
        logger.info("去重模型返回: %s", resp)
        unique = json.loads(resp)
        if not isinstance(unique, list):
            raise ValueError("去重返回结果不是列表格式")
        return unique
    except Exception as e:
        logger.error("去重调用失败：%s", e)
        return ideas  # 出错则返回原列表


def main():
    unique_ideas = dedupe_ideas(ideas_list)
    # 保存 TXT，每行一个想法
    try:
        TXT_OUT.write_text("\n".join(unique_ideas), encoding="utf-8")
        logger.info(f"去重结果已保存到 TXT: {TXT_OUT}")
    except Exception as e:
        logger.error(f"保存 TXT 失败：{e}")

    # 保存 JSON
    try:
        with open(JSON_OUT, "w", encoding="utf-8") as jf:
            json.dump(unique_ideas, jf, ensure_ascii=False, indent=2)
        logger.info(f"去重结果已保存到 JSON: {JSON_OUT}")
    except Exception as e:
        logger.error(f"保存 JSON 失败：{e}")

if __name__ == "__main__":
    main()
