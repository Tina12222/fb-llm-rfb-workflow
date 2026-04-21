#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_missing.py  ——  对齐 ReadCube & Crossref，并补齐缺失的 DOI
既可 import 使用，也可直接通过 CLI 运行。
"""
import json
import logging
import unicodedata
import re
import argparse
from pathlib import Path
from typing import Tuple, Optional, List

# ---------- 模块级 Logger ----------
logger = logging.getLogger(__name__)

# ---------- 工具函数 ----------

def normalize_filename(filename: str) -> str:
    """
    对文件名进行归一化处理：
    1. 使用 Unicode 归一化（NFKC）；
    2. 将所有符号（标点、特殊字符、下划线等）替换为单个空格；
    3. 将文本转为小写；
    4. 将连续空格合并为一个，并去除首尾空格。
    """
    nfkd = unicodedata.normalize("NFKC", filename)
    no_symbols = re.sub(r'[_\W]+', ' ', nfkd)
    lowercased = no_symbols.lower()
    cleaned = re.sub(r'\s+', ' ', lowercased).strip()
    return cleaned


def load_json_file(path: Path) -> dict:
    """加载 JSON 文件并返回解析后的数据"""
    return json.loads(path.read_text(encoding='utf-8'))


def save_json_file(path: Path, data) -> None:
    """将数据保存为 JSON 文件"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def extract_num_from_label(text: str) -> Optional[str]:
    """
    从各种复杂的 key/label 中提取参考文献序号：
      1) refNN / citNN / bibNN / crNN / rNN
      2) e_1_2_... 类型 —— 取倒数第二个数字
      3) 其他 —— 取最后一个数字
    返回去掉前导零的十进制字符串，匹配不到返回 None。
    """
    s = (text or '').strip()
    if not s:
        return None

    patterns = [
        r'(?<![A-Za-z0-9_])(?:ref|cit)[_-]?(\d+)(?![A-Za-z0-9_])',
        r'(?<![A-Za-z0-9_])(?:bib)[_-]?(\d+)(?![A-Za-z0-9_])',
        r'(?<![A-Za-z0-9_])(?:cr)[_-]?(\d+)(?![A-Za-z0-9_])',
        r'(?<![A-Za-z0-9_])(?:r)[_-]?(\d+)(?![A-Za-z0-9_])',
    ]
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            return str(int(m.group(1)))

    if re.fullmatch(r'[eE](?:_\d+)+', s):
        nums = re.findall(r'\d+', s)
        if len(nums) >= 2:
            return str(int(nums[-2]))

    all_nums = re.findall(r'\d+', s)
    return str(int(all_nums[-1])) if all_nums else None

# ---------- 核心处理函数 ----------

def update_doi_in_file(
    read_cube_path: Path,
    crossref_path: Path,
    output_path: Path
) -> bool:
    """
    对单个 ReadCube JSON 补全 DOI：
      - load 两份 JSON
      - 若所有引用已有 DOI，直接跳过并复制
      - 长度相等时：一一对应索引补全
      - 否则：构建序号映射，用 label 对齐
      - 保存到 output_path
    返回 True 表示本次有 DOI 补全，否则 False。
    """
    try:
        cube = load_json_file(read_cube_path)
        cref = load_json_file(crossref_path)
    except Exception as e:
        logger.error("加载文件失败: %s | %s — %s", read_cube_path, crossref_path, e)
        return False

    refs_cube: List[dict] = cube.get('references', [])
    if not isinstance(cref, list):
        logger.error("crossref 文件 %s 格式应为 list", crossref_path)
        return False

    # 前提：检查是否所有引用都已有 DOI
    missing = [r for r in refs_cube if not (r.get('doi') or '').strip()]
    if not missing:
        logger.info("所有引用都已有 DOI，跳过补全 → %s", read_cube_path.name)
        # 直接复制原文件
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_json_file(output_path, cube)
        return False

    updated = False
    # 1) 若长度相等，使用索引一对一补全
    if len(refs_cube) == len(cref):
        for idx, (ref_item, cref_item) in enumerate(zip(refs_cube, cref)):
            doi_cube = (ref_item.get('doi') or '').strip()
            doi_cref = (cref_item.get('DOI') or '').strip()
            if not doi_cube and doi_cref:
                ref_item['doi'] = doi_cref
                updated = True
                logger.debug("Direct 补 DOI idx=%d DOI=%s", idx, doi_cref)
    else:
        # 2) 长度不等时，使用 label + 正则 提取序号映射补全
        cref_map: dict = {}
        for item in cref:
            num = extract_num_from_label(item.get('key', ''))
            if num:
                cref_map[num] = item

        for ref_item in refs_cube:
            num = extract_num_from_label(ref_item.get('label', ''))
            if not num:
                continue
            cref_item = cref_map.get(num)
            if not cref_item:
                logger.debug("编号 %s 在 crossref 中无匹配", num)
                continue
            doi_cube = (ref_item.get('doi') or '').strip()
            doi_cref = (cref_item.get('DOI') or '').strip()
            if not doi_cube and doi_cref:
                ref_item['doi'] = doi_cref
                updated = True
                logger.debug("Patch 补 DOI num=%s DOI=%s", num, doi_cref)

    # 保存结果
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_json_file(output_path, cube)
    except Exception as e:
        logger.error("保存文件失败: %s — %s", output_path, e)
        return False

    if updated:
        logger.info("✔ 已补 DOI → %s", output_path.name)
    else:
        logger.info("＝ 无需补 DOI → %s", output_path.name)
    return updated


