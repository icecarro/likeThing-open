#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 questions.json 嵌进问卷页面，生成可直接打开的 out/questionnaire.html。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
Q = json.loads((BASE / "data" / "questions.json").read_text(encoding="utf-8"))

clean = []
for q in Q.get("profile", []) + Q["questions"]:
    item = {k: q[k] for k in ("id", "module", "type", "stem", "dynamic", "grouped", "tag") if k in q}
    if "max_chars" in q:
        item["max_chars"] = q["max_chars"]
    if "max_pick" in q:
        item["max_pick"] = q["max_pick"]
    if "options" in q:
        item["options"] = [{"key": o["key"], "text": o["text"]} for o in q["options"]]
    if "items" in q:
        item["items"] = [{"key": i["key"], "text": i["text"]} for i in q["items"]]
    clean.append(item)

payload = {"questions": clean, "counts": Q["counts"],
           "meta": {
               "kicker": "YOUR USER MANUAL · 你的使用说明书",
               "title": "你的使用说明书",
               "line1": f"{len(clean)} 道题，约 10–12 分钟。",
               "line2": "最后会得到：3 个你擅长的事、2 个深耕行业、具体岗位方向，以及一份 90 天验证。",
               "note": "这不是心理测试，不出诊断，不承诺结果。",
           }}
INT = json.loads((BASE / "data" / "interests.json").read_text(encoding="utf-8"))
payload["groups"] = INT["groups"]
payload["fields"] = [{"id": f["id"], "name": f["name"], "group": f["group"],
                      "subs": f.get("subs", [])} for f in INT["fields"]]
tpl = (BASE / "templates" / "questionnaire.html").read_text(encoding="utf-8")
html = tpl.replace("__DATA__", json.dumps(payload, ensure_ascii=False))

out = BASE / "问卷" / f"01_主问卷_{len(clean)}题.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"生成 {out}  ({len(clean)} 题, {out.stat().st_size // 1024} KB)")
