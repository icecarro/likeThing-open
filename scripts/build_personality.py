#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成性格问卷（24 题，MBTI 四维）。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
P = json.loads((BASE / "data" / "personality.json").read_text(encoding="utf-8"))

qs = []
for it in P["items"]:
    qs.append({"id": it["id"], "module": "personality", "type": "likert", "stem": it["stem"]})
qs.append({"id": "O1", "module": "open", "type": "open", "max_chars": 500,
           "stem": "最后，还有什么想补充的？喜欢的事、最近的难处、特别想做的事，随便写。"})

data = {
    "questions": qs,
    "meta": {
        "kicker": "PERSONALITY · 性格底色",
        "title": "你的性格底色",
        "line1": "24 道题，约 3 分钟。",
        "line2": "结果是你的 MBTI 四维倾向，用来给擅长与行业加一层权重。",
        "note": "不是贴标签，是解释你为什么在某些环境里更累。",
    },
}
tpl = (BASE / "templates" / "questionnaire.html").read_text(encoding="utf-8")
html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
out = BASE / "问卷" / f"02_性格问卷_{len(qs)}题.html"
out.write_text(html, encoding="utf-8")
print(f"生成 {out} ({len(qs)} 题)")
