'''
调用大模型来从excel里面的abstract列里面提取研究的theme
'''
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List
from tqdm.asyncio import tqdm_asyncio
import pandas as pd
from openai import AsyncOpenAI, OpenAIError, RateLimitError

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger("rfb-tag")
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    timeout=600
)

###定义模板
TEMPLATE = """
You are a domain expert in redox-flow batteries.  
Your task is to read the *Abstract* below and extract **one** most-representative *Theme* from the allowed lists.

### Allowed Theme labels：
1. Electrode Materials & Engineering
   eg. porous carbon modification, catalytic layer construction, surface functionalization
2. Membrane & Separator Engineering
   eg. ion-selective membranes, proton-conductive enhancements, antifouling surface coatings
3. Electrolyte Formulation & Additives
   eg. concentration optimization, solvent-system tuning, stability-enhancing additives
4. Novel Redox Couples Discovery
   eg. vanadium alternatives, organic quinone systems, metal–ligand complex redox couples
5. Flow-Field & Stack Design
   eg. bipolar plate channel patterns, pressure-drop minimization, modular stack configurations
6. Degradation Mechanisms & Mitigation
   eg. electrode corrosion analysis, membrane fouling suppression, capacity-fade mitigation strategies
7. System-Level Evaluation & Techno-Economics
   eg. system integration modeling, energy-management strategies, cost-sensitivity assessment, TEA/LCA                
8. Other                                  

                                                  
## Guideline：
1. **Output format** – reply with **one** JSON object and nothing else:
   **Example** → `{"theme":"Electrode Materials & Engineering"}`
2. **Label source** – pick each value **exclusively** from its own list
   *Theme → Allowed Theme labels* ;
   if no suitable match exists, use `"Other"`.
3. **Single best match** – when several labels could apply, return the **single most representative / most frequent** one in the abstract.
4. **Normalisation** – map synonyms, abbreviations, or spelling variants to the closest allowed label; if nothing is close enough, fall back to `"Other"`.
5. **Exact text** – keep the chosen label’s spelling, capitalisation, and spacing **exactly** as shown in the allowed lists, and ignore peripheral details such as years, citation counts, page numbers, or funding information.
<|user|>Abstract:\n{abstract}
"""

SYS_PROMPT, USER_PROMPT = TEMPLATE.split("<|user|>", 1)

# ─────────────────── LLM 调用助手 ───────────────────
async def call_llm_async(
    msgs: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
    max_retry: int = 3,
    req_timeout: float = 90,
) -> Dict[str, str]:
    """单条摘要→模型→解析 JSON；失败兜底返回 "Other"。"""

    for attempt in range(max_retry):
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    temperature=0,
                    response_format={"type": "json_object"},
                ),
                timeout=req_timeout,
            )
            content = resp.choices[0].message.content
            return json.loads(content)

        except RateLimitError:
            backoff = 5 * 2 ** attempt
            logger.warning("RateLimit (retry %d/%d) → sleep %.1fs", attempt + 1, max_retry, backoff)
            await asyncio.sleep(backoff)
        except (
            OpenAIError,
            json.JSONDecodeError,
            asyncio.TimeoutError,
            asyncio.CancelledError,
            Exception,  # catch‑all 保险
        ) as e:
            logger.warning("LLM error (retry %d/%d): %s", attempt + 1, max_retry, e)
            await asyncio.sleep(2 ** attempt)

    return {"theme": "Other"}


async def classify_batch_async(
    abstracts: List[str],
    *,
    model: str = "gpt-4o-mini",
    concurrency: int = 10,
) -> List[Dict[str, str]]:
    """批量异步调用，返回标签列表，与 abstracts 顺序一致。"""

    sem = asyncio.Semaphore(concurrency)

    async def _worker(abs_txt: str) -> Dict[str, str]:
        async with sem:
            safe_abs = abs_txt.replace("{", "{{").replace("}", "}}")
            msgs = [
                {"role": "system", "content": SYS_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(abstract=safe_abs)},
            ]
            return await call_llm_async(msgs, model=model)

    tasks = [_worker(a or "") for a in abstracts]

    results = await tqdm_asyncio.gather(
        *tasks,
        desc="Tagging"
    )

    return results


# ────────────────── 公开 API ───────────────────