def process_folders(
    read_cube_folder: Path,
    crossref_folder: Path,
    output_folder: Path,
    prefix_length: int = 30
) -> Tuple[int, int, int]:
    """
    遍历 read_cube_folder 下所有 JSON，与 crossref_folder 对齐并补 DOI，结果存于 output_folder。
    返回 (done, skip, miss)：
      done = 实际补全的文件数
      skip = 全部已有 DOI 的文件数
      miss = 未匹配或错误的文件数
    """
    rc_folder = Path(read_cube_folder)
    cr_folder = Path(crossref_folder)
    out_folder = Path(output_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    rc_files = sorted(rc_folder.glob("*.json"))
    cr_files = sorted(cr_folder.glob("*.json"))
    if len(rc_files) != len(cr_files):
        logger.warning("readcube 数量 %d, crossref 数量 %d 不匹配", len(rc_files), len(cr_files))

    # 构建 crossref 按前缀索引
    cr_index: dict = {}
    for p in cr_files:
        key = normalize_filename(p.name)[:prefix_length]
        if key in cr_index:
            logger.warning("前缀冲突: %s 对应 %s 和 %s", key, cr_index[key].name, p.name)
        else:
            cr_index[key] = p

    done = skip = miss = 0
    for rc_p in rc_files:
        key = normalize_filename(rc_p.name)[:prefix_length]
        cr_p = cr_index.get(key)
        if not cr_p:
            logger.warning("未找到匹配 crossref: %s", rc_p.name)
            miss += 1
            continue
        out_p = out_folder / rc_p.name
        try:
            changed = update_doi_in_file(rc_p, cr_p, out_p)
            if changed:
                done += 1
            else:
                skip += 1
        except Exception as e:
            logger.error("处理 %s 错误: %s", rc_p.name, e)
            miss += 1

    return done, skip, miss

# ---------- CLI 入口 ----------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="对齐 ReadCube & Crossref 并补 DOI",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument(
        "-i", "--readcube",
        default=r"Reference\read_cube_ref",
        help="ReadCube JSON 目录"
    )
    p.add_argument(
        "-j", "--crossref",
        default=r"Reference\crossref_out",
        help="Crossref JSON 目录"
    )
    p.add_argument(
        "-o", "--output",
        default=r"Reference\aligned_ref",
        help="输出 JSON 目录"
    )
    p.add_argument("-p", "--prefix", type=int, default=30, help="前缀长度")
    p.add_argument("-v", "--verbose", action="store_true", help="DEBUG 模式")
    return p

if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s: %(message)s")
    done, skip, miss = process_folders(Path(args.readcube), Path(args.crossref), Path(args.output), args.prefix)
    print(f"补全: {done}，跳过: {skip}，错误: {miss}")
