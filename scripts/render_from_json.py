# -*- coding: utf-8 -*-
"""用已有 report.json 重新渲染 HTML + 图，不调用 LLM。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jinja2  # noqa: E402
from generate import BASE, KICKER, render, make_mobile  # noqa: E402

for arg in sys.argv[1:]:
    d = Path(arg).resolve()
    data = json.loads((d / "report.json").read_text(encoding="utf-8"))
    report = data["report"]
    seg = report.get("segment") or "senior"
    meta = {"id": d.name, "date": "2026-10-28", "duration": "9",
            "brand": "擅长研究所", "segment": seg, "kicker": KICKER.get(seg, "")}
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(BASE / "templates")), autoescape=True)
    html = env.get_template("report.html").render(report=report, meta=meta)
    (d / "report.html").write_text(html, encoding="utf-8")
    ok, how = render(d / "report.html", d)
    if not ok:
        ok, how = render(d / "report.html", d)
    if ok:
        make_mobile(d / "report.png")
    print(d.name, ok, how)
