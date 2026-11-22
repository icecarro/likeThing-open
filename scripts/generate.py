#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键出报告：答案 → 打分 → 生成 → 质检 → HTML/长图/PDF。

用法：
    python scripts/generate.py --demo
    python scripts/generate.py --answers answers.json --id A001
    python scripts/generate.py --excel inbox/A001.xlsx --id A001
    python scripts/generate.py --demo --engine llm      # 需要 DEEPSEEK_API_KEY

输出：out/<id>/report.html / report.png / report.pdf / scores.json / report.json
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import jinja2

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from score import score, demo_answers, load_questions  # noqa: E402
from segments import (TEXT, LABELS, KICKER, SUMMARY, PITFALLS,  # noqa: E402
                      EXPERIMENT, EXPERIMENT_NOTE, JOBS_POOL, detect_segment,
                      PERSONA, detect_persona)
from bazi import analyze as bazi_analyze  # noqa: E402

MACRO = json.loads((BASE / "data" / "macro.json").read_text(encoding="utf-8"))["trends"]

_RF = BASE / "data" / "redact.txt"
REDACT = [w.strip() for w in _RF.read_text(encoding="utf-8").splitlines()
          if w.strip() and not w.strip().startswith("#")] if _RF.exists() else []


def redact_text(t):
    """把包含敏感词的分句整段删掉。"""
    if not t or not REDACT:
        return t
    parts = re.split(r"[，。；！？\n]", str(t))
    keep = [p for p in parts if p.strip() and not any(w.lower() in p.lower() for w in REDACT)]
    return "，".join(keep)


def redact_answers(ans):
    out = dict(ans)
    for k in list(out.keys()):
        if isinstance(out[k], str) and len(out[k]) > 15:
            out[k] = redact_text(out[k])
    return out

JOBS = json.loads((BASE / "data" / "jobs.json").read_text(encoding="utf-8"))["jobs"]
for extra in ("jobs_curated.json", "jobs_gen.json"):
    p = BASE / "data" / extra
    if p.exists():
        JOBS += json.loads(p.read_text(encoding="utf-8"))["jobs"]

# 更具体的「一天在干什么」（LLM 扩写过的一版）
_DAY = BASE / "data" / "jobs_day.json"
if _DAY.exists():
    _DAY_MAP = json.loads(_DAY.read_text(encoding="utf-8"))
    for _j in JOBS:
        if _j.get("id") in _DAY_MAP:
            _j["a_day"] = _DAY_MAP[_j["id"]]

CLUSTER_TEXT = {
    "thinking": {
        "headline": "你靠「先想清楚」吃饭",
        "plain": "你能在信息还没成型的时候，先看见它该长什么样。别人看到 20 条零散意见，你看到 3 个分类和 1 个优先级。",
        "use_best": "你最适合的位置，是「别人说不清、需要有人先想明白」的地方：复杂判断、信息密度高的决策、需要拆解和归纳的岗位。",
        "shadow": "你会慢慢变成团队的中控台——所有整理都找你，但整理不进考核。三年后你什么都懂，简历上却没有一件自己的作品。",
    },
    "creating": {
        "headline": "你靠「想到别人没想到的」吃饭",
        "plain": "你对「还有没有别的做法」有一种本能的痒。别人接受现状，你总想改一改。",
        "use_best": "适合从 0 到 1 的位置：新业务、新内容、新品牌。你在有空白的地方最值钱。",
        "shadow": "点子多的人最容易死在执行上。你的硬盘里大概躺着 10 个没做完的方案。",
    },
    "connecting": {
        "headline": "你靠「让人愿意」吃饭",
        "plain": "你能让人愿意多说一句。这不是会说话，是别人在你面前觉得安全。",
        "use_best": "适合所有「靠人成事」的位置：销售、运营、培训、招聘、社群。你的产出不在电脑里，在人身上。",
        "shadow": "你会被消耗在所有人的情绪里。帮完一圈人，晚上发现自己什么都没做成。",
    },
    "executing": {
        "headline": "你靠「把事做完」吃饭",
        "plain": "你是那种「交给他就放心」的人。别人还在讨论，你已经在拆第一步了。",
        "use_best": "适合需要落地和推进的位置：项目、运营、供应链、交付。你是让事情真正发生的那个人。",
        "shadow": "你容易变成团队的免费项目经理——所有杂事最后都落到你头上，却没人给你对应的职级。",
    },
    "exploring": {
        "headline": "你靠「学得快」吃饭",
        "plain": "你对新东西的饥饿感比大多数人强。别人怕陌生，你兴奋。",
        "use_best": "适合变化快、需要快速学习的位置：新业务、增长、研究、独立开发。你学得比谁都快。",
        "shadow": "你容易被「下一个新鲜事」带走。开了很多头，收尾的很少。",
    },
    "stabilizing": {
        "headline": "你靠「待得住」吃饭",
        "plain": "你能在一件事上待得住。这个能力在今天比聪明稀缺。",
        "use_best": "适合需要长期积累的位置：财务、审计、质量、运维、手艺。你的复利在第三年才显现。",
        "shadow": "稳定过头就是不动。你可能会在一个已经不适合的位置上，因为「习惯了」而多待三年。",
    },
}

ENGINE = "offline"

# 证据匹配用的关键词（中文里最简单的语义匹配）
KEYWORDS = {
    "thinking": ["研究", "分析", "规律", "系统", "数据", "逻辑", "拆", "原理", "策略", "模型", "量化"],
    "creating": ["设计", "创作", "化妆", "穿搭", "写", "点子", "拍", "画", "风格", "cos", "做"],
    "executing": ["推进", "落地", "计划", "管理", "执行", "做完", "搞定", "盯"],
    "connecting": ["聊", "帮", "朋友", "团队", "沟通", "带人", "交流", "客户"],
    "exploring": ["学", "新", "试", "旅游", "探索", "陌生", "换", "看海", "全世界"],
    "stabilizing": ["坚持", "长期", "稳定", "反复", "每天", "熬", "积累"],
}
NEGATIVE = ("没有", "很少", "几乎不", "不擅长", "不太", "不懂")


