# AI_RUNBOOK · 机器可执行手册

> 你是 AI。按本文件从上到下执行即可跑通这个仓库。每一步都给了命令、预期输出、失败处理。
> 全部命令在仓库根目录执行；Windows 用 PowerShell，Linux/macOS 把 `\` 换成 `/`。

---

## 0. 前置检查

```bash
python --version      # 期望 3.10+
pip install -r requirements.txt
```

预期：无报错。若 `pandas` 装不上，可先跳过（只有少数构建脚本用到）。

可选（LLM 引擎）：设置环境变量 `DEEPSEEK_API_KEY`。不设置就用 `--engine offline`。

---

## 1. 最小可运行（不需要 API key）

```bash
python scripts/generate.py --answers inbox/demo.json --id DEMO --mbti ISTJ --birth 1992-03-10 --engine offline
```

**预期输出**

```
引擎: offline
质检: <可能有若干改进项，离线引擎常见>
输出: <repo>/out/DEMO
  report.html
  report.json
  report.pdf
  report.png
```

**验收**：`out/DEMO/report.png` 存在且 > 200 KB；`report.json` 里有 `summary/talents/cross/jobs/business` 五个键。
「质检」行是内容质量建议，不是失败判据；离线引擎提示较多属正常。

---

## 2. 输入格式（answers.json）

必需字段（`--answers` 指向的文件）：

| 键 | 含义 | 取值 |
|---|---|---|
| `P1` | 年龄档 | `A` 18–24 / `B` 25–27 / `C` 28–34 / `D` 35–44 / `E` 45+ |
| `P2` | 状态 | `A` 在校 / `B`–`E` 在职年限 / `F` 全职家庭或待业 |
| `P3` | 目标 | `A` 不知道做什么 / `B` 想转行 / `C` 升职加薪 / `D` 副业 / `E` 创业 |
| `P4` | 生日 | `YYYY-MM-DD`（用于星座与八字） |
| `P5` | 出生时辰 | `A`–`L`（子时到亥时，可缺省，缺省按子时） |
| `Q1`–`Q18` | 能力题 | `A`–`D` 或 1–5，见 `data/questions.json` |
| `Q19`–`Q22` | 价值观 | `A`–`D` |
| `Q23`–`Q26` | 价值观排序 | 4 个字母的数组，如 `["3","4","1","2"]` |
| `Q27`–`Q30` | 多选 | 数组 |
| `Q31` | 初选行业 | 20 个行业 id 的数组（`data/interests.json` 的 `fields[].id`） |
| `Q32` | 二选 | 10 个 |
| `Q33` | 三选 | 5 个 |
| `Q34` | 深耕 | 2 个 |
| `Q35`/`Q39` | 两个行业的细分 | 下标数组 |
| `Q36` | 熟悉度 | `A`–`D` |
| `Q37`/`Q38` | 1–5 | 数字 |
| `Q40`–`Q43` | 开放题 | 字符串，越具体越好（报告会引用原话） |
| `C1`–`C3` | 一致性检查 | `A`–`D` / 1–5 |

缺字段不报错，但报告质量会下降；`Q31`–`Q39` 缺失会导致「领域地图」为空。

---

## 3. 生成命令参数

| 参数 | 作用 | 示例 |
|---|---|---|
| `--answers` | 答案文件 | `inbox/a.json` |
| `--demo` | 内置示例答案 | `--demo` |
| `--id` | 输出目录名 | `--id A001` |
| `--engine` | `offline` / `llm` | `--engine llm` |
| `--mbti` | 直接指定性格 | `--mbti INTJ` |
| `--personality` | 性格问卷答案文件 | `--personality inbox/p.json` |
| `--birth` | 生日（覆盖 P4） | `--birth 1990-05-12` |
| `--hour` | 出生小时 0–23 | `--hour 14` |
| `--no-render` | 只生成 JSON，不截图 | `--no-render` |
| `--out-dir` | 自定义输出目录 | `--out-dir out/test` |

---

## 4. 问卷服务（可选）

```bash
python scripts/server.py 8799
```

- 浏览器打开 `http://127.0.0.1:8799/` → 答 78 题 → 提交
- 提交后自动落盘 `out/customers/<手机号>/` 并触发生成
- 需要公网访问时，用任意隧道工具把 8799 暴露出去（仓库不含隧道二进制）

**验收**：`data/records/db.md` 新增一行「已提交」，`out/customers/<手机号>/report.png` 存在。

---

## 5. 重建题库 / 岗位库（可选）

```bash
python scripts/build_questionnaire.py   # 问卷/01_主问卷_51题.html
python scripts/build_personality.py     # 问卷/02_性格问卷_25题.html
python scripts/build_ming.py            # 问卷/03_命理问卷_生日时辰.html
python scripts/build_jobs.py            # data/jobs_gen.json（由 seeds 展开）
python scripts/build_business.py        # data/business_fields.json（按行业生成生意方向）
```

**验收**：对应文件 mtime 更新；`build_jobs.py` 输出 `fields 100 / generated jobs N`。

---

## 6. 抓取数据（可选，小红书创作者后台）

```bash
python scripts/xhs_metrics.py
```

**前置**：`.edge_profile/` 已登录创作者后台（本地浏览器 profile，不入库）。
**验收**：`out/metrics.csv` 追加一行，列为 `抓取时间,标题,发布时间,浏览,评论,点赞,收藏,分享`。
**失败处理**：`wait_for_selector` 超时 → 重新登录该 profile。
**注意**：该脚本只读数据，不发布内容。仓库**不提供**自动发布脚本。

---

## 7. 验收判据（一次跑完自查）

| 项 | 判据 |
|---|---|
| 依赖 | `pip install -r requirements.txt` 无报错 |
| 生成 | `out/<id>/report.png` 与 `.pdf` 均存在；`report.json` 含 `summary/talents/cross/jobs/business` |
| 报告内容 | `report.json` 含 `summary/talents/cross/jobs/business`，`cross` 3–5 条 |
| 问卷 | `问卷/00_完整问卷_78题.html` 能在浏览器打开并提交 |
| 数据抓取 | `out/metrics.csv` 新增行且 8 列 |

---

## 8. 常见故障

| 现象 | 原因 | 修法 |
|---|---|---|
| `Unexpected UTF-8 BOM` | JSON 带 BOM | 读文件用 `utf-8-sig` |
| `KeyError: 'options'` | 日期题没有 options | 导出/渲染时用 `q.get("options", [])` |
| 报告里出现英文占位符 | LLM 带出字段名 | `generate.py` 已内置替换，勿删 |
| `playwright` 报浏览器缺失 | 未装浏览器 | `playwright install chromium` 或改用离线引擎 |
| 中文字体缺字 | 系统无微软雅黑 | 换字体路径或在 Linux 装 `fonts-noto-cjk` |
| 渲染很慢 | Edge 无头启动慢 | 首次 20–40 秒正常 |

---

## 9. 禁止事项（给 AI 的硬约束）

1. 不要在报告里写「保证」「一定能」「最准」「唯一」等绝对化用语（`generate.py` 的 `check()` 会拦）。
2. 不要把命理段当结论——它不参与岗位排序。
3. 不要自动发布到任何内容平台（会触发平台风控，本项目明确不做）。
4. 不要提交 `out/`、`inbox/`、`.edge_profile/`、`data/records/`（含个人数据）。
5. 不要硬编码 API key，只用环境变量。
