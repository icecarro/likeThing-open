#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按行业（100 个）生成生意方向：每个行业 3 个，用它的细分来写，不再共用组模板。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
D = BASE / "data"
INT = json.loads((D / "interests.json").read_text(encoding="utf-8"))

SERVICE = {
    "cost": "低（时间 + 少量工具）",
    "first": "先低价接 1 单，拿到案例",
    "risk": "靠个人信誉，前 3 单最难；回款看客户",
}
CONTENT = {
    "cost": "低（设备和时间）",
    "first": "先更 30 条，看有没有 1 条起量",
    "risk": "前 6 个月大概率没收入；平台规则说变就变",
}
PRODUCT = {
    "cost": "1–5 万（打样、库存、工具）",
    "first": "先做 20 个付费用户",
    "risk": "获客成本高，容易做成自嗨产品",
}

out = {}
for f in INT["fields"]:
    subs = f.get("subs") or f.get("roles") or [f["name"]]
    s0 = subs[0] if subs else f["name"]
    s1 = subs[1] if len(subs) > 1 else s0
    s2 = subs[2] if len(subs) > 2 else s1
    out[f["id"]] = [
        {"name": f"{s0} 服务 / 咨询", "tags": ["thinking", "connecting"],
         "pitch": f"给企业或个人做「{s0}」的诊断与交付，按项目或年费收费。",
         **SERVICE},
        {"name": f"{f['name']} 内容 / 课程", "tags": ["creating", "connecting"],
         "pitch": f"把「{f['name']}」里的经验做成账号、小课或训练营。",
         **CONTENT},
        {"name": f"{s1} 工具 / 产品", "tags": ["thinking", "creating"],
         "pitch": f"把「{s1}」里重复的动作做成模板、工具或小产品，一次做多次卖。",
         **PRODUCT},
    ]

(D / "business_fields.json").write_text(
    json.dumps({"version": "v1.0", "fields": out}, ensure_ascii=False, indent=2), encoding="utf-8")
print("fields", len(out), "ideas", sum(len(v) for v in out.values()))