def snippet(text, cluster, width=60):
    """围绕关键词截取上下文，而不是从头硬截。"""
    import re
    kws = KEYWORDS.get(cluster, [])
    parts = [p.strip() for p in re.split(r"[，。；、！？\n]", text) if p.strip()]
    idx = None
    for i, p in enumerate(parts):
        if any(k in p for k in kws):
            idx = i
            break
    if idx is None:
        return text[:78] + ("…" if len(text) > 78 else "")
    best = parts[idx]
    lo, hi, step = idx, idx, 0
    while len(best) < 40 and step < 6:
        step += 1
        if hi + 1 < len(parts):
            hi += 1
            best = best + "，" + parts[hi]
            continue
        if lo - 1 >= 0:
            lo -= 1
            best = parts[lo] + "，" + best
    if len(best) > width:
        best = best[:width] + "…"
    pre = "…" if lo > 0 else ""
    post = "…" if (hi < len(parts) - 1 and len(best) >= width) else ""
    return pre + best + post

PURPOSE_BODY = {
    "成长": "你必须看到自己在变强，否则再高的薪水也留不住你。",
    "自由": "你不能接受被人管死。能让你长期做下去的，是能自己决定怎么做、什么时候做的工作。",
    "看见": "你需要被需要。没有人因为你变好，你会很快失去动力。",
    "安心": "你需要确定性。看不到稳定预期的工作，再有意思你也会焦虑。",
}


# ---------- 读取答案 ----------

def _split_list(v):
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v]
    s = str(v)
    parts = [p for p in re.split(r"[>,，、\s]+", s) if p.strip()]
    return parts


def normalize_answers(raw):
    out = {}
    for k, v in raw.items():
        key = str(k).strip()
        if key == "_mbti":
            out[key] = str(v).strip().upper()
            continue
        if key == "_zodiac":
            out[key] = str(v).strip()
            continue
        if key == "P4":
            out[key] = str(v).strip()
            continue
        if key == "P0":
            out[key] = str(v).strip()
            continue
        if re.match(r"^X\d+$", key):
            try:
                out[key] = int(float(v))
            except (TypeError, ValueError):
                pass
            continue
        if re.match(r"^P\d+$", key):
            out[key] = str(v).strip()[:1].upper()
            continue
        if not re.match(r"^(Q|C)\d+$", key):
            continue
        if key.startswith("Q"):
            qn = int(key[1:])
            if 1 <= qn <= 6 or 19 <= qn <= 22 or key in ("C1",):
                out[key] = str(v).strip()[:1].upper()
            elif 7 <= qn <= 18 or qn in (37, 38):
                out[key] = int(float(v))
            elif qn in (23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 39):
                out[key] = _split_list(v)
            elif qn == 34:
                out[key] = _split_list(v)
            elif qn == 36:
                out[key] = str(v).strip()[:1].upper()
            else:
                out[key] = str(v)
        else:
            try:
                out[key] = int(float(v))
            except Exception:
                out[key] = str(v).strip()[:1].upper()
    return out


def load_from_excel(path):
    import pandas as pd
    df = pd.read_excel(path)
    if df.empty:
        raise SystemExit("Excel 是空的")
    row = df.iloc[-1]
    return normalize_answers(row.to_dict())


# ---------- 离线生成 ----------

def _quote(ans, key, fallback):
    s = (ans.get(key) or "").strip()
    if len(s) < 8:
        return fallback
    return s if len(s) <= 80 else s[:78] + "…"


def match_jobs(scores, pool=None, allow_low=False):
    """只保留和用户所选行业有交集的岗位；低于 55 分不进前三，宁缺毋滥。"""
    cl = scores["clusters"]
    dom = scores["domains"]
    fmap = scores.get("fields", {}) or {}
    user_fields = set(scores.get("deep_fields") or [])
    user_groups = {g["key"] for g in (scores.get("top", {}).get("groups") or [])}

    def blocked_by_weak(j):
        """岗位明显依赖用户很弱的才能 -> 不推。"""
        w = j["clusters"]
        for c, v in w.items():
            sc = cl[c]["score"]
            if v >= 0.8 and sc < 60:
                return True
            if v >= 0.6 and sc < 45:
                return True
        return False

    def base_score(j):
        w = j["clusters"]
        denom = sum(w.values()) or 1
        base = sum(cl[c]["score"] * v for c, v in w.items()) / denom
        if j.get("fields"):
            fscore = max((fmap.get(f, {}).get("score", 0) for f in j["fields"]), default=0)
        else:
            fscore = max((dom.get(d, {}).get("score", 0) for d in j["domains"]), default=0) * 0.6
        return round(min(95, base * 0.5 + fscore * 0.5))

    tier1, tier2 = [], []
    for j in (pool or JOBS):
        if blocked_by_weak(j):
            continue
        s = base_score(j)
        jf = set(j.get("fields") or [])
        if jf & user_fields:
            tier1.append((s, j))
        elif set(j.get("domains") or []) & user_groups:
            tier2.append((s, j))

    key = lambda x: (x[0], 0 if x[1].get("source") == "gen" else 1)
    tier1.sort(key=key, reverse=True)
    tier2.sort(key=key, reverse=True)

    pick = []
    # 每个深耕领域至少一条，保证两个方向都被覆盖
    for df in sorted(user_fields):
        cands = [x for x in tier1 if df in set(x[1].get("fields") or []) and x[0] >= 55]
        if cands:
            best = max(cands, key=key)
            if all(x[1].get("title") != best[1].get("title") for x in pick):
                pick.append(best)
    # 剩余名额按分数补
    for x in tier1:
        if len(pick) >= 3:
            break
        if x[0] >= 55 and all(x[1].get("title") != y[1].get("title") for y in pick):
            pick.append(x)
    pick.sort(key=key, reverse=True)
    if allow_low and len(pick) < 2:
        # 放宽到「领域相关」和低分岗位
        for x in tier2:
            if x[0] >= 55 and all(x[1].get("title") != y[1].get("title") for y in pick):
                pick.append(x)
            if len(pick) >= 3:
                break
        rest = sorted(tier1 + tier2, key=key, reverse=True)
        for x in rest:
            if all(x[1].get("title") != y[1].get("title") for y in pick):
                pick.append(x)
            if len(pick) >= 2:
                break
    if not pick:
        fb = [(base_score(j), j) for j in (pool or JOBS)]
        fb.sort(key=key, reverse=True)
        pick = fb[:2]
    return sorted(pick, key=key, reverse=True)[:3]


