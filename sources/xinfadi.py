# -*- coding: utf-8 -*-
"""
北京新发地 · 分品种水果批发价
==============================
接口：POST http://www.xinfadi.com.cn/getPriceData.html
无反爬，只需 Referer + X-Requested-With + 普通 UA。请求体是 form-urlencoded：

    limit=5000&current=1&prodName=&pubDateStartTime=YYYY-MM-DD&pubDateEndTime=YYYY-MM-DD

为什么用它：
    农业农村部全国口径只有 6 种水果（富士苹果/巨峰葡萄/香蕉/菠萝/西瓜/鸭梨），
    **没有橘子**。新发地每天 88 条左右水果报价，蜜桔/叶桔/金秋砂糖桔/爱媛都在，
    正好补上「橘子」这个缺口，同时能给出苹果/香蕉/西瓜的多品种综合价。

三条硬约束（见 sources/variety_map.py）：
    1. 品种名一律走白名单映射，映射不到就不计入（并在 stats 里留名备查）；
    2. 单位是元/斤，统一 ×2 转元/公斤；unitInfo 既不是「斤」也不是空 → 跳过；
    3. 同一品种同日多条（不同产地/规格）→ 取中位数，避免极端规格拉偏。

一次请求可以覆盖 4 天区间（返回体按 pubDate 分组），所以 52 周历史只需 52 次请求。
"""

import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests

from sources import variety_map

URL = "http://www.xinfadi.com.cn/getPriceData.html"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Referer": "http://www.xinfadi.com.cn/priceDetail.html",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
TIMEOUT = 25
RETRY = 2
TOL_DAYS = 3                 # 某周目标日没有报价时，最多往前找 3 天
MAX_WORKERS = 6              # 别打太急，新发地没有明确限流但礼貌一点

_local = threading.local()


def _sess():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        _local.s = s
    return s


def fetch_range(start, end, limit=5000):
    """拉 [start, end] 区间的原始报价行（全部品类）。失败抛异常。"""
    payload = {"limit": limit, "current": 1, "prodName": "",
               "pubDateStartTime": start, "pubDateEndTime": end}
    last = None
    for i in range(RETRY + 1):
        try:
            r = _sess().post(URL, data=payload, timeout=TIMEOUT)
            j = r.json()
            return j.get("list") or []
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
    raise RuntimeError("新发地 %s~%s 请求失败（%s）" % (start, end, last))


def aggregate(rows):
    """
    把一天的原始行聚合成品类价。

    返回 ({key: {"price": 中位数, "n": 品种条数}}, {未映射品种名: 出现次数})
    """
    bucket = {}
    unmapped = {}
    for r in rows:
        if r.get("prodCat") != "水果":
            continue
        name = r.get("prodName") or ""
        key = variety_map.classify(name)
        if not key:
            if name:
                unmapped[name] = unmapped.get(name, 0) + 1
            continue

        unit = (r.get("unitInfo") or "").strip()
        if unit not in ("斤", ""):
            continue                     # 「箱」「公斤」等口径不一致，不猜
        try:
            price = float(r.get("avgPrice"))
        except (TypeError, ValueError):
            continue
        if price <= 0 or price > 500:
            continue
        # 新发地报的是元/斤（unitInfo 为空的实测也是斤价），统一 ×2 转元/公斤
        kg = round(price * 2, 2)
        bucket.setdefault(key, []).append(kg)

    out = {}
    for key, prices in bucket.items():
        out[key] = {"price": round(statistics.median(prices), 2), "n": len(prices)}
    return out, unmapped


def _date_of(row):
    return (row.get("pubDate") or "")[:10]


def day_snapshot(target, rows=None):
    """
    取 target 当天（找不到就往前 3 天内最近一天）的品类聚合价。
    返回 (实际日期, {key: price})；完全没数据返回 (None, {})。
    """
    if rows is None:
        start = (datetime.strptime(target, "%Y-%m-%d")
                 - timedelta(days=TOL_DAYS)).strftime("%Y-%m-%d")
        rows = fetch_range(start, target)
    by_date = {}
    for r in rows:
        d = _date_of(r)
        if d:
            by_date.setdefault(d, []).append(r)

    for d in sorted(by_date, reverse=True):
        agg, _ = aggregate(by_date[d])
        if agg:
            return d, {k: v["price"] for k, v in agg.items()}
    return None, {}


def _grid(last_date, weeks):
    d0 = datetime.strptime(last_date, "%Y-%m-%d")
    return [(d0 - timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(weeks - 1, -1, -1)]


def collect(weeks=52, log=print):
    """
    抓新发地水果，返回与 agri_national.collect 同构的结构：
        {"dates": [...], "latest": ..., "series": {显示名: {...}}, "stats": {...}}
    """
    today = datetime.now().strftime("%Y-%m-%d")
    latest, snap = day_snapshot(today)
    if not latest:
        raise RuntimeError("新发地最近 4 天都没有水果报价")
    log("  最新报价日 %s，当日映射到 %d 个品类（%s）"
        % (latest, len(snap), "/".join(variety_map.display_of(k) for k in snap)))

    dates = _grid(latest, weeks)
    # 最新一天已经有了，其余并发补
    todo = [d for d in dates if d != latest]

    results = {latest: snap}
    unmapped_all = {}
    errors = []

    def work(d):
        start = (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=TOL_DAYS)).strftime("%Y-%m-%d")
        rows = fetch_range(start, d)
        by_date = {}
        for r in rows:
            dd = _date_of(r)
            if dd:
                by_date.setdefault(dd, []).append(r)
        for dd in sorted(by_date, reverse=True):
            agg, unm = aggregate(by_date[dd])
            if agg:
                return d, dd, {k: v["price"] for k, v in agg.items()}, unm
        return d, None, {}, {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for d, actual, snap2, unm in ex.map(work, todo):
            if actual:
                results[d] = snap2
            else:
                errors.append(d)
            for k, v in unm.items():
                unmapped_all[k] = unmapped_all.get(k, 0) + v

    series = {}
    for rule in variety_map.RULES:
        key = rule["key"]
        values = [results.get(d, {}).get(key) for d in dates]
        series[rule["display"]] = {
            "category": rule["category"],
            "values": values,
            "obs": len([v for v in values if v is not None]),
        }

    log("  52 周网格命中 %d 周（缺 %d 周，含节假日停报）"
        % (len(dates) - len(errors), len(errors)))

    return {
        "dates": dates,
        "latest": latest,
        "series": series,
        "stats": {
            "weeks_requested": weeks,
            "weeks_hit": len(dates) - len(errors),
            "weeks_missing": sorted(errors),
            "unmapped": sorted(unmapped_all.items(), key=lambda x: -x[1])[:40],
        },
    }
