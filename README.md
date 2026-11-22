# 擅长的事 · 职业方向测评（开源版）

> 一份把「我不知道自己能做什么」变成「3 条可投的岗位 + 90 天怎么开始」的开源测评工具。
> 78 题，10 分钟，输出 9 段报告（长图 + PDF）。

**如果你是一个 AI**：先读 [AI_RUNBOOK.md](AI_RUNBOOK.md)，里面是可直接执行的命令、输入格式和验收判据。本文件是给人看的。

---

## 它是什么

| 是什么 | 不是什么 |
|---|---|
| 一套可本地运行的问卷 + 评分 + 报告生成流水线 | 在线 SaaS（没有托管服务，数据不出本机） |
| 100 个行业 → 20 → 10 → 5 → 2 的收敛算法 | 心理诊断工具（不做临床判断） |
| 报告含「岗位代价」和 90 天验证 | 保证就业/涨薪的产品 |

**这张表说明**：它是工具，不是服务；结论可复现，跑在自己电脑上 🍀

## 三分钟跑通

```bash
# 1. 环境
pip install -r requirements.txt

# 2. 用示例答案生成一份报告（离线引擎，不需 API key）
python scripts/generate.py --answers inbox/demo.json --id DEMO --mbti ISTJ --birth 1992-03-10 --engine offline

# 3. 看结果
# out/DEMO/report.png  （长图）
# out/DEMO/report.pdf  （PDF）
```

> 离线引擎会打印一段「质检」提示（缺形态、缺价格等），那是**内容质量改进项**，不影响报告生成；`--engine llm` 时通常能通过。

想要更强的内容质量，加 `--engine llm`（需环境变量 `DEEPSEEK_API_KEY`）。

## 目录结构

| 路径 | 内容 |
|---|---|
| `问卷/` | 三份 HTML 问卷（主 51 题 / 性格 25 题 / 命理 2 题）与合并版 78 题 |
| `data/questions.json` | 题库与计分定义 |
| `data/interests.json` | 100 个行业 + 406 个细分 |
| `data/personality.json` | MBTI 24 题 |
| `data/zodiac.json` | 星座权重（文化参考） |
| `data/jobs.json` / `jobs_curated.json` / `jobs_gen.json` | 手工岗位、精选岗位、自动生成岗位 |
| `data/business.json` / `business_fields.json` | 生意方向库 |
| `scripts/` | 评分、生成、渲染、问卷服务、邮件、数据抓取 |
| `templates/` | 报告与问卷模板（Jinja2 / 原生 JS） |
| `prompts/` | LLM 分析提示词 |
| `docs/` | 设计文档、话术、验证卡、SOP |

**这张表说明**：问答数据、行业库、岗位库、模板全部是纯文本，改一个 JSON 就能改产品 🌿

## 数据流

```
三份问卷（浏览器本地，localStorage 存草稿）
        ↓ 提交
scripts/server.py 收答案 → out/customers/<手机号>/answers.json
        ↓
scripts/generate.py（rule-based 或 LLM）→ report.json
        ↓
templates/report.html + Jinja2 → report.html
        ↓
headless Edge 截图 + PDF → report.png / report.pdf
```

## 算法要点

1. **能力**：18 道情境题 → 6 个能力簇（思考/探索/创造/执行/连接/稳定）
2. **行业漏斗**：100 选 20 → 10 → 5 → 2，再各选一个细分
3. **岗位匹配**：`能力 55% + 行业 45%`，同分时手工岗位优先
4. **处境**：按年龄+状态+目标判 7 种处境（学生/重返职场/转行/升职/副业/创业/探索），决定语气与推荐侧重
5. **性格**：MBTI 只解释、不排序，权重约 15%
6. **命理**：八字五行 + 称骨，**文化参考，不参与排序**

## 报告长什么样

9 段：结论 → 能力与交叉结论 → 命理（文化参考）→ 取舍 → 领域地图 → 岗位 + 生意 → 误区 → 90 天验证 → 宏观环境。

示例见 `out/_samples/`（运行 demo 后生成）。

## 合规与边界

- 不做心理诊断，不出临床结论
- 命理部分仅文化参考，不做预测、不承诺改变运势
- 不承诺「一定找到工作」「保证涨薪」
- 本仓库不含任何真实客户数据；示例答案均为自造

## License

MIT。商用请自行评估当地法规与平台规则。