BIZ = json.loads((BASE / "data" / "business.json").read_text(encoding="utf-8"))["groups"]
_BIZF = BASE / "data" / "business_fields.json"
BIZ_FIELDS = json.loads(_BIZF.read_text(encoding="utf-8"))["fields"] if _BIZF.exists() else {}
_TO = BASE / "data" / "jobs_tradeoff.json"
TRADEOFF = json.loads(_TO.read_text(encoding="utf-8")) if _TO.exists() else {}
for _j in JOBS:
    if not _j.get("tradeoff") and _j["id"] in TRADEOFF:
        _j["tradeoff"] = TRADEOFF[_j["id"]]


def pick_business(scores, field_id, field_name, sub_name, group_id=None):
    cl = scores["clusters"]
    ideas = list(BIZ_FIELDS.get(field_id or "", [])) or list(BIZ.get(group_id or "", []))
    if not ideas:
        tops = sorted(scores.get("groups", {}).items(), key=lambda kv: kv[1]["score"], reverse=True)
        ideas = list(BIZ.get(tops[0][0], [])) if tops else []

    def fit(i):
        tags = i.get("tags") or []
        return sum(cl[t]["score"] for t in tags) / len(tags) if tags else 0

    out = []
    for i in sorted(ideas, key=fit, reverse=True)[:3]:
        out.append({
            "name": i["name"],
            "pitch": i["pitch"].replace("{field}", field_name).replace("{sub}", sub_name),
            "cost": i["cost"], "first": i["first"], "risk": i["risk"],
            "fit": round(fit(i)),
        })
    return out


def cross_insights(scores, pers, zod, names, field_name, roles, purpose):
    out = []
    if not pers:
        return out
    t = pers["type"]
    d = pers["dims"]
    words = {k: v["word"] for k, v in d.items()}
    # 1 能量
    if t[0] == "I":
        out.append({"title": "你的产出高峰在独处时",
                    "body": "人一多你就掉电，会议对你不是产出，是成本。所以要选「少开会也能交付」的位置——"
                            "这不是社恐，是你的工作方式。"})
    else:
        out.append({"title": "你在人群里充电",
                    "body": "越聊越有想法，但也容易把「聊过」当成「做过」。你需要一个能帮你收尾的人，或者一条硬性的交付线。"})
    # 2 决策
    if t[2] == "T":
        out.append({"title": "你是那个先泼冷水的人",
                    "body": "你做判断靠逻辑和利弊，团队里最先指出问题的人通常是你。这让你判断准，"
                            "但也让人觉得冷——尤其在你对的时候。"})
    else:
        out.append({"title": "你先感受，再判断",
                    "body": "你做决定会先看人的感受，团队愿意跟你说真话。代价是：你容易把别人的情绪当成自己的责任。"})
    # 3 行业 × 性格
    if roles:
        better, worse = roles[0], roles[-1]
        out.append({"title": f"在「{field_name}」里，你更适合做{better}",
                    "body": f"同样是「{field_name}」，{t} 的你在「{better}」这类位置上会比在「{worse}」上更省力。"
                            f"前者吃的是你的{names[0]}，后者吃的是你不多的那部分。"})
    # 4 价值观 × 性格
    if "自由" in purpose and t[0] == "I":
        out.append({"title": "你要的自由，不是不上班",
                    "body": "是「不被打断」。给你一间安静的屋子和一件能自己决定节奏的事，你能干很久；"
                            "天天开会、随时被拉群，再自由你也会想跑。"})
    elif "自由" in purpose:
        out.append({"title": "你要的自由，是「自己说了算」",
                    "body": "你能接受忙，不能接受被安排。所以「结果导向、不打卡」的团队对你比薪资更重要。"})
    return out[:4]


