# -*- coding: utf-8 -*-
"""每天抓一次笔记数据，追加到 out/metrics.csv（标题/日期 + 5 个指标）。"""
import csv
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(r"D:\python\pythonProject\LikeThing")
PROFILE = BASE / ".edge_profile"
CSV = BASE / "out" / "metrics.csv"
KEYS = ["浏览", "评论", "点赞", "收藏", "分享"]

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(user_data_dir=str(PROFILE), channel="msedge",
        headless=False, no_viewport=True, args=["--start-maximized"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://creator.xiaohongshu.com/new/note-manager", wait_until="domcontentloaded", timeout=60000)
    time.sleep(6)

    cards = page.evaluate("""() => [...document.querySelectorAll('div')]
      .map(e => (e.innerText||'').trim())
      .filter(t => t.length > 20 && t.length < 300 && /2026-\\d{2}-\\d{2}/.test(t))""")

    rows, seen = [], set()
    for c in cards:
        lines = [s.strip() for s in c.split("\n") if s.strip()]
        # 找到「标题 / 日期 / 5 个数字」的结尾
        m = re.search(r"\n(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\n((?:\d+\n?){5})$", c + "\n")
        if not m:
            continue
        title = lines[lines.index(m.group(1)) - 1] if m.group(1) in lines else lines[0]
        if title in seen:
            continue
        seen.add(title)
        nums = [int(x) for x in re.findall(r"\d+", m.group(2))][:5]
        rows.append((title, m.group(1), nums))

    for t, d, n in rows:
        print(t[:24], d, dict(zip(KEYS, n)), flush=True)

    new = not CSV.exists()
    with CSV.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["抓取时间", "标题", "发布时间"] + KEYS)
        for t, d, n in rows:
            w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), t, d] + n)
    print("WROTE", CSV, "rows", len(rows), flush=True)
    ctx.close()
