# Public Reproduction Repository (RFB Workflow)

## 1) 项目简介
本仓库面向公开复现，包含三条主链路：
- RAG 检索与重排（`RAG/rag_core/`）
- RAG 效果评测（`RAG/evaluation/`）
- 研究假设生成与评估（`Reaearch_Idea/code/`）
- 参考文献构建与匹配（`Reference/scripts/`、`ref_db_match/script/`）

## 2) 统一运行入口（推荐）
从仓库根目录 `D:\CODE` 执行：

```bash
python run_pipeline.py check --dry-run
python run_pipeline.py rag --dry-run
python run_pipeline.py reference --dry-run
python run_pipeline.py idea --dry-run
```

## 3) 目录结构
```text
RAG/rag_core/             # 检索/重排核心
RAG/evaluation/           # 效果评测脚本
Reaearch_Idea/code/       # 背景-灵感-假设-评估更新链路
Reference/scripts/        # 参考文献抓取、对齐、去重、摘要补全
ref_db_match/script/      # 引文索引匹配与回写
prompt_dedup_all/         # 去重后的统一 prompt
docs/                     # 复现说明
```

## 4) 环境安装
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 5) 兼容旧入口
```bash
python RAG/rag_core/main.py --dry-run
python Reference/scripts/ref_main.py --dry-run
python ref_db_match/script/ra_main.py --dry-run
python Reaearch_Idea/code/background.py --dry-run
```

## 6) 配置说明
- 所有路径优先使用项目根目录相对路径。
- 可通过 `.env` 覆盖关键路径（见 `.env.example`）。
- `Reference/scripts/config.yaml` 与 `ref_db_match/script/config.yaml` 现已使用相对路径。

## 7) 复现边界
- 外部 API（OpenAI/ReadCube/Crossref）不可用时，流程会在资源检查阶段给出清晰报错，不伪造结果。
- 大体积索引与私有数据不随仓库提供，需要自行准备。
