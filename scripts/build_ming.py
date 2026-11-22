#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第三份问卷：出生年月日 + 时辰（用于八字/五行）。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
Q = json.loads((BASE / "data" / "questions.json").read_text(encoding="utf-8"))
prof = [q for q in Q["profile"] if q["id"] in ("P4", "P5")]

data = {
    "questions": prof,
    "meta": {
        "kicker": "DESTINY · 命理参考",
        "title": "你的出生时间",
        "line1": "2 道题，30 秒。",
        "line2": "用来排八字、五行和称骨，作为报告最后一节的参考。",
        "note": "只是文化参考，不参与岗位排序。",
    },
}
tpl = (BASE / "templates" / "questionnaire.html").read_text(encoding="utf-8")
html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
out = BASE / "问卷" / "03_命理问卷_生日时辰.html"
out.write_text(html, encoding="utf-8")
print(f"生成 {out} ({len(prof)} 题)")
