# -*- coding: utf-8 -*-
"""八字 / 五行 / 称骨（文化参考，不作为科学依据）。

输入：公历生日 1984-11-16 + 出生小时 0-23
输出：农历、四柱、五行分布、缺失、称骨重量、适合的行业方向
"""
from datetime import date
import re

try:
    from lunardate import LunarDate
except Exception:  # pragma: no cover
    LunarDate = None

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_WX = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
           "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
BRANCH_WX = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
             "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}

# 袁天罡称骨：年（60 甲子）、月（12）、日（30）、时（12），单位：钱
YEAR_W = [12, 9, 6, 7, 12, 5, 9, 8, 7, 8, 15, 9, 16, 8, 8, 19, 12, 6, 8, 7, 5, 15, 6, 16,
          15, 7, 9, 12, 10, 7, 15, 6, 5, 14, 14, 9, 7, 7, 9, 12, 8, 7, 13, 5, 14, 5, 9, 17,
          5, 7, 12, 8, 8, 6, 19, 6, 8, 16, 10, 6]
MONTH_W = [6, 7, 18, 9, 5, 16, 9, 15, 18, 8, 9, 5]
DAY_W = [5, 10, 8, 15, 16, 15, 8, 16, 8, 16, 9, 17, 8, 17, 10, 8, 9, 18, 5, 15,
         10, 9, 8, 9, 15, 18, 7, 8, 16, 6]
HOUR_W = [16, 6, 7, 10, 9, 16, 10, 8, 8, 9, 6, 6]

WX_DIRECTION = {
    "木": {"name": "木", "industries": "教育、文化出版、农林园艺、家具木作、医药、公益",
           "trait": "生长、规划、长期主义"},
    "火": {"name": "火", "industries": "能源电力、电子、餐饮、传媒演艺、美业、互联网",
           "trait": "表达、传播、爆发力"},
    "土": {"name": "土", "industries": "房地产建筑、农业、仓储物流、管理咨询、陶瓷",
           "trait": "承载、稳定、信用"},
    "金": {"name": "金", "industries": "金融、机械制造、法律、五金、军警、审计",
           "trait": "规则、切割、决断"},
    "水": {"name": "水", "industries": "贸易物流、旅游、水产、咨询、数据、流动性行业",
           "trait": "流动、信息、变通"},
}

WEIGHT_BAND = [
    (0, 30, "偏轻", "传统上认为早年靠自己，贵人和资源要主动争取，不适合等。"),
    (31, 42, "中轻", "传统上认为靠手艺和积累，三十岁后开始稳，忌频繁换道。"),
    (43, 52, "中", "传统上认为中年后起势，适合在一条线上做深，忌多头下注。"),
    (53, 62, "中重", "传统上认为一生有起伏但总体向上，适合承担大项目。"),
    (63, 200, "偏重", "传统上认为责任重、压力大，适合做组织里的顶梁柱。"),
]


def _jdn(y, m, d):
    a = (14 - m) // 12
    y2 = y + 4800 - a
    m2 = m + 12 * a - 3
    return d + (153 * m2 + 2) // 5 + 365 * y2 + y2 // 4 - y2 // 100 + y2 // 400 - 32045


def _pillar(stem_i, branch_i):
    return STEMS[stem_i % 10] + BRANCHES[branch_i % 12]


def parse_date(s):
    """兼容 1984-11-16 / 1984/11/16 / 1984.11.16 / 1984年11月16日 / 19841116。"""
    t = str(s)
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", t)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    digits = re.sub(r"\D", "", t)
    if len(digits) == 8:
        return int(digits[:4]), int(digits[4:6]), int(digits[6:])
    raise ValueError(f"无法识别日期：{s}")


def analyze(birth: str, hour: int = 0, calendar: str = "solar"):
    """calendar: solar（阳历）或 lunar（阴历）。阴历会先转成公历再算。"""
    y, m, d = parse_date(birth)
    cal = str(calendar or "solar").lower()
    if cal in ("lunar", "b", "阴历", "农历") and LunarDate is not None:
        # 用户填的是农历，先转公历
        sd = LunarDate(y, m, d).toSolarDate()
        y, m, d = sd.year, sd.month, sd.day
    solar = date(y, m, d)
    if LunarDate is not None:
        ld = LunarDate.fromSolarDate(y, m, d)
        ly, lm, lday = ld.year, ld.month, ld.day
    else:  # 退化为公历，精度下降
        ly, lm, lday = y, m, d

    # 年柱：以农历年计（简化，未按立春换年）
    y_idx = (ly - 4) % 60
    year_p = _pillar(y_idx % 10, y_idx % 12)
    y_stem = y_idx % 10
    # 月柱：正月为寅
    m_branch = (lm + 1) % 12
    m_stem = (y_stem * 2 + lm + 1) % 10
    month_p = _pillar(m_stem, m_branch)
    # 日柱：JDN 锚定 1984-02-02 甲子
    d_idx = (_jdn(y, m, d) + 49) % 60
    day_p = _pillar(d_idx % 10, d_idx % 12)
    # 时柱：23–1 为子
    h_branch = ((hour + 1) // 2) % 12
    h_stem = (d_idx % 10 * 2 + h_branch) % 10
    hour_p = _pillar(h_stem, h_branch)

    chars = year_p + month_p + day_p + hour_p
    wx = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for ch in chars:
        if ch in STEM_WX:
            wx[STEM_WX[ch]] += 1
        elif ch in BRANCH_WX:
            wx[BRANCH_WX[ch]] += 1
    total = sum(wx.values()) or 1
    missing = [k for k, v in wx.items() if v == 0]
    strongest = max(wx, key=wx.get)
    weakest = min(wx, key=wx.get)

    weight = (YEAR_W[y_idx] + MONTH_W[(lm - 1) % 12] + DAY_W[(lday - 1) % 30] + HOUR_W[h_branch])
    band = next((b for b in WEIGHT_BAND if b[0] <= weight <= b[1]), WEIGHT_BAND[-1])

    return {
        "solar": f"{y:04d}-{m:02d}-{d:02d} {hour:02d}:00",
        "lunar": f"{ly}年{'闰' if False else ''}{lm}月{lday}日 {BRANCHES[h_branch]}时",
        "pillars": [year_p, month_p, day_p, hour_p],
        "bazi": " ".join([year_p, month_p, day_p, hour_p]),
        "wuxing": wx,
        "wuxing_pct": {k: round(v / total * 100) for k, v in wx.items()},
        "missing": missing,
        "strong": strongest,
        "weak": weakest,
        "weight": weight,
        "weight_text": f"{weight // 10}两{weight % 10}钱" if weight >= 10 else f"{weight}钱",
        "weight_band": band[2],
        "weight_note": band[3],
        "directions": [WX_DIRECTION[k]["industries"] for k in ([strongest] + missing)[:3]],
        "strong_info": WX_DIRECTION[strongest],
        "missing_info": [WX_DIRECTION[k] for k in missing],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(analyze("1984-11-16", 0), ensure_ascii=False, indent=2))