def compose_offline(scores, ans, meta, seg="mid"):
    qs_all = load_questions()["questions"]
    cl = scores["clusters"]
    top = [k for k, _ in sorted(cl.items(), key=lambda kv: kv[1]["score"], reverse=True)[:3]]
    t1, t2, t3 = top
    names = [cl[k]["name"] for k in top]
    vals = scores["values"]
    v_order = [k for k, _ in sorted(vals.items(), key=lambda kv: kv[1]["score"], reverse=True)]
    purpose = vals[v_order[0]]["purpose"]
    doms = [d for d, _ in sorted(scores["domains"].items(), key=lambda kv: kv[1]["score"], reverse=True)[:3]]
    dom_names = [scores["domains"][d]["name"] for d in doms]
    gtop = scores["top"].get("groups") or [{"name": "（没有选领域）", "score": 0}]
    ftop = scores["top"].get("fields") or [{"name": "（没有选细分方向）", "group_name": "", "roles": [], "score": 0}]
    gnames = [g["name"] for g in gtop[:2]]
    fnames = [f["name"] for f in ftop[:3]]
    f1 = ftop[0]
    f1_roles = "、".join(f1.get("roles") or []) or "这个方向里的具体岗位"
    deep_ids = scores.get("deep_fields") or []
    deep_names = [scores["fields"][i]["name"] for i in deep_ids if i in scores.get("fields", {})]
    if not deep_names:
        deep_names = [f1["name"]]
    deep_name = "」和「".join(deep_names)
    subs = scores.get("subs") or []
    subs2 = scores.get("subs2") or []
    subs_by_field = scores.get("subs_by_field") or []
    role_parts = []
    pick_parts = []
    for i, g in enumerate(subs_by_field):
        ss = subs if i == 0 else (subs2 if i == 1 else [])
        if ss:
            pick_parts.append(f"「{g['field']}」里的「{'、'.join(ss)}」")
        roles = (scores.get("fields", {}).get(g["id"], {}) or {}).get("roles") or []
        if roles:
            role_parts.append(f"「{g['field']}」里：{'、'.join(roles)}")
    trail = scores.get("trail") or {}

    # 证据选择：先按语义匹配开放题，匹配不上就用最高分的行为题
    pool = []
    for qid in ("Q40", "Q41", "Q42"):
        txt = (ans.get(qid) or "").strip()
        if len(txt) >= 8:
            pool.append((qid, txt))

    def kw_score(text, c):
        s = sum(text.count(k) for k in KEYWORDS.get(c, []))
        if any(n in text for n in NEGATIVE):
            s -= 3
        return s
    def likert_ev(c):
        cand = [q for q in qs_all if q["module"] == "talent" and q["type"] == "likert" and q.get("target") == c]
        if not cand:
            return "这一项的证据较弱，建议用 7 天实验验证。"
        best = max(cand, key=lambda q: ans.get(q["id"], 0))
        return f"你给这句话打了 {ans.get(best['id'], 0)} 分：『{best['stem']}』"

    used = set()
    evidence = {}
    for c in top:
        best, best_s = None, 0
        for qid, txt in pool:
            if qid in used:
                continue
            s = kw_score(txt, c) - (2 if qid == "Q42" else 0)
            if s > best_s:
                best, best_s = (qid, txt), s
        if best and best_s >= 4:
            used.add(best[0])
            t = snippet(best[1], c)
            evidence[c] = f"你说的：「{t}」"
        else:
            evidence[c] = likert_ev(c)

    talents = []
    for k in top:
        tx = TEXT[seg][k]
        talents.append({
            "name": cl[k]["name"], "score": cl[k]["score"], "confidence": cl[k]["confidence"],
            "plain": tx["plain"], "use_best": tx["use_best"], "shadow": tx["shadow"], "evidence": evidence[k],
        })

    pool_ids = JOBS_POOL.get(seg)
    if seg == "mid":
        pool_jobs = JOBS
    else:
        lv = {"early": "e", "senior": "s"}[seg]
        pool_jobs = [j for j in JOBS if j["id"] in (pool_ids or []) or j.get("level") == lv]
    n_jobs = 3 if seg in ("early", "senior") else 5
    sel = match_jobs(scores, pool_jobs)
    if len(sel) < 2:
        sel = match_jobs(scores, JOBS)   # 池子太窄就放开到全库
    if len(sel) < 2:
        sel = match_jobs(scores, JOBS, allow_low=True)
    jobs = []
    for i, (m, j) in enumerate(sel[:n_jobs]):
        best_c = max(j["clusters"], key=lambda c: cl[c]["score"])
        best_s = cl[best_c]["score"]
        why = f"它最吃「{cl[best_c]['name']}」，你 {best_s} 分，是天然对上的。"
        fld_hit = [f for f in (j.get("fields") or [])
                   if scores.get("fields", {}).get(f, {}).get("score", 0) > 0]
        dom_in = [d for d in j["domains"] if d in doms]
        if fld_hit:
            why += f"而且它就在你选的「{scores['fields'][fld_hit[0]]['name']}」这个细分方向里。"
        elif dom_in:
            dn = scores["domains"][dom_in[0]]["name"]
            why += [f"而且它就在你愿意花时间的「{dn}」里。",
                    f"你花时间最多的「{dn}」，正好是它的主场。",
                    f"它和你常待的「{dn}」是同一个圈子。"][i % 3]
        else:
            why += (f"不过它落在「{scores['domains'][j['domains'][0]]['name']}」，"
                    f"离你最想去的「{dom_names[0]}」有点远——这是你要接受的交换。")
        weak = [(c, cl[c]["score"]) for c in j["clusters"] if cl[c]["score"] < 55]
        if weak:
            c0, s0 = min(weak, key=lambda x: x[1])
            suffix = {
                "early": "——这是你接下来两年最值得练的地方。",
                "senior": "——这个年纪不建议硬补，绕开它。",
                "mid": "——这是你要接受、或者补的短板。",
            }[seg]
            why += f"但它也很吃「{cl[c0]['name']}」，你只有 {s0} 分{suffix}"
        jobs.append({
            "title": j["title"], "industry": j["industry"], "match": m,
            "a_day": j["a_day"], "entry": j["entry"], "salary": j["salary"],
            "tradeoff": j.get("tradeoff", ""),
            "why_you": why, "path90": j["path90"],
        })

    q41 = (ans.get("Q41") or "")
    no_ask = any(n in q41 for n in ("没有", "很少", "几乎不"))
    pitfalls = list(PITFALLS.get(seg, [])) if seg != "mid" else []
    if seg == "mid":
        if not no_ask:
            pitfalls.append({
                "trap": f"把「{names[0]}」用成义务",
                "signal": "所有杂事最后都落到你头上，但没人给你对应的职级或钱。",
                "fix": "下次有人找你，先说「这件事算我哪块工作」，说不清就推掉。",
            })
        if cl["connecting"]["score"] < 60:
            pitfalls.append({
                "trap": "把「不需要人」当成「不擅长人」",
                "signal": "你说几乎没人来找你帮忙。不是你不值钱，是你从没把自己放进需要协作的场景。",
                "fix": "用作品换连接，而不是靠性格换连接：进一个有反馈回路的小圈子，先输出，再认识人。",
            })
        if v_order[0] == "freedom":
            pitfalls.append({
                "trap": "把「自由」当成「没人管」",
                "signal": "你最不能忍的是被管，但自由的反面不是被管，是没人给你兜底。",
                "fix": "先练出一件「不用人盯也能交付」的作品，自由才有议价权。",
            })
        if cl["creating"]["score"] >= 70 and cl["stabilizing"]["score"] < 65:
            pitfalls.append({
                "trap": "开了很多头，收尾的很少",
                "signal": "硬盘里躺着一堆没做完的东西，每一个当时都让你兴奋。",
                "fix": "一次只留一个进行中的项目，其余的写进「以后再说」清单，三个月后再看。",
            })
        pitfalls.append({
            "trap": "把「兴趣」当成「方向」",
            "signal": "你说想转行，但说不出具体做什么岗位。",
            "fix": "先用 7 天验证一个假设，再谈辞职。兴趣只需要付时间，方向要付代价。",
        })
        pitfalls = pitfalls[:3]

    exp = EXPERIMENT[seg]

    self_purpose = purpose.replace("让人", "让我")
    seg_sum = SUMMARY[seg]
    g1 = gnames[0] if len(gnames) > 0 else "你现在做的事"
    g2 = gnames[1] if len(gnames) > 1 else g1
    base_body = (f"这份回答里，出现最多的不是某个行业，而是一种做事方式：{names[0]}（{cl[t1]['score']} 分）、"
                 f"{names[1]}（{cl[t2]['score']} 分）、{names[2]}（{cl[t3]['score']} 分）。"
                 f"你反复花时间的领域是「{g1}」和「{g2}」。"
                 f"把「{names[0]}」放到「{g1}」里，就是你现在最值得试的方向。"
                 f"另外，你的价值观第一位是{vals[v_order[0]]['name']}——你选工作时第一个该问的不是钱，"
                 f"是「这件事能不能{self_purpose}」。")
    if seg == "senior":
        base_body = (f"你被验证过的能力是：{names[0]}（{cl[t1]['score']} 分）、{names[1]}（{cl[t2]['score']} 分）、"
                     f"{names[2]}（{cl[t3]['score']} 分）。你长期投入的领域是「{gnames[0]}」和「{gnames[1]}」。"
                     f"你的价值观第一位是{vals[v_order[0]]['name']}——到这个年纪，它不是「你想要什么」，是「你不愿意再牺牲什么」。")
    if seg == "early":
        base_body = (f"你的回答里，能力倾向已经有了轮廓：{names[0]}（{cl[t1]['score']} 分）、{names[1]}（{cl[t2]['score']} 分）、"
                     f"{names[2]}（{cl[t3]['score']} 分）。你现在愿意花时间的领域是「{gnames[0]}」和「{gnames[1]}」。"
                     f"注意：你的样本还少，这份结论是「假设」，不是「定论」。")
        lows = sorted(((cl[k]["name"], cl[k]["score"]) for k in cl if cl[k]["score"] < 40), key=lambda x: x[1])
        if lows:
            base_body += (f"另外，{'、'.join(n for n, _ in lows[:2])}分数偏低——"
                          f"这不代表你不行，只代表还没练。二十几岁的分数是「现在的你」，不是「以后的你」。")
    summary = {
        "headline": TEXT[seg][t1]["headline"],
        "one_liner": f"你的核心不是某个技能，是「{names[0]} + {names[1]}」的组合。",
        "body": (" ".join(x for x in (seg_sum["opener"], base_body, seg_sum["closer"]) if x)),
    }
    pers = scores.get("personality")
    zod = scores.get("zodiac")
    df0 = scores.get("fields", {}).get(deep_ids[0], {}) if deep_ids else {}
    field0 = df0.get("name") or f1["name"]
    roles0 = df0.get("roles") or f1.get("roles") or []
    group0 = df0.get("group")
    cross = cross_insights(scores, pers, zod, names, field0, roles0, purpose)
    biz = pick_business(scores, deep_ids[0] if deep_ids else "", field0,
                        subs[0] if subs else field0, group0)
    if pers:
        summary["body"] += (f" 你的性格底色是 {pers['type']}——它解释了你为什么用这种方式做事，"
                            f"也解释了你在哪些环境里会累。")
    if pers and zod:
        summary["body"] += (f" 加上{zod['name']}，两套标签其实指向同一件事："
                            f"你要的是掌控感和判断权，最烦被安排。")
    persona_key = detect_persona(ans)
    persona = {"key": persona_key, **PERSONA[persona_key]}
    biz_title = {
        "student": "以后想自己做事的话，先记住这几个方向",
        "returnee": "如果你想用碎片时间做点自己的事",
        "founder": "你的主线：三个可以先验证的生意",
        "side": "如果你想把副业做成第二曲线",
    }.get(persona_key, "如果你更想自己做事")
    summary["body"] += f" 你现在处在「{persona['label']}」——{persona['advice']}"

    compass = {
        "purpose": purpose,
        "body": (f"在四组价值里，你把「{vals[v_order[0]]['name']}」排在最前（{vals[v_order[0]]['score']} 分），"
                 f"「{vals[v_order[1]]['name']}」第二。翻成一句工作目的，就是：{purpose}。"
                 f"{seg_sum['compass']}"
                 f"{PURPOSE_BODY.get({'growth': '成长', 'freedom': '自由', 'relation': '看见', 'security': '安心'}[v_order[0]], '')}"),
        "rank": [{"name": vals[k]["name"], "score": vals[k]["score"]} for k in v_order],
    }

    compass = {
        "purpose": purpose,
        "body": (f"在四组价值里，你把「{vals[v_order[0]]['name']}」排在最前（{vals[v_order[0]]['score']} 分），"
                 f"「{vals[v_order[1]]['name']}」第二。翻成一句工作目的，就是：{purpose}。"
                 f"{PURPOSE_BODY.get({'growth': '成长', 'freedom': '自由', 'relation': '看见', 'security': '安心'}[v_order[0]], '')}"),
        "rank": [{"name": vals[k]["name"], "score": vals[k]["score"]} for k in v_order],
    }

    labels = dict(LABELS[seg])
    if seg == "senior":
        labels["s3_h2"] = "到这个年纪，你<em>不愿意再牺牲</em>什么"
    else:
        labels["s3_h2"] = f"你真正想要的，是<em>{purpose}</em>"

    return {
        "summary": summary,
        "talents": talents,
        "compass": compass,
        "domains_note": (f"100 个行业里你圈了 {trail.get('q31', 0)} 个，收窄到 {trail.get('q32', 0)} 个，"
                         f"再留下 {trail.get('q33', 0)} 个，最后只深耕「{deep_name}」。"
                         f"这不是随便选的——三轮下来还留下的，才是你真正愿意花时间的。"),
        "domains_hint": (("你最想碰的是" + "、".join(pick_parts) +
                          "；对应的具体岗位——" + "；".join(role_parts) + "。")
                         if pick_parts else
                         f"在「{deep_name}」里，用「{names[0]}」的方式做事——落到具体岗位就是：{f1_roles}。"),
        "chosen_field": deep_name,
        "personality": pers,
        "zodiac": zod,
        "cross": cross,
        "business": biz,
        "persona": persona,
        "biz_title": biz_title,
        "subs": subs,
        "subs2": subs2,
        "subs_by_field": subs_by_field,
        "domains": [{"name": g["name"], "score": g["score"]} for g in gtop[:3]],
        "fields": [{"name": f["name"], "group_name": f["group_name"], "roles": f["roles"], "score": f["score"]}
                   for f in ftop[:4]],
        "jobs_hint": (f"如果你想留在「{gnames[0]}」，给上面任意一个岗位加一个领域前缀就行："
                      f"「{jobs[0]['title'] if jobs else '一个具体岗位'}」→「{gnames[0]}方向的{jobs[0]['title'] if jobs else '同一类岗位'}」。"
                      f"能力不变，场景换了。"),
        "jobs": jobs,
        "pitfalls": pitfalls,
        "experiment": exp,
        "experiment_note": EXPERIMENT_NOTE[seg],
        "tags": names + dom_names,
        "labels": labels,
        "segment": seg,
    }


