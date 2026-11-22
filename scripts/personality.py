# -*- coding: utf-8 -*-
"""MBTI 四维计分 + 对才能分的权重导向。"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
P = json.loads((BASE / "data" / "personality.json").read_text(encoding="utf-8"))

DIM_ORDER = ("EI", "SN", "TF", "JP")
CLUSTERS = ("thinking", "creating", "connecting", "executing", "exploring", "stabilizing")


def score_personality(answers):
    """answers: {"X1":1..5, ...}; 返回 None 表示没做性格题。"""
    got = {k: v for k, v in answers.items() if k.startswith("X") and str(k[1:]).isdigit()}
    if not got:
        return None
    dims = {}
    letters = []
    for d in DIM_ORDER:
        vals = []
        for it in P["items"]:
            if it["dim"] != d or it["id"] not in got:
                continue
            try:
                vals.append((float(got[it["id"]]) - 3) * it["dir"])
            except (TypeError, ValueError):
                continue
        if not vals:
            continue
        raw = sum(vals)
        score = round(raw / (len(vals) * 2) * 100)
        meta = P["dims"][d]
        letter = meta["pos"] if score >= 0 else meta["neg"]
        letters.append(letter)
        dims[d] = {
            "name": meta["name"],
            "letter": letter,
            "word": meta["pos_name"] if score >= 0 else meta["neg_name"],
            "score": score,
            "strength": abs(score),
        }
    if len(letters) < 4:
        return None
    t = "".join(letters)
    return {"type": t, "dims": dims, "bias": bias_of(t), "source": "test"}


def bias_of(t):
    """性格对才能簇的加减分（-6 ~ +7）。"""
    b = {c: 0.0 for c in CLUSTERS}
    e, n, f, j = t[0], t[1], t[2], t[3]
    if e == "E":
        b["connecting"] += 6
    else:
        b["connecting"] -= 4
        b["thinking"] += 4
    if n == "N":
        b["creating"] += 5
        b["exploring"] += 4
    else:
        b["executing"] += 5
        b["stabilizing"] += 3
    if f == "T":
        b["thinking"] += 5
        b["connecting"] -= 2
    else:
        b["connecting"] += 6
        b["thinking"] -= 2
    if j == "J":
        b["executing"] += 5
        b["stabilizing"] += 4
    else:
        b["exploring"] += 5
        b["stabilizing"] -= 3
    return b


def from_type(t):
    """用户直接给类型（如 INTJ）时，合成一个默认强度的结果。"""
    t = (t or "").strip().upper()
    if len(t) != 4 or t[0] not in "EI" or t[1] not in "SN" or t[2] not in "TF" or t[3] not in "JP":
        return None
    dims = {}
    for i, d in enumerate(DIM_ORDER):
        meta = P["dims"][d]
        letter = t[i]
        score = 60 if letter == meta["pos"] else -60
        dims[d] = {"name": meta["name"], "letter": letter,
                   "word": meta["pos_name"] if score > 0 else meta["neg_name"],
                   "score": score, "strength": 60}
    return {"type": t, "dims": dims, "bias": bias_of(t), "source": "manual"}


PHRASE = {    "I": "你从独处里恢复能量，人多了会累",
    "E": "你从人群里获得能量，越聊越有想法",
    "N": "你先看可能性，再回头看细节",
    "S": "你先看事实和细节，再谈可能性",
    "T": "你做决定靠逻辑和利弊",
    "F": "你做决定先看人的感受",
    "J": "你需要确定的计划，讨厌临时变卦",
    "P": "你需要保留余地，讨厌被排满",
}

WORK = {
    "I": "适合能自己掌控节奏、少开会的环境",
    "E": "适合需要主动对外、快速建立关系的环境",
    "N": "适合从 0 到 1、需要判断趋势的位置",
    "S": "适合需要稳、准、可复用的位置",
    "T": "适合能讲道理、看结果的地方，人情味太重的团队你会累",
    "F": "适合有人情味、能感受到意义的地方，纯 KPI 你会耗干",
    "J": "适合目标清晰、能收尾的位置",
    "P": "适合变化快、需要随时调整的位置",
}


Z = json.loads((BASE / "data" / "zodiac.json").read_text(encoding="utf-8"))["signs"]


def zodiac_of(birth):
    """birth 支持 YYYY-MM-DD / MM-DD / YYYYMMDD。"""
    s = str(birth or "").strip()
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 8:
        m, d = int(digits[4:6]), int(digits[6:8])
    elif len(digits) == 4:
        m, d = int(digits[:2]), int(digits[2:4])
    else:
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    md = (m, d)
    for sign in Z:
        a, b = tuple(sign["from"]), tuple(sign["to"])
        if a <= b:
            hit = a <= md <= b
        else:  # 跨年，如摩羯 12/22–1/19
            hit = md >= a or md <= b
        if hit:
            return {**sign, "line": f"太阳落在{sign['name']}：{sign['strength']}；要小心的是，{sign['watchout']}。"}
    return None


def zodiac_by_key(key):
    """按 id / 中文名 / 英文名 指定星座，如 scorpio / 天蝎 / 天蝎座。"""
    k = str(key or "").strip().lower()
    if not k:
        return None
    for sign in Z:
        if k in (sign["id"], sign["name"], sign["name"].replace("座", "")):
            return {**sign, "line": f"太阳落在{sign['name']}：{sign['strength']}；要小心的是，{sign['watchout']}。"}
    return None


def describe(p):
    t = p["type"]
    lines = [PHRASE[c] for c in t]
    works = [WORK[c] for c in t]
    return {
        "type": t,
        "headline": " · ".join(d["word"] for d in p["dims"].values()),
        "lines": lines,
        "work": works,
        "blind": (f"{t} 的人最容易把「自己顺手的方式」当成「所有人都该这样」——"
                  f"这会让你在协作里显得不好相处。报告里的岗位匹配，已经把这一层算进去了。"),
    }
