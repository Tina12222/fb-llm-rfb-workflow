# logger_utils.py
import logging
import sys
from pathlib import Path

def init_logger(
    log_dir: Path,
    logger_name: str = "main_logger",
    log_filename: str = "bk_retrieval.log",
    file_level: int = logging.DEBUG,
    stream_level: int = logging.INFO
) -> logging.Logger:
    """
    创建 log_dir（如果不存在），并初始化一个带 FileHandler 和 StreamHandler 的 Logger。
    """
    # 确保目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename

    # 创建 Logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # 接收所有级别，Handler 控制输出

    # 日志格式
    fmt = "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    # 文件处理器
    file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)

    # 控制台处理器
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stream_level)
    stream_handler.setFormatter(formatter)

    # 重置并添加
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