# ---------- LLM 生成 ----------

SYSTEM_PROMPT = (BASE / "prompts" / "system.md")


def compose_llm(scores, ans, meta, seg="mid"):
    import requests
    base = compose_offline(scores, ans, meta, seg)
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("⚠ 没有 DEEPSEEK_API_KEY，回退离线引擎")
        return base
    sys_p = SYSTEM_PROMPT.read_text(encoding="utf-8") if SYSTEM_PROMPT.exists() else "你是职业咨询顾问。"

    pers = scores.get("personality") or {}
    zod = scores.get("zodiac") or {}
    payload = {
        "talents": [{"name": t["name"], "score": t["score"], "confidence": t["confidence"]}
                    for t in base["talents"]],
        "values": {"rank": [v["name"] for v in base["compass"]["rank"]],
                   "purpose": base["compass"]["purpose"]},
        "interests": {"deep": base.get("chosen_field"),
                      "subs": base.get("subs_by_field") or [],
                      "trail": scores.get("trail")},
        "personality": {"type": pers.get("type"),
                        "dims": {k: v["score"] for k, v in (pers.get("dims") or {}).items()}} if pers else None,
        "persona": {"label": (base.get("persona") or {}).get("label"),
                    "focus": (base.get("persona") or {}).get("focus")},
        "zodiac": {"name": zod.get("name"), "keywords": zod.get("keywords")} if zod else None,
        "open_answers": [ans.get("Q40", ""), ans.get("Q41", ""), ans.get("Q42", ""), ans.get("Q43", "")],
        "candidate_jobs": [{"title": j["title"], "match": j["match"]} for j in base["jobs"]],
        "business": [{"name": b["name"], "pitch": b["pitch"]} for b in base.get("business", [])],
        "already_said": {"summary": base["summary"]["body"][:300],
                         "cross": [c["title"] for c in base.get("cross", [])]},
    }
    user = ("这是测评结果，请按 system.md 的分析顺序输出 JSON。\n"
            "顺序必须是：先工作目的（Why）→ 再使用说明书（How）→ 再领域（What）"
            "→ 再 combos（喜欢×擅长，3–5 条，至少 3 条真交叉）→ 用工作目的筛（keep）→ 最后才是岗位。\n"
            "重点：cross 写 3–5 条；jobs 写 2–3 条实现手段，角色名要带\"怎么用才能\"，"
            "至少一条不是打工（自由职业/小生意/内容）；business 写 2–3 条，第一条必须是服务型、先收钱、给具体价格。不要重复 already_said 里的表述。\n"
            + json.dumps(payload, ensure_ascii=False)[:9000])

    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat",
                  "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": user}],
                  "response_format": {"type": "json_object"}, "temperature": 0.8, "max_tokens": 8000},
            timeout=240,
        )
        r.raise_for_status()
        data = json.loads(r.json()["choices"][0]["message"]["content"])
        # 清掉模型可能带出的字段名
        _s = json.dumps(data, ensure_ascii=False)
        for _a, _b in (("candidate_jobs", "候选岗位"), ("already_said", "已写内容"),
                       ("open_answers", "开放题"), ("personality", "性格"), ("zodiac", "星座")):
            _s = _s.replace(_a, _b)
        data = json.loads(_s)
        _s2 = json.dumps(data, ensure_ascii=False)
        for _bad, _good in (("保证", "确保"), ("一定能", "很可能"), ("包就业", "就业方向"),
                            ("最赚钱", "相对赚钱"), ("只有一条路", "其中一条路")):
            _s2 = _s2.replace(_bad, _good)
        data = json.loads(_s2)
    except Exception as e:
        print(f"⚠ LLM 失败（{e}），回退离线引擎")
        return base

    if isinstance(data.get("summary"), dict) and data["summary"].get("body"):
        head = data["summary"].get("headline") or ""
        if any(w in head for w in ("唯一", "只有", "必须", "值得", "应该", "不可能", "注定")):
            head = ""  # 命中禁用词，退回离线标题
        base["summary"]["body"] = data["summary"]["body"]
        if head:
            base["summary"]["headline"] = head
    if isinstance(data.get("cross"), list) and data["cross"]:
        base["cross"] = [c for c in data["cross"] if c.get("title") and c.get("body")][:5]
    if isinstance(data.get("pitfalls"), list) and len(data["pitfalls"]) >= 2:
        base["pitfalls"] = data["pitfalls"][:3]
    # 按原书：喜欢 × 擅长 的组合候选 + 工作目的
    if isinstance(data.get("combos"), list):
        combos = [c for c in data["combos"] if c.get("what") and c.get("result")][:5]
        if combos:
            base["combos"] = combos
    if isinstance(data.get("compass"), dict):
        if data["compass"].get("purpose"):
            base["compass"]["purpose"] = data["compass"]["purpose"]
        if data["compass"].get("body"):
            base["compass"]["body"] = data["compass"]["body"]
    if isinstance(data.get("summary"), dict) and data["summary"].get("one_liner"):
        base["summary"]["one_liner"] = data["summary"]["one_liner"]
    if isinstance(data.get("business"), list):
        bs = [b for b in data["business"] if b.get("name")][:3]
        if bs:
            base["business"] = [{
                "name": b.get("name", ""),
                "form": b.get("form", ""),
                "from_combo": b.get("from_combo", ""),
                "who": b.get("who", ""),
                "deliverable": b.get("deliverable", ""),
                "price": b.get("price", ""),
                "first_money": b.get("first_money", ""),
                "cost": b.get("cost", ""),
                "risk": b.get("risk", ""),
                "first_30_days": b.get("first_30_days", ""),
                "pitch": b.get("pitch", ""),
                "fit": b.get("fit", ""),
            } for b in bs]
    if isinstance(data.get("jobs"), list):
        js = [j for j in data["jobs"] if j.get("title")][:3]
        if len(js) >= 2:
            base["jobs"] = [{
                "title": j["title"],
                "form": j.get("form", "") or "打工",
                "from_combo": j.get("from_combo", ""),
                "industry": "", "salary": "", "match": 0,
                "a_day": j.get("a_day", ""),
                "why_you": j.get("why_you", ""),
                "entry": j.get("entry", ""),
                "tradeoff": j.get("tradeoff", ""),
                "first_step": j.get("first_step", ""),
                "path90": [],
            } for j in js]
            base["jobs_hint"] = ""
    base["engine"] = "llm"
    return base


