#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 questions.json + interests.json 导出成一份人读的问卷清单。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
D = BASE / "data"
Q = json.loads((D / "questions.json").read_text(encoding="utf-8"))
INT = json.loads((D / "interests.json").read_text(encoding="utf-8"))

groups = {g["id"]: g for g in INT["groups"]}
fields = INT["fields"]
SCALE = ["从不", "很少", "有时", "经常", "总是"]
MOD = {"profile": "背景", "talent": "才能", "value": "价值观",
       "passion": "热情", "open": "开放题", "check": "校验"}
TYPE = {"choice": "单选", "likert": "5 点量表", "ranking": "排序",
        "multi": "多选", "open": "填空", "check_likert": "5 点量表"}

out = []
out.append("# 10 · 问卷清单（v1.2）\n")
out.append(f"> 共 **{Q['counts']['total']} 题**：3 道背景 + 45 道计分/校验，预计 **10–12 分钟**。")
out.append("> 机器可读版：`data/questions.json`；本文件用于审题和往问卷平台录入。\n")

# 结构总览
out.append("## 0. 结构总览\n")
out.append("| 模块 | 题号 | 题数 | 作用 |")
out.append("|---|---|---|---|")
out.append("| 背景 | P1–P3 | 3 | 决定报告版本（探索/转型/重构） |")
out.append("| 才能 | Q1–Q18 | 18 | 6 个才能簇 × 3 题 |")
out.append("| 价值观 | Q19–Q30 | 12 | 4 组 × 3 题 |")
out.append("| 热情 | Q31–Q39 | 9 | 100 行业 → 20 → 10 → 5 → 2 → 细分×2 |")
out.append("| 开放题 | Q40–Q42 | 3 | 报告原文引用 |")
out.append("| 校验 | C1–C3 | 3 | 防乱答 |")
out.append("")

# profile
out.append("## 1. 背景题（不计分）\n")
for q in Q["profile"]:
    out.append(f"**{q['id']}**（{TYPE.get(q['type'],q['type'])}）｜{q['stem']}")
    for o in q.get("options", []):
        out.append(f"- {o['key']}．{o['text']}")
    if q.get("type") == "date":
        out.append("- 日期选择（年 / 月 / 日）→ 自动排星座")
    out.append("")

out.append("---\n")
out.append("## 2. 才能（Q1–Q18，18 题）\n")
out.append("> 6 个簇：思考 / 创造 / 连接 / 执行 / 探索 / 稳定。前 6 题是情境四选一，后 12 题是 5 点量表。\n")
for q in Q["questions"]:
    if q["module"] != "talent":
        continue
    out.append(f"**{q['id']}**（{TYPE.get(q['type'],q['type'])}）｜{q['stem']}")
    if q["type"] == "choice":
        for o in q["options"]:
            out.append(f"- {o['key']}．{o['text']}")
    elif q["type"] == "likert":
        out.append(f"- 量表：{' / '.join(SCALE)}")
    out.append("")

out.append("---\n")
out.append("## 3. 价值观（Q19–Q30，12 题）\n")
out.append("> 4 组：成就成长 / 自由自主 / 关系贡献 / 安全稳定。\n")
for q in Q["questions"]:
    if q["module"] != "value":
        continue
    out.append(f"**{q['id']}**（{TYPE.get(q['type'],q['type'])}）｜{q['stem']}")
    if q["type"] == "choice":
        for o in q["options"]:
            out.append(f"- {o['key']}．{o['text']}")
    elif q["type"] == "ranking":
        out.append("- 排序项：" + " / ".join(i["text"] for i in q["items"]))
    elif q["type"] == "multi":
        out.append("- 选项（限选 %d）：" % q["max_pick"] + "、".join(o["text"] for o in q["options"]))
    out.append("")

out.append("---\n")
out.append("## 4. 热情（Q31–Q38，8 题）\n")
out.append("> 按书里的方法做了五轮收敛：**100 → 20 → 10 → 5 → 1 → 细分**。\n")
for q in Q["questions"]:
    if q["module"] != "passion":
        continue
    tag = TYPE.get(q["type"], q["type"])
    dyn = q.get("dynamic")
    out.append(f"**{q['id']}**（{tag}）｜{q['stem']}")
    if dyn == "all_fields":
        out.append(f"- 从 {len(fields)} 个行业里选，最多 {q['max_pick']} 个，按 14 组展示：\n")
        for g in INT["groups"]:
            names = [f["name"] for f in fields if f["group"] == g["id"]]
            out.append(f"  - **{g['name']}**：{'、'.join(names)}")
    elif dyn == "picked20":
        out.append("- 选项 = 你在 Q31 选中的 20 个行业，最多留 10 个")
    elif dyn == "picked10":
        out.append("- 选项 = 你在 Q32 留下的 10 个，最多留 5 个")
    elif dyn == "picked5":
        out.append("- 选项 = 你在 Q33 留下的 5 个，最多选 2 个")
    elif dyn == "subs":
        out.append(f"- 选项 = 你选中的那个行业下面的细分小行业，最多选 {q['max_pick']} 个")
    elif q["type"] == "choice":
        for o in q["options"]:
            out.append(f"- {o['key']}．{o['text']}")
    elif q["type"] == "likert":
        out.append(f"- 量表：{' / '.join(SCALE)}")
    out.append("")

out.append("---\n")
out.append("## 5. 开放题（Q40–Q42，3 题）\n")
for q in Q["questions"]:
    if q["module"] != "open":
        continue
    out.append(f"**{q['id']}**｜{q['stem']}（限 {q['max_chars']} 字，可语音）\n")

out.append("---\n")
out.append("## 6. 校验题（C1–C3，不计分）\n")
for q in Q["questions"]:
    if q["module"] != "check":
        continue
    out.append(f"**{q['id']}**（{TYPE.get(q['type'],q['type'])}）｜{q['stem']}")
    if q["type"] == "choice":
        for o in q["options"]:
            out.append(f"- {o['key']}．{o['text']}")
    out.append("")

out.append("---\n")
out.append("## 7. 计分方式\n")
out.append("| 模块 | 计分 |")
out.append("|---|---|")
out.append("| 才能 | 簇分 = 100 ×（0.30 × 情境命中率 + 0.70 × 量表均值） |")
out.append("| 价值观 | 组分 = 100 ×（0.40 × 情境命中率 + 0.35 × 排序得分率 + 0.25 × 勾选率） |")
out.append("| 热情 | 行业分：入选 40 / 留 10 强 65 / 留 5 强 85 / 深耕 100；细分由 Q35、Q39 决定 |")
out.append("| 岗位匹配 | 0.65 × 能力匹配 + 0.35 × 行业匹配（封顶 95） |")
out.append("| 校验 | C1 注意力、C2 反向题、C3 重复题，任一不过标记「可疑」 |")
out.append("")

(BASE / "docs" / "10_问卷清单.md").write_text("\n".join(out), encoding="utf-8")
print("written", len(out), "lines")
