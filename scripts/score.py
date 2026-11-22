#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""规则引擎：把 45 题答案算成标签分。

用法：
    python scripts/score.py answers.json          # 输出 scores.json
    python scripts/score.py answers.json --print  # 同时打印可读摘要
    python scripts/score.py --demo                # 跑样例
"""
import json
import sys
import argparse
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from personality import (score_personality, from_type, describe,  # noqa: E402
                         zodiac_of, zodiac_by_key)

BASE = Path(__file__).resolve().parent.parent
QFILE = BASE / "data" / "questions.json"


def load_questions():
    return json.loads(QFILE.read_text(encoding="utf-8"))


def likert_norm(v):
    """1..5 -> 0..1"""
    return max(0.0, min(1.0, (float(v) - 1) / 4))


def score(answers):
    q = load_questions()
    qs = {x["id"]: x for x in q["questions"]}

    talent_hit = defaultdict(int)
    talent_opp = defaultdict(int)
    talent_likert = defaultdict(list)

    value_hit = defaultdict(int)
    value_rank = defaultdict(int)
    value_multi = defaultdict(int)

    domain_likert = defaultdict(list)

    # ---- 才能：情境题 ----
    for qid, item in qs.items():
        if item["module"] != "talent" or item["type"] != "choice":
            continue
        for opt in item["options"]:
            for c in opt.get("scores", {}):
                talent_opp[c] += 1
        chosen = answers.get(qid)
        for opt in item["options"]:
            if opt["key"] == chosen:
                for c in opt.get("scores", {}):
                    talent_hit[c] += 1

    # ---- 才能：频率题 ----
    for qid, item in qs.items():
        if item["module"] == "talent" and item["type"] == "likert":
            if qid in answers:
                talent_likert[item["target"]].append(likert_norm(answers[qid]))

    # ---- 价值观 ----
    for qid, item in qs.items():
        if item["module"] != "value":
            continue
        if item["type"] == "choice":
            chosen = answers.get(qid)
            for opt in item["options"]:
                if opt["key"] == chosen:
                    for g in opt.get("scores", {}):
                        value_hit[g] += 1
        elif item["type"] == "ranking":
            order = answers.get(qid) or []
            points = [4, 3, 2, 1]
            for pos, key in enumerate(order):
                for it in item["items"]:
                    if it["key"] == key and pos < len(points):
                        value_rank[it["group"]] += points[pos]
        elif item["type"] == "multi":
            chosen = set(answers.get(qid) or [])
            for opt in item["options"]:
                if opt["key"] in chosen:
                    value_multi[opt["group"]] += 1

    # ---- 热情：16 组 / 93 个细分方向 ----
    interests = json.loads((BASE / "data" / "interests.json").read_text(encoding="utf-8"))

    def _lst(v):
        return v if isinstance(v, (list, tuple)) else ([v] if v else [])

    grp_sel = {str(x) for x in _lst(answers.get("Q31"))}
    s10 = {str(x) for x in _lst(answers.get("Q32"))}
    s5 = {str(x) for x in _lst(answers.get("Q33"))}
    deep_list = [str(x) for x in _lst(answers.get("Q34"))]
    subs_idx = [str(x) for x in _lst(answers.get("Q35"))]
    level = {"A": -10, "B": 0, "C": 5, "D": 10}.get(str(answers.get("Q36") or "B"), 0)
    inten_list = [likert_norm(answers[k]) for k in ("Q37", "Q38") if k in answers]
    inten = (sum(inten_list) / len(inten_list)) if inten_list else 0.5
    bonus = level + round(10 * (inten - 0.5), 1)

    fscore = {}
    for f in interests["fields"]:
        if f["id"] in deep_list:
            s = 100.0
        elif f["id"] in s5:
            s = 85.0 + bonus
        elif f["id"] in s10:
            s = 65.0 + bonus
        elif f["id"] in grp_sel:
            s = 40.0
        else:
            s = 0.0
        fscore[f["id"]] = round(max(0.0, min(100.0, s)), 1)

    gscore = {}
    for g in interests["groups"]:
        vals = [fscore[f["id"]] for f in interests["fields"] if f["group"] == g["id"]]
        gscore[g["id"]] = max(vals) if vals else 0.0

    subs_by_field = []
    for fid in deep_list:
        df = next((f for f in interests["fields"] if f["id"] == fid), None)
        if not df:
            continue
        subs_by_field.append({"id": fid, "field": df["name"],
                              "subs": list(df.get("subs") or df.get("roles") or [])})

    def _pick(idx_list, group):
        if not group:
            return []
        return [group["subs"][int(i)] for i in idx_list if i.isdigit() and int(i) < len(group["subs"])]

    subs = _pick(subs_idx, subs_by_field[0] if subs_by_field else None)
    idx2 = [str(x) for x in _lst(answers.get("Q39"))]
    subs2 = _pick(idx2, subs_by_field[1] if len(subs_by_field) > 1 else None)

    # ---- 汇总 ----
    clusters = {}
    for c, meta in q["clusters"].items():
        opp = max(1, talent_opp.get(c, 0))
        hit = talent_hit.get(c, 0) / opp
        lk = talent_likert.get(c) or [0.0]
        mean = sum(lk) / len(lk)
        s = 100 * (0.30 * hit + 0.70 * mean)
        spread = (max(lk) - min(lk)) if len(lk) > 1 else 0
        conf = "high" if (spread <= 0.25 and abs(s - 50) >= 15) else "medium"
        clusters[c] = {
            "name": meta["name"],
            "score": round(s, 1),
            "choice_rate": round(hit, 2),
            "likert_mean": round(mean, 2),
            "confidence": conf,
        }

    # ---- 性格（可选）：MBTI 四维，作为才能分的权重导向 ----
    p = score_personality(answers)
    if p is None and answers.get("_mbti"):
        p = from_type(str(answers["_mbti"]))
    if p:
        for c in clusters:
            clusters[c]["score"] = round(
                max(0.0, min(100.0, clusters[c]["score"] + p["bias"].get(c, 0))), 1)

    z = zodiac_of(answers.get("P4") or answers.get("_birth")) or zodiac_by_key(answers.get("_zodiac"))
    if z:
        for c in clusters:
            clusters[c]["score"] = round(
                max(0.0, min(100.0, clusters[c]["score"] + z["bias"].get(c, 0) * 0.5)), 1)

    values = {}
    for g, meta in q["value_groups"].items():
        hit_rate = value_hit.get(g, 0) / 4
        rank_rate = value_rank.get(g, 0) / 16
        multi_rate = value_multi.get(g, 0) / 3
        s = 100 * (0.40 * hit_rate + 0.35 * rank_rate + 0.25 * multi_rate)
        values[g] = {
            "name": meta["name"],
            "purpose": meta["purpose"],
            "score": round(s, 1),
            "choice_hits": value_hit.get(g, 0),
            "rank_points": value_rank.get(g, 0),
            "multi_hits": value_multi.get(g, 0),
        }

    domains = {}
    for d, name in q["domains"].items():
        vals = [gscore[g["id"]] for g in interests["groups"] if g["domain"] == d]
        domains[d] = {"name": name, "score": round(max(vals) if vals else 0.0, 1)}

    groups_out = {g["id"]: {"name": g["name"], "score": round(gscore[g["id"]], 1)}
                  for g in interests["groups"]}
    fields_out = {f["id"]: {"name": f["name"], "group": f["group"],
                            "group_name": next(g["name"] for g in interests["groups"] if g["id"] == f["group"]),
                            "roles": f["roles"], "score": fscore[f["id"]]}
                  for f in interests["fields"]}

    # ---- 质量检查 ----
    checks = {}
    if "C1" in answers:
        checks["C1_attention"] = {"pass": answers["C1"] == "B", "value": answers["C1"]}
    if "C2" in answers:
        strong_thinking = (clusters["thinking"]["likert_mean"] or 0) >= 0.6
        checks["C2_reverse"] = {
            "pass": (not strong_thinking) or float(answers["C2"]) <= 2,
            "value": answers["C2"],
        }
    if "C3" in answers and "Q13" in answers:
        hi = float(answers["C3"]) >= 3
        hi_q13 = float(answers["Q13"]) >= 3
        checks["C3_duplicate"] = {"pass": hi == hi_q13, "value": answers["C3"]}
    quality = "ok" if all(c["pass"] for c in checks.values()) else "suspect"

    order = sorted(values.items(), key=lambda kv: kv[1]["score"], reverse=True)
    top_clusters = sorted(clusters.items(), key=lambda kv: kv[1]["score"], reverse=True)[:3]
    top_domains = sorted(domains.items(), key=lambda kv: kv[1]["score"], reverse=True)[:3]
    top_groups = sorted(groups_out.items(), key=lambda kv: kv[1]["score"], reverse=True)[:4]
    top_fields = sorted(fields_out.items(),
                        key=lambda kv: (kv[1]["score"], 1 if kv[0] in deep_list else 0),
                        reverse=True)[:6]

    return {
        "meta": {"questionnaire": q["version"], "quality": quality, "checks": checks},
        "clusters": clusters,
        "values": values,
        "domains": domains,
        "groups": groups_out,
        "fields": fields_out,
        "deep_field": (deep_list[0] if deep_list else ""),
        "deep_fields": deep_list,
        "subs": subs,
        "subs2": subs2,
        "subs_by_field": subs_by_field,
        "trail": {"q31": len(grp_sel), "q32": len(s10), "q33": len(s5)},
        "top": {
            "talents": [{"key": k, "name": v["name"], "score": v["score"],
                         "confidence": v["confidence"]} for k, v in top_clusters],
            "values": [{"key": k, "name": v["name"], "score": v["score"]} for k, v in order],
            "work_purpose": values[order[0][0]]["purpose"],
            "domains": [{"key": k, "name": v["name"], "score": v["score"]} for k, v in top_domains],
            "groups": [{"key": k, "name": v["name"], "score": v["score"]} for k, v in top_groups if v["score"] > 0],
            "fields": [{"key": k, "name": v["name"], "group_name": v["group_name"],
                        "roles": v["roles"], "score": v["score"]} for k, v in top_fields if v["score"] > 0],
        },
        "open_answers": {k: answers.get(k, "") for k in ("Q40", "Q41", "Q42")},
        "personality": ({**p, "desc": describe(p)} if p else None),
        "zodiac": z,
    }


def demo_answers():
    return {
        "Q1": "B", "Q2": "A", "Q3": "D", "Q4": "A", "Q5": "B", "Q6": "D",
        "Q7": 5, "Q8": 4, "Q9": 3, "Q10": 4, "Q11": 3, "Q12": 2,
        "Q13": 5, "Q14": 4, "Q15": 3, "Q16": 3, "Q17": 2, "Q18": 4,
        "Q19": "A", "Q20": "A", "Q21": "A", "Q22": "A",
        "Q23": ["1", "2", "3", "4"], "Q24": ["1", "2", "3", "4"],
        "Q25": ["1", "2", "3", "4"], "Q26": ["1", "2", "3", "4"],
        "Q27": ["1", "2", "3"], "Q28": [], "Q29": [], "Q30": ["1"],
        "Q31": 3, "Q32": 4, "Q33": 5, "Q34": 1, "Q35": 2,
        "Q36": 2, "Q37": 1, "Q38": 1, "Q39": 3,
        "Q40": "给一个乱成一团的运营数据，两天内理成能看懂的看板，做完很爽。",
        "Q41": "朋友都说找我看简历、帮我梳理职业方向。",
        "Q42": "做一个帮人看清自己的产品。",
        "C1": "B", "C2": 2, "C3": 4,
    }


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("answers", nargs="?", help="answers json")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--print", dest="do_print", action="store_true")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    if args.demo:
        ans = demo_answers()
        out = BASE / "out" / "_demo" / "scores.json"
    else:
        if not args.answers:
            sys.exit("need answers.json or --demo")
        ans = json.loads(Path(args.answers).read_text(encoding="utf-8"))
        out = Path(args.out) if args.out else Path(args.answers).with_name("scores.json")

    result = score(ans)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.do_print or args.demo:
        t = result["top"]
        print(f"质量: {result['meta']['quality']}  {result['meta']['checks']}")
        print("才能 Top3:")
        for x in t["talents"]:
            print(f"  {x['name']:6s} {x['score']:5.1f}  ({x['confidence']})")
        print("价值观排序:")
        for x in t["values"]:
            print(f"  {x['name']:6s} {x['score']:5.1f}")
        print(f"工作目的: {t['work_purpose']}")
        print("领域 Top3:")
        for x in t["domains"]:
            print(f"  {x['name']:8s} {x['score']:5.1f}")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