# ---------- 质检 ----------

def check(report):
    """v3.1 定版校验：结构 + 写法密度。"""
    errs = []
    if not report.get("jobs") or len(report["jobs"]) < 2:
        errs.append("实现手段不足 2 条")
    jobs5 = report.get("jobs") or []
    if jobs5 and not any(j.get("form") and j.get("from_combo") for j in jobs5):
        errs.append("05 的实现手段缺形态(from_combo/form)")
    if jobs5 and all((j.get("form") or "打工") == "打工" for j in jobs5):
        errs.append("05 全是打工形态，缺自由职业/小生意/内容")
    if jobs5 and not all(j.get("tradeoff") for j in jobs5):
        errs.append("05 有路径没写代价")

    biz = report.get("business") or []
    if len(biz) < 2:
        errs.append("06 生意方向不足 2 条")
    if biz:
        if not any((b.get("form") or "") == "服务" for b in biz):
            errs.append("06 没有一条服务型（应先卖后做）")
        if not all(b.get("price") for b in biz):
            errs.append("06 有生意方向没给具体价格")
        if any((b.get("who") or "") in ("所有人", "大家") for b in biz):
            errs.append("06 客户写得太笼统（所有人）")
    for t in report.get("talents", []):
        if not t.get("evidence"):
            errs.append(f"天赋「{t.get('name')}」缺证据引用")
        if not t.get("shadow"):
            errs.append(f"天赋「{t.get('name')}」缺「用错了会怎样」")

    # 定版结构：工作目的 + 喜欢×擅长 组合 + 结论从原话开始
    if not (report.get("compass") or {}).get("purpose"):
        errs.append("缺工作目的（compass.purpose）")
    combos = report.get("combos") or []
    if len(combos) < 3:
        errs.append("喜欢×擅长 组合不足 3 条")
    if combos and not any(c.get("keep") is False for c in combos):
        errs.append("组合里没有一条被工作目的筛掉（缺取舍）")

    body = (report.get("summary") or {}).get("body") or ""
    if body and ("你给" not in body[:40] and "你说的" not in body[:40] and "「" not in body[:40]):
        errs.append("结论第一句不是用户原话")
    if body and "不劝你" not in body and "不做什么" not in body:
        errs.append("结论缺「这份报告不做什么」的边界声明")

    text = json.dumps(report, ensure_ascii=False)
    for w in ("包就业", "保证", "一定能", "最赚钱", "唯一值得", "只有一条路"):
        if w in text:
            errs.append(f"出现禁用词：{w}")
    head = (report.get("summary") or {}).get("headline") or ""
    for w in ("唯一", "只有", "必须", "值得", "应该", "不可能", "注定"):
        if w in head:
            errs.append(f"标题出现收缩词：{w}")
    if len(text) < 1500:
        errs.append("报告太短")
    return errs


