# -*- coding: utf-8 -*-
"""只重新渲染已有报告（不调用 LLM）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import BASE, render, make_mobile  # noqa: E402

dirs = sys.argv[1:] or [str(d) for d in (BASE / "out" / "customers").iterdir() if d.is_dir()]
for d in dirs:
    p = Path(d).resolve()
    html = p / "report.html"
    if not html.exists():
        print("skip", p)
        continue
    ok, how = render(html, p)
    if ok:
        make_mobile(p / "report.png")
    print(p.name, ok, how,
          (p / "report.png").stat().st_mtime_ns if (p / "report.png").exists() else None)
