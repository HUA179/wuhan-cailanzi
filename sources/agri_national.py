# -*- coding: utf-8 -*-
"""
农业农村部「全国农产品批发市场价格信息系统」· 全国参考价
============================================================
站点：https://pfsc.agri.cn/（Vue SPA，接口无签名、无验证码，带浏览器 UA 即可）

用到的两个接口（分页参数必须放 **JSON body**，放 query 会被忽略）：
    POST /api/farmWeekly/pageList   {"pageNum":1,"pageSize":300}   周报，共 246 期
    POST /api/FarmDaily/list        {"pageNum":1,"pageSize":430}   日报，共 1369 期

一、周报（分品种水果周价，元/公斤）
    每期正文 HTML 里有 5 张表，最后一张是「表5 重点监测的水果价格及变化幅度」，
    表头固定为 产品种类/上周/本周/去年同期/环比/同比。
    这里**不按表序号取**，而是找含有至少 2 个已知水果名的表，
    因为历史期数里表格数量并不总是 5 张。
    → 52 周历史里每一个点都是官方发布的真实周价，historyReal=True。

二、日报（全国均价基准）
    每期正文是结构化好的句子，直接正则抽数：
        fruitsConclusion     → 重点监测的 6 种水果平均价格 X 元/公斤
        vegetablesConclusion → 28 种蔬菜平均价格 X 元/公斤
        animalConclusion     → 猪肉/牛肉/羊肉/鸡蛋/白条鸡
        aquaticConclusion    → 鲫鱼/鲤鱼/白鲢鱼/大带鱼
    → 日均值按「同一周网格」抽样，得到 52 个真实周点。

设计原则（与前三个源保持一致）：
    · 只抽官方明文写出的数字，绝不反推；
    · 某周官方没发（节假日/技术原因）→ 该点 None，不插值；
    · 单位本来就叫元/公斤，不做任何换算。
"""

import re

import requests
from bs4 import BeautifulSoup

BASE = "https://pfsc.agri.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

TIMEOUT = 25
RETRY = 2

# 官方「6 种水果」固定就是这 6 个，缺一个都说明表没解析对
WEEKLY_FRUITS = ["富士苹果", "巨峰葡萄", "香蕉", "菠萝", "西瓜", "鸭梨"]

# 日报里可抽的全国基准：(显示名, 分类, 来源字段)
DAILY_ITEMS = [
    ("全国蔬菜均价", "蔬菜",   "vegetables"),
    ("全国水果均价", "水果",   "fruits"),
    ("全国猪肉",     "肉禽蛋", "animal"),
    ("全国牛肉",     "肉禽蛋", "animal"),
    ("全国羊肉",     "肉禽蛋", "animal"),
    ("全国鸡蛋",     "肉禽蛋", "animal"),
    ("全国白条鸡",   "肉禽蛋", "animal"),
    ("全国鲫鱼",     "水产",   "aquatic"),
    ("全国鲤鱼",     "水产",   "aquatic"),
    ("全国白鲢鱼",   "水产",   "aquatic"),
    ("全国大带鱼",   "水产",   "aquatic"),
]

# 周报里点名的品种 → 中性显示名（加「全国」前缀，避免和新发地的同名品类撞车）
WEEKLY_DISPLAY = {}          # 空表示直接用官方品种名，加前缀见 display_weekly()

_UA_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Origin": BASE,
    "Referer": BASE + "/",
}


def _post(path, body=None, params=None, timeout=TIMEOUT, retries=RETRY):
    """
    POST 接口，返回 content 字典；失败抛异常（不静默返回空）。

    注意这两个接口的分页参数位置**不一致**（实测）：
        /api/farmWeekly/pageList  只认 query params，放 body 会被当成默认第 1 页 10 条
        /api/FarmDaily/list       只认 JSON body，放 query 会被忽略
    所以 params 和 body 分开传，调用方自己决定放哪。
    """
    last = None
    for i in range(retries + 1):
        try:
            r = requests.post(BASE + path, params=params or {}, json=body or {},
                              headers=_UA_HEADERS, timeout=timeout)
            j = r.json()
            if j.get("code") != 200:
                raise RuntimeError("接口返回 code=%s %s" % (j.get("code"), j.get("message")))
            return j.get("content") or {}
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
            if i == retries:
                break
    raise RuntimeError("%s 连续 %d 次失败（%s）" % (path, retries + 1, last))


# ---------------------------------------------------------------- 周报

def _num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", (s or "").replace(",", ""))
    return float(m.group()) if m else None