# ---------- 渲染 ----------

def render(html_path, out_dir):
    """优先 playwright，其次 Edge/Chrome 无头模式。"""
    png = out_dir / "report.png"
    pdf = out_dir / "report.pdf"
    url = "file:///" + str(html_path).replace("\\", "/").replace(" ", "%20")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 750, "height": 1600})
            pg.goto(url)
            pg.screenshot(path=str(png), full_page=True)
            pg.pdf(path=str(pdf), width="750px", print_background=True)
            b.close()
        return True, "playwright"
    except Exception:
        pass

    exe = None
    for c in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ):
        if Path(c).exists():
            exe = c
            break
    if not exe:
        return False, "未找到浏览器，只输出 HTML"

    shot = out_dir / "_shot.png"
    import tempfile
    profile = tempfile.mkdtemp(prefix="edge_shot_")
    base_args = ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                 "--no-default-browser-check", f"--user-data-dir={profile}"]
    try:
        subprocess.run([exe, *base_args,
                        "--force-device-scale-factor=2", "--window-size=750,9000",
                        f"--screenshot={shot}", url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
        subprocess.run([exe, *base_args, "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", url],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    if not shot.exists():
        return False, "edge 截图失败（没有产出）"
    if shot.exists():
        try:
            from PIL import Image
            im = Image.open(shot).convert("RGB")
            w, h = im.size
            # 裁掉底部空白
            pix = im.load()
            bottom = h
            step = max(1, w // 30)
            while bottom > 10:
                row_white = True
                for x in range(0, w, step):
                    if pix[x, bottom - 1] != (255, 255, 255):
                        row_white = False
                        break
                if not row_white:
                    break
                bottom -= 1
            im.crop((0, 0, w, min(h, bottom + 20))).save(png, optimize=True)
            shot.unlink(missing_ok=True)
        except Exception as e:
            shutil.move(str(shot), str(png))
            return True, f"edge（裁剪失败：{e}）"
    return True, "edge"


def make_mobile(png: Path, width=750):
    """手机版：宽 750 的 JPEG，约 0.8MB，用于页面内直接看。"""
    try:
        from PIL import Image
        im = Image.open(png).convert("RGB")
        w, h = im.size
        if w > width:
            im = im.resize((width, int(h * width / w)), Image.LANCZOS)
        out = png.with_name("report_mobile.jpg")
        im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
        return out
    except Exception as e:
        print("mobile fail", e)
        return None


# ---------- 主流程 ----------

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--answers")
    ap.add_argument("--excel")
    ap.add_argument("--id", default="A000")
    ap.add_argument("--engine", choices=["offline", "llm"], default="offline")
    ap.add_argument("--mbti", help="直接指定性格类型，如 INTJ（不填则从 X1–X24 计算）")
    ap.add_argument("--personality", help="性格问卷导出的 answers.json")
    ap.add_argument("--birth", help="出生年月日，如 1984-03-15（用于星座）")
    ap.add_argument("--zodiac", help="直接指定星座，如 scorpio / 天蝎")
    ap.add_argument("--hour", type=int, help="出生小时 0–23（用于八字）")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--out-dir", help="自定义输出目录（默认 out/<id>）")
    args = ap.parse_args()

    if args.demo:
        ans, pid = demo_answers(), "A000"
    elif args.answers:
        ans, pid = normalize_answers(json.loads(Path(args.answers).read_text(encoding="utf-8"))), args.id
    elif args.excel:
        ans, pid = load_from_excel(args.excel), args.id
    else:
        raise SystemExit("用 --demo / --answers / --excel")

    out = Path(args.out_dir).resolve() if getattr(args, "out_dir", None) else BASE / "out" / pid
    out.mkdir(parents=True, exist_ok=True)

    if getattr(args, "mbti", None):
        ans["_mbti"] = args.mbti.upper()
    if getattr(args, "personality", None):
        pj = json.loads(Path(args.personality).read_text(encoding="utf-8"))
        for k, v in pj.items():
            if str(k).upper().startswith("X"):
                try:
                    ans[str(k).upper()] = int(float(v))
                except (TypeError, ValueError):
                    pass
    if getattr(args, "birth", None):
        ans["P4"] = args.birth
    if getattr(args, "zodiac", None):
        ans["_zodiac"] = args.zodiac

    ans = redact_answers(ans)

    # 命理：先算（阴历先转公历），并把 P4 归一成公历，供星座使用
    bz = None
    cal = str(ans.get("P6") or "A").upper()
    if ans.get("P4"):
        hh = getattr(args, "hour", None)
        if hh is None and ans.get("P5"):
            hh = (ord(str(ans["P5"]).upper()) - 65) * 2
        try:
            bz = bazi_analyze(ans["P4"], int(hh or 0), "lunar" if cal == "B" else "solar")
            if bz:
                ans["_birth_input"] = f"{ans['P4']}（{'阴历' if cal == 'B' else '阳历'}）"
                ans["P4"] = bz["solar"][:10]
        except Exception as e:
            print("⚠ 八字计算失败：", e)

    sc = score(ans)
    (out / "scores.json").write_text(json.dumps(sc, ensure_ascii=False, indent=2), encoding="utf-8")

    seg = detect_segment(ans)
    meta = {"id": pid, "date": "2026-10-28", "duration": "9", "brand": "擅长研究所",
            "segment": seg, "kicker": KICKER[seg]}
    report = compose_llm(sc, ans, meta, seg) if args.engine == "llm" else compose_offline(sc, ans, meta, seg)
    report["bazi"] = bz
    report["birth_input"] = ans.get("_birth_input")

    # 宏观（只取与用户领域相关的 2 条）
    top_groups = [g["key"] for g in (sc.get("top", {}).get("groups") or [])[:3]]
    scored = [(len(set(t["groups"]) & set(top_groups)), i, t) for i, t in enumerate(MACRO)]
    scored.sort(key=lambda x: (-x[0], x[1]))
    mac = [t for s, _, t in scored if s > 0][:3] or MACRO[:3]
    report["macro"] = mac

    errs = check(report)
    (out / "report.json").write_text(
        json.dumps({"report": report, "errors": errs, "engine": args.engine}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(BASE / "templates")), autoescape=True)
    html = env.get_template("report.html").render(report=report, meta=meta)
    (out / "report.html").write_text(html, encoding="utf-8")

    ok, how = (False, "skipped")
    if not args.no_render:
        ok, how = render(out / "report.html", out)
        if not ok:
            time.sleep(2)
            ok, how = render(out / "report.html", out)
        if ok:
            make_mobile(out / "report.png")

    print(f"引擎: {args.engine}")
    print(f"质检: {'通过' if not errs else '; '.join(errs)}")
    print(f"输出: {out}")
    for f in sorted(out.iterdir()):
        print(f"  {f.name}  {f.stat().st_size // 1024} KB")
    if not ok:
        print(f"渲染: {how}")


if __name__ == "__main__":
    main()
