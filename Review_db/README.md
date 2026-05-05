# Review_db

`Review_db` 用于把收集到的综述论文文本加工成可检索的综述数据库。
核心流程是：

`review_text -> sections -> chunks -> statements/themes -> review_database.pkl/csv`

---

## 1. 功能定位

本目录只保留与“文本处理与检索库构建”直接相关的核心代码：

- `section_sep.py`：按分隔符切分论文为 section
- `chunks_sep.py`：按长度与结构切分 section 为 chunk
- `statement_ex.py`：从 chunk 中抽取结构化 statement（LLM）
- `theme_ex.py`：从 chunk 中抽取结构化 theme（LLM）
- `database.py`：合并 chunk + statement + theme，生成最终数据库
- `main_review.py`：一键串联整个流程（推荐入口）

历史或一次性脚本放在 `archive/`，不参与主流程。

---

## 2. 目录结构

```text
Review_db/
  main_review.py
  section_sep.py
  chunks_sep.py
  statement_ex.py
  theme_ex.py
  database.py
  README.md
  archive/                 # 非核心历史脚本

  review_text/             # 输入：原始综述 txt（每篇一个 txt）
  sections/                # 中间产物：按篇分目录，每目录下 section_*.txt
  chunks/                  # 中间产物：按篇分目录，每目录下 *_chunk*.txt
  statements/              # 中间产物：按篇分目录，*_result.txt
  themes/                  # 中间产物：按篇分目录，*_theme.txt

  review_database.pkl      # 最终结构化数据库
  review_database.csv      # 便于查看/调试的导出
  main_review.log          # 主流程日志
```

说明：
- 所有默认路径都相对 `Review_db` 目录解析，不再依赖绝对路径。

---

## 3. 环境准备

建议在项目根目录准备 Python 环境并安装依赖（至少包含）：

- `pandas`
- `python-dotenv`
- `openai`

如果运行 statement/theme 抽取，需要配置环境变量：

- `OPENAI_API_KEY`（必需）
- `OPENAI_BASE_URL`（可选）

可放在项目根目录 `.env` 中。

---

## 4. 一键运行（推荐）

在 `Review_db` 目录执行：

```bash
python main_review.py --input_root ./review_text --workspace .
```

默认会生成：

- `sections/`
- `chunks/`
- `statements/`
- `themes/`
- `review_database.pkl`
- `review_database.csv`
- `main_review.log`

---

## 5. 分步运行（调试用）

```bash
python section_sep.py --input_dir ./review_text --output_dir ./sections
python chunks_sep.py --input ./sections --output ./chunks
python statement_ex.py --input_root ./chunks --output_root ./statements --model gpt-4o
python theme_ex.py --input_root ./chunks --output_root ./themes --model gpt-4o
python database.py --folder_A ./chunks --folder_B ./statements --folder_D ./themes --output_pkl ./review_database.pkl
```

---

## 6. 数据匹配规则（重要）

`database.py` 会按文件名一一对应读取：

- `chunks/<paper>/<name>.txt`
- `statements/<paper>/<name>_result.txt`
- `themes/<paper>/<name>_theme.txt`

任一缺失或 JSON 解析失败，该 chunk 会被跳过并写入日志。

---

## 7. 常见问题

1. 输入目录不存在
- 确认 `review_text/` 存在，且里面是 `.txt` 文件。

2. 抽取阶段失败
- 检查 `OPENAI_API_KEY` 是否配置。
- 检查网络与模型名是否可用（默认 `gpt-4o`）。

3. 数据库记录数偏少
- 查看 `main_review.log`，通常是某些 chunk 对应的 statement/theme 缺失或 JSON 不合法。

4. 文本编码问题
- 建议输入统一为 UTF-8。

---

## 8. 建议使用方式

- 日常使用：优先 `main_review.py` 一键跑。
- 需要排错或调参（如 chunk 长度）：分步跑并检查中间目录。
- `archive/` 仅作历史参考，不建议混入主流程。