def extract_theme(
    df: pd.DataFrame,
    *,
    model: str = "gpt-4o-mini",
    concurrency: int = 10,
) -> pd.DataFrame:
    """输入 DataFrame，返回追加 theme列的新 DataFrame。"""

    abstracts = df["abstract"].fillna("").astype(str).tolist()

    try:
        loop = asyncio.get_running_loop()
        # 已在事件循环内（Jupyter / GUI）
        fut = asyncio.ensure_future(
            classify_batch_async(abstracts, model=model, concurrency=concurrency)
        )
        tag_list = loop.run_until_complete(fut)
    except RuntimeError:  # 无事件循环（普通脚本）
        tag_list = asyncio.run(
            classify_batch_async(abstracts, model=model, concurrency=concurrency)
        )

    tag_df = pd.DataFrame(tag_list)
    return pd.concat([df.reset_index(drop=True), tag_df], axis=1)


# ---------------------------------------------------------------------------
# CLI utility
# ---------------------------------------------------------------------------

def _guess_outfile(infile: str) -> str:
    base_name = os.path.splitext(os.path.basename(infile))[0]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{ts}_tag.xlsx"


def main() -> None:
    parser = argparse.ArgumentParser(description="批量抽取 redox‑flow battery 论文的 Theme 标签")
    parser.add_argument(
    "--infile",
    default=r"Reference\dedup_ref_abstract_del.xlsx",
    help="输入 xlsx，需包含 'abstract' 列"
)
    parser.add_argument(
        "--outfile",
        default=r"Reference\theme_tag.xlsx",
        help="输出 xlsx 路径"
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="模型名称，默认 o3-mini")
    parser.add_argument("--conc", type=int, default=10, help="并发任务数，默认 10")
    args = parser.parse_args()

    infile = args.infile
    outfile = args.outfile or _guess_outfile(infile)

    ext = os.path.splitext(infile)[1].lower()
    logger.info("读取输入文件: %s", infile)
    if ext in (".xlsx", ".xls"):
        df_in = pd.read_excel(infile, dtype=str)
    else:
        df_in = pd.read_csv(infile, dtype=str)

    logger.info("共 %d 条记录，开始调用大模型……", len(df_in))
    df_out = extract_theme(df_in, model=args.model, concurrency=args.conc)

    logger.info("写出结果 → %s", outfile)
    out_ext = os.path.splitext(outfile)[1].lower()
    if out_ext in (".xlsx", ".xls"):
        df_out.to_excel(outfile, index=False)
    else:
        df_out.to_csv(outfile, index=False)

    logger.info("完成！🎉")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("用户中断 (Ctrl+C)。")



# ### Allowed Theme labels
# 1. Electrode modification                （电极改性）
# 2. Membrane modification                 （膜改性）
# 3. Electrolyte engineering               （电解液配方 / 添加剂）
# 4. Stack / flow-field design             （堆 / 流道设计）
# 5. System-level analysis                
# 6. Degradation mechanisms & mitigation   
# 7. New chemistry exploration              (全钒外的新活性对、混合体系)
# 8. Modelling & simulation                  (机理、CFD、数据驱动)
# 9. Other                                  （以上均不匹配）

# ### Allowed Method labels 
# A. Wet-Chemical Synthesis & Surface Functionalization       （湿化学合成和表面官能化） 
#        e.g. hydrothermal、sol-gel、in-situ polymerization、chemical grafting      
# B. Thermal Treatment & Phase Engineering                    （热处理和相变工程）       
#        e.g. carbonization、annealing、phase-transition-templating
# C. Plasma & Radiation Activation                                 （等离子体与辐射活化）
#        e.g. O₂-plasma、N₂-plasma、UV-ozone、γ-irradiation
# D. Chemical / Electrochemical Activation                      （化学 / 电化学活性）    
#        e.g. acid-etch、base-activation、electrochemical-conditioning
# E. Structural Shaping & Advanced Manufacturing                （结构设计与高级制造）    
#        e.g. electrospinning、3-D printing、freeze-casting、layer-by-layer
# F. Computational Modeling & Digital Design                         （计算模型与数字设计）
#        e.g. DFT、MD、CFD、ML-screening、system-level-TEA
# G. Other                                                    （以上均不匹配）
