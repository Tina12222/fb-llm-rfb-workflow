# crossref_ref.py
"""
拉取 Crossref 参考文献，并保存为 JSON
可直接 import 使用，也可通过 CLI `python crossref_ref.py --help`
"""
from __future__ import annotations
import json
import re
import time
import logging
import argparse
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

__all__ = ["fetch_references", "save_references", "process_metadata_file"]

logger = logging.getLogger(__name__)  # 不在 import 时自动配置 handler

# ------------------------------------------------------------------------
# 1. 公共工具
# ------------------------------------------------------------------------
def sanitize_filename(name: str) -> str:
    """去掉 Windows/Unix 文件名不合法字符"""
    return re.sub(r'[\\/:*?"<>|]', " ", name).strip()

def make_session(max_retries: int = 3, backoff: float = 0.5) -> requests.Session:
    """构造带重试的 requests.Session"""
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "crossref-ref-fetcher/0.1 (mailto:YOUR_EMAIL@EXAMPLE.COM)"
    })
    return session

# ------------------------------------------------------------------------
# 2. 核心函数
# ------------------------------------------------------------------------
def fetch_references(doi: str, session: requests.Session | None = None) -> list[dict] | None:
    """
    给定 DOI，向 Crossref API 请求并返回 reference 列表（可能为空 list），失败返回 None
    """
    if session is None:
        session = make_session()
    url = f"https://api.crossref.org/works/{doi}"
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("reference", [])
        logger.warning("DOI %s 请求失败，HTTP %s", doi, resp.status_code)
    except Exception as exc:
        logger.error("DOI %s 请求异常：%s", doi, exc)
    return None

def save_references(title: str, refs: list[dict], out_dir: Path | str) -> Path:
    """
    将参考文献列表保存到指定目录，文件名用 title，返回文件路径
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = sanitize_filename(title) or "untitled"
    fpath = out_dir / f"{fname}.json"
    with fpath.open("w", encoding="utf-8") as fp:
        json.dump(refs, fp, ensure_ascii=False, indent=2)
    return fpath

def process_metadata_file(
    meta_json: Path | str,
    out_dir: Path | str,
    sleep_seconds: float = 0.0,
    overwrite: bool = False
) -> tuple[int, int, int]:
    """
    批量读取元数据文件（字段含 doi + title），抓取并保存参考文献
    返回 (成功数, 跳过数, 失败数)
    """
    session = make_session()
    records = json.loads(Path(meta_json).read_text(encoding="utf-8"))
    success = skip = fail = 0

    for rec in records:
        doi = rec.get("DOI"); title = rec.get("title")
        if not (doi and title):
            logger.warning("缺少 DOI 或 title，跳过：%s", rec)
            skip += 1
            continue

        outfile = Path(out_dir) / f"{sanitize_filename(title)}.json"
        if outfile.exists() and not overwrite:
            logger.info("已存在，跳过：%s", outfile.name)
            skip += 1
        else:
            logger.info("抓取 DOI=%s  (%s)", doi, title[:60])
            refs = fetch_references(doi, session)
            if refs is not None:
                save_references(title, refs, out_dir)
                logger.info("✔ 保存 %s (%d 条)", outfile.name, len(refs))
                success += 1
            else:
                logger.error("✖ 抓取失败：%s", doi)
                fail += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)

    return success, skip, fail

# ------------------------------------------------------------------------
# 3. CLI 入口
# ------------------------------------------------------------------------
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="批量抓取 Crossref 参考文献并保存为 JSON",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    p.add_argument("-m","--meta_json", default=r"Reference\doi_metadata.json",help="包含 doi+title 字段的 JSON 文件路径")
    p.add_argument("-o", "--out-dir", default=r"Reference\crossref_ref",
                   help="保存 reference 的目录")
    p.add_argument("--sleep", type=float, default=0.0,
                   help="每次请求后 sleep 秒数，防止限流")
    p.add_argument("--overwrite", action="store_true",
                   help="已存在同名文件则覆盖")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="输出详细日志 (DEBUG)")
    return p

if __name__ == "__main__":
    args = _build_argparser().parse_args()
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    s, sk, f = process_metadata_file(
        meta_json=args.meta_json,
        out_dir=args.out_dir,
        sleep_seconds=args.sleep,
        overwrite=args.overwrite
    )
    logger.info("完成：成功=%d，跳过=%d，失败=%d", s, sk, f)
