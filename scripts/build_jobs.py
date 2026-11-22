#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 seeds.json 展开成岗位库，并把细分写回 interests.json。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
D = BASE / "data"
seeds = json.loads((D / "seeds.json").read_text(encoding="utf-8"))
seeds = {k: v for k, v in seeds.items() if not k.startswith("_")}
interests = json.loads((D / "interests.json").read_text(encoding="utf-8"))

ARCH = {
    "tech":     {"clusters": {"thinking": 0.9, "stabilizing": 0.6, "exploring": 0.6},
                 "a_day": "在「{sub}」方向做技术实现：写方案、做原型、调试、跟需求方对细节。",
                 "entry": "相关专业，或能独立做出一个能看的作品。",
                 "salary": {"e": "8–15K/月", "m": "15–30K/月", "s": "25–50K/月"}},
    "product":  {"clusters": {"thinking": 0.8, "connecting": 0.7, "creating": 0.6},
                 "a_day": "在「{sub}」方向做产品/设计：拆需求、画方案、跟研发或供应商对落地。",
                 "entry": "能独立写一份方案或画一套原型。",
                 "salary": {"e": "8–15K/月", "m": "15–30K/月", "s": "25–45K/月"}},
    "creative": {"clusters": {"creating": 0.9, "exploring": 0.7, "connecting": 0.5},
                 "a_day": "在「{sub}」方向做内容/创作：选题、产出、改稿、看反馈。",
                 "entry": "有 3 个作品，比学历管用。",
                 "salary": {"e": "6–12K/月", "m": "12–25K/月", "s": "20–40K/月"}},
    "sales":    {"clusters": {"connecting": 0.9, "executing": 0.7, "stabilizing": 0.5},
                 "a_day": "在「{sub}」方向做销售/BD：找客户、讲方案、报价、跟进成交。",
                 "entry": "不怕被拒绝，能把话讲清楚。",
                 "salary": {"e": "6–12K/月 + 提成", "m": "12–25K/月 + 提成", "s": "20–40K/月 + 提成"}},
    "ops":      {"clusters": {"executing": 0.9, "connecting": 0.6, "stabilizing": 0.6},
                 "a_day": "在「{sub}」方向做运营/项目：排期、协调、盯数据、处理异常。",
                 "entry": "能把一件事从头跟到尾。",
                 "salary": {"e": "6–10K/月", "m": "10–20K/月", "s": "18–35K/月"}},
    "research": {"clusters": {"thinking": 0.9, "exploring": 0.8, "stabilizing": 0.5},
                 "a_day": "在「{sub}」方向做研究/分析：收集信息、建模型、写结论、给建议。",
                 "entry": "能独立完成一份有结论的报告。",
                 "salary": {"e": "8–15K/月", "m": "15–30K/月", "s": "25–45K/月"}},
    "service":  {"clusters": {"connecting": 0.8, "executing": 0.7, "stabilizing": 0.6},
                 "a_day": "在「{sub}」方向做服务/交付：接需求、处理问题、维护客户关系。",
                 "entry": "耐心、靠谱、能处理突发。",
                 "salary": {"e": "5–9K/月", "m": "9–18K/月", "s": "15–30K/月"}},
    "edu":      {"clusters": {"connecting": 0.8, "thinking": 0.7, "stabilizing": 0.6},
                 "a_day": "在「{sub}」方向做教学/培训：备课、上课、答疑、迭代课程。",
                 "entry": "有一个能讲 1 小时的主题。",
                 "salary": {"e": "6–10K/月", "m": "10–20K/月", "s": "18–35K/月"}},
    "health":   {"clusters": {"executing": 0.8, "connecting": 0.7, "stabilizing": 0.7},
                 "a_day": "在「{sub}」方向做健康服务：评估、处置、记录、随访。",
                 "entry": "相关资质，或跟师学习过。",
                 "salary": {"e": "5–10K/月", "m": "10–20K/月", "s": "18–40K/月"}},
    "finance":  {"clusters": {"thinking": 0.9, "stabilizing": 0.8, "executing": 0.6},
                 "a_day": "在「{sub}」方向做财务/金融：建模、核算、风控、出报告。",
                 "entry": "数字敏感，能独立做完一套账或一个模型。",
                 "salary": {"e": "8–15K/月", "m": "15–30K/月", "s": "25–60K/月"}},
    "supply":   {"clusters": {"executing": 0.9, "stabilizing": 0.7, "thinking": 0.5},
                 "a_day": "在「{sub}」方向做供应链/制造：排产、验货、控成本、处理异常。",
                 "entry": "细致、抗压、会跟供应商打交道。",
                 "salary": {"e": "6–10K/月", "m": "10–20K/月", "s": "18–35K/月"}},
    "mgmt":     {"clusters": {"executing": 0.8, "connecting": 0.8, "thinking": 0.7},
                 "a_day": "在「{sub}」方向做管理：定目标、带人、协调资源、对结果负责。",
                 "entry": "带过 3 人以上，或独立负责过一块业务。",
                 "salary": {"e": "10–18K/月", "m": "18–35K/月", "s": "30–60K/月"}},
}

groups = {g["id"]: g for g in interests["groups"]}
fields = {f["id"]: f for f in interests["fields"]}

# 手写岗位已有的（行业+岗位名），生成时跳过，避免重复
cur_path = D / "jobs_curated.json"
curated = json.loads(cur_path.read_text(encoding="utf-8"))["jobs"] if cur_path.exists() else []

def norm(t):
    return t.replace(" ", "").split("/")[0].split("（")[0]

covered = {(fid, norm(j["title"])) for j in curated for fid in j.get("fields", [])}

jobs = []
skipped = 0
for fid, seed in seeds.items():
    f = fields.get(fid)
    if not f:
        print("skip unknown field", fid)
        continue
    subs = seed.get("subs") or []
    f["subs"] = subs
    g = groups[f["group"]]
    for i, (title, arch, level) in enumerate(seed.get("jobs", [])):
        if (fid, norm(title)) in covered:
            skipped += 1
            continue
        a = ARCH[arch]
        sub = subs[i] if i < len(subs) else (subs[0] if subs else f["name"])
        jobs.append({
            "id": f"g_{fid}_{i}",
            "title": title,
            "industry": f"{g['name']} / {f['name']}",
            "clusters": a["clusters"],
            "domains": [g["domain"]],
            "fields": [fid],
            "a_day": a["a_day"].format(sub=f["name"]),
            "entry": a["entry"],
            "salary": a["salary"][level],
            "path90": [
                f"第 1–2 周：搞清「{sub}」每天到底在做什么，找 3 个人问",
                "第 3–4 周：做一件这个岗位真实会做的事，做出能给人看的东西",
                "第 5–8 周：投 10 家相关公司，或接 1 个小单",
                "第 9–12 周：复盘反馈，决定继续还是换方向",
            ],
            "level": level,
            "source": "gen",
        })

(D / "jobs_gen.json").write_text(
    json.dumps({"version": "v1.0", "jobs": jobs}, ensure_ascii=False, indent=2), encoding="utf-8")
(D / "interests.json").write_text(
    json.dumps(interests, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"fields {len(seeds)}  generated jobs {len(jobs)}  skipped(covered) {skipped}")
print("subs coverage", sum(1 for f in interests['fields'] if f.get('subs')), "/", len(interests['fields']))