def parse_fruit_table(html):
    """
    从一期周报正文里抽「表5 水果价格」。

    返回 {品种: 本周价}（元/公斤）。抽不到返回 {}。
    不按表格序号取：只认「表头有 产品种类 + 本周，且行里出现 ≥2 个官方水果名」的表。
    """
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = [[c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                for tr in table.find_all("tr")]
        rows = [r for r in rows if r]
        if len(rows) < 3:
            continue
        head = rows[0]
        if "产品种类" not in head or "本周" not in head:
            continue
        i_name = head.index("产品种类")
        i_cur = head.index("本周")
        hits, out = 0, {}
        for cells in rows[1:]:
            # 表头第二行是「单位（元/公斤） | （%）」，只有 2 格，跳过
            if len(cells) <= max(i_name, i_cur):
                continue
            name = re.sub(r"\s+", "", cells[i_name])
            if name not in WEEKLY_FRUITS:
                continue
            v = _num(cells[i_cur])
            if v is None or v <= 0 or v > 500:
                continue
            out[name] = round(v, 2)
            hits += 1
        if hits >= 2:
            return out
    return {}


def fetch_weekly_rows(page_size=300):
    """
    拉全部周报（一次请求，246 期），返回按日期**降序**的 [{date, content}]。

    只做元数据整理，不解析表5 —— 解析哪几期由 collect() 按需决定，
    避免为了 52 周数据把 246 份 HTML 全嚼一遍。
    """
    content = _post("/api/farmWeekly/pageList", params={"pageNum": 1, "pageSize": page_size})
    rows = content.get("list") or []
    out = []
    for r in rows:
        d = (r.get("weeklyTime") or "")[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            continue
        out.append({"date": d, "content": r.get("content") or ""})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


# ---------------------------------------------------------------- 日报

_RE_AVG = r"(\d+)种(?:蔬菜|水果)平均价格为\s*([\d.]+)\s*元/公斤"
_RE_ITEM = r"([\u4e00-\u9fa5]{2,5}?)(?:平均价格为)?\s*([\d.]+)\s*元/公斤"


def parse_daily_row(row):
    """
    解析一期日报，返回 {字段: {品种: 价格}}。

    正文是官方写好的句子，这里只做「切开句子 + 取数字」，不做任何推断：
        猪肉平均价格为15.76元/公斤，比昨天下降0.6%；牛肉72.81元/公斤…
    """
    out = {"vegetables": {}, "fruits": {}, "animal": {}, "aquatic": {}}

    for field, key in (("vegetablesConclusion", "vegetables"),
                       ("fruitsConclusion", "fruits")):
        txt = row.get(field) or ""
        m = re.search(_RE_AVG, txt) or re.search(r"平均价格为\s*([\d.]+)\s*元/公斤", txt)
        if m:
            groups = m.groups()
            val = groups[-1]
            try:
                out[key]["均价"] = round(float(val), 2)
            except (TypeError, ValueError):
                pass

    for field, key in (("animalConclusion", "animal"), ("aquaticConclusion", "aquatic")):
        txt = row.get(field) or ""
        if "元/公斤" not in txt:
            continue
        for seg in re.split(r"[；;。]", txt):
            m = re.search(_RE_ITEM, seg)
            if not m:
                continue
            name, val = m.group(1), m.group(2)
            name = name.replace("平均价格为", "").strip()
            if not name:
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            if 0 < v < 1000:
                out[key][name] = round(v, 2)
    return out


def fetch_daily_rows(days=430):
    """
    拉最近 N 期日报（接口默认一页 10 条，pageSize 必须写在 body 里）。
    返回按日期升序的 [{date, values}]。
    """
    content = _post("/api/FarmDaily/list", {"pageNum": 1, "pageSize": int(days)})
    rows = content.get("list") or []
    out = []
    for r in rows:
        d = (r.get("daylyDate") or "")[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
            continue
        out.append({"date": d, "values": parse_daily_row(r)})
    out.sort(key=lambda x: x["date"])
    return out


# ---------------------------------------------------------------- 组装

def _grid(last_date, weeks):
    """以最后发布日期为锚，往前取 weeks 个 7 天间隔的日期（升序）。"""
    from datetime import datetime, timedelta
    d0 = datetime.strptime(last_date, "%Y-%m-%d")
    return [(d0 - timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(weeks - 1, -1, -1)]


def _pick(points, target, tol_days=3):
    """
    在 [(date, value)] 里找最接近 target 的一天（±tol_days 内），返回 value 或 None。

    官方周报/日报在节假日会停更，宁可在图上留一个断口，也不把上周的价格
    搬到本周来充当「本周数据」。
    """
    from datetime import datetime
    if not points:
        return None
    t0 = datetime.strptime(target, "%Y-%m-%d")
    best, best_gap = None, None
    for d, v in points:
        try:
            gap = abs((datetime.strptime(d, "%Y-%m-%d") - t0).days)
        except Exception:
            continue
        if gap <= tol_days and (best_gap is None or gap < best_gap):
            best, best_gap = v, gap
    return best


def _covered(parsed_dates, dates, tol=3):
    """网格里每一天是否都能在 ±tol 天内找到一期已解析的周报。"""
    from datetime import datetime
    for d in dates:
        t = datetime.strptime(d, "%Y-%m-%d")
        if not any(abs((datetime.strptime(p, "%Y-%m-%d") - t).days) <= tol
                   for p in parsed_dates):
            return False
    return True


def collect(weeks=52, daily_days=430, log=print):
    """
    抓全国参考数据，返回：
        {
          "dates": [52 个周网格日期],
          "latest": "2026-10-12",
          "series": {显示名: {"category":..., "values":[52]} },
          "stats": {...}
        }
    series 里的 values 与 dates 一一对应，缺数据的位置是 None。
    """
    result = {"dates": [], "latest": None, "series": {}, "stats": {}}

    rows = fetch_weekly_rows()
    if not rows:
        raise RuntimeError("周报接口没返回任何期数")
    latest = rows[0]["date"]
    dates = _grid(latest, weeks)
    result["dates"] = dates
    result["latest"] = latest

    # 从最新往回解析，凑满 52 个网格点就停（历史期数里表格结构可能有变化，
    # 没必要为了窗口外的数据把 246 份 HTML 全解析一遍）
    parsed = []
    # 52 个槽位正常只需约 57 期；留到 82 期是给「历史上有整月停更」留余量。
    # 上限不能省：官方偶尔有 6 周左右漏发，凑不满时会一路嚼到底，纯属浪费时间。
    cap = min(len(rows), weeks + 30)
    for row in rows[:cap]:
        fruits = parse_fruit_table(row["content"])
        if fruits:
            parsed.append({"date": row["date"], "fruits": fruits})
        if len(parsed) >= weeks and _covered([p["date"] for p in parsed], dates):
            break
    parsed.sort(key=lambda x: x["date"])

    log("  周报 %d 期可用，解析 %d 份（%s ~ %s），表5 成功 %d 份"
        % (len(rows), min(cap, len(rows)),
           rows[min(cap, len(rows)) - 1]["date"], rows[0]["date"], len(parsed)))
    if not parsed:
        raise RuntimeError("周报一份都没解析出水果表，格式可能变了")

    # 每个品种一条 (date, price) 序列，再按周网格抽样
    for fruit in WEEKLY_FRUITS:
        pts = [(x["date"], x["fruits"][fruit]) for x in parsed if fruit in x["fruits"]]
        values = [_pick(pts, d) for d in dates]
        result["series"]["全国" + fruit] = {
            "category": "水果",
            "values": values,
            "obs": len([v for v in values if v is not None]),
        }

    # ---- 日报：全国均价基准 ----
    daily = fetch_daily_rows(daily_days)
    log("  日报 %d 期（%s ~ %s）"
        % (len(daily), daily[0]["date"] if daily else "-", daily[-1]["date"] if daily else "-"))

    def day_points(field, name=None):
        pts = []
        for row in daily:
            bucket = row["values"].get(field) or {}
            v = bucket.get("均价") if name is None else bucket.get(name)
            if v:
                pts.append((row["date"], v))
        return pts

    for display, cat, field in DAILY_ITEMS:
        if field in ("vegetables", "fruits"):
            pts = day_points(field)
        else:
            # animal/aquatic 段落里的品种名和显示名对应关系：全国猪肉 → 猪肉
            pts = day_points(field, display.replace("全国", ""))
        values = [_pick(pts, d, tol_days=4) for d in dates]
        result["series"][display] = {
            "category": cat,
            "values": values,
            "obs": len([v for v in values if v is not None]),
        }

    result["stats"] = {
        "weekly_issues": len(rows),          # 站点上总共有多少期
        "weekly_parsed": len(parsed),        # 实际解析成功多少期
        "weekly_span": (parsed[0]["date"], parsed[-1]["date"]) if parsed else None,
        "daily_rows": len(daily),
    }
    return result
