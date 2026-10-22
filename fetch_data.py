# -*- coding: utf-8 -*-
"""
武汉菜篮子 - 数据抓取脚本（多源版）
===================================
数据源（全部为政府公开数据，无需登录）

① 武汉市发改委「价格监测平台」每日价格（主源，每日更新）
   http://58.48.136.167:7600/comparePrice 背后的 JSON 接口
   - queryJBSJData?date=YYYY-MM-DD  → 43 个品种的最高/最低/平均价（元/500克）
   - queryPointList?areaCode=420100 → 28 个监测点（7 家超市 + 集贸市场）
   - queryDataForPoint?pointId=&date= → 单个门店的逐品价格（真实商超价）
   ✅ 支持查询历史日期（回溯一年），因此 52 周走势是**真实历史**，不是模拟

② 武汉市农业农村局「数据发布」（补充品种，每日更新）
   蔬菜批发价（四季美+白沙洲）、水产品批发价、粮油批发价
   → 补足发改委清单里没有的品种（如西洋芹、茼蒿、甲鱼…）

③ 武汉市商务局「生活必需品市场监测」周报（补充肉禽蛋细类）

输出：data.json（与前端结构一致，另加 source / updated / historyReal 等字段）

运行（动静分离）：
    python fetch_data.py --mode=full    # 全量：回溯 52 周真实历史。历史是死数据，
                                        # 只在需要补历史/换季新品种时本地手动跑
    python fetch_data.py --mode=daily   # 增量：只抓今天一个截面，追加到 52 周末尾、
                                        # 淘汰最老一周、重算百分位。默认模式，
                                        # 请求数个位数，云端 Actions 每天跑这个

为什么要分两种：GitHub 的机器在境外，跨国访问武汉发改委的政务网（裸 IP:7600）
极不稳定，52 个历史日期并发去拉必然超时。历史数据本身不会变，每天重爬纯属浪费。

依赖：
    pip install requests beautifulsoup4 pypinyin
"""

import json
import os
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypinyin import lazy_pinyin, Style

# ---------------------------------------------------------------- 配置

FGJ_API = "http://58.48.136.167:7600/prod-api"
FGJ_REFERER = "http://58.48.136.167:7600/comparePrice"
AREA_CODE = "420100"          # 武汉市

NYNCJ_BASE = "https://nyncj.wuhan.gov.cn"
SW_BASE = "https://sw.wuhan.gov.cn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
TIMEOUT = 15                   # 单次请求超时（境外跑 Actions 时政务网偶有丢包，超过 15s 基本没救）
RETRY = 2                      # 重试次数
MAX_WORKERS = 6                # 历史日期并发数（串行 52 周在境外机器上要跑十几分钟）
WEEKS = 52                    # 走势图窗口
DATA_FILE = "data.json"

# 农业农村局栏目：column -> (前端分类, 抓最新几篇)
NYNCJ_SOURCES = [
    {"column": "/zwgk_25/fdzdgknr/snsj/scpfjg/", "category": "蔬菜",   "take": 2},
    {"column": "/zwgk_25/fdzdgknr/snsj/scppfjg/", "category": "水产",   "take": 1},
    {"column": "/zwgk_25/fdzdgknr/snsj/lypfjg/",  "category": "米面粮油", "take": 1},
]
SW_SOURCE = {"column": "/zfxxgk/fdzdgknr/sjfb/jgjczb/", "take": 10}

# 发改委品种 -> 前端分类
FGJ_CATEGORY = {
    "米面粮油": ["中籼米", "早籼米", "晚粳米", "特一粉", "食盐"],
    "肉禽蛋": ["猪排骨", "猪精瘦肉", "猪腿夹肉", "白条鸡", "白条鸭",
               "良种鸡蛋", "鲜牛肉", "鲜羊肉"],
    "水产": ["胖头鱼", "草鱼", "鲫鱼", "鳊鱼"],
    "豆制品": ["豆腐", "千张", "干子"],
}
# 名字归一（发改委叫法 -> 更通用的叫法）
NAME_ALIAS = {
    "良种鸡蛋": "鸡蛋",
    "鲜牛肉": "牛肉",
    "鲜羊肉": "羊肉",
    "胖头鱼": "花鲢（胖头鱼）",
    "猪腿夹肉": "猪腿夹肉",
}

_local = threading.local()


def _sess():
    """每个线程一个 Session，避免共享连接池在多线程下互相干扰。"""
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": HEADERS["User-Agent"], "Referer": FGJ_REFERER})
        _local.s = s
    return s


# ---------------------------------------------------------------- 发改委接口

def fgj_get(path, params=None, retries=None):
    """
    调用发改委平台接口。
    返回 dict = 有响应（可能为空数据）；返回 None = 网络层彻底失败。
    区分这两者是关键：境外 Actions 访问裸 IP:7600 常常直接超时，
    若把超时当成「这天没数据」，探测就会一天天重试，白等好几十分钟。
    """
    n = RETRY if retries is None else retries
    for i in range(n + 1):
        try:
            r = _sess().get(FGJ_API + path, params=params or {}, timeout=TIMEOUT)
            j = r.json()
            if j.get("code") == 200:
                return j.get("data") or {}
            print(f"  [warn] {path} 返回 {j.get('msg')}")
            return {}
        except Exception as e:
            if i == n:
                print(f"  [error] {path} 失败: {type(e).__name__}")
                return None
    return None


def fgj_daily(date_str):
    """某天的每日价格：{品种名: {avg,max,min,unit,spec}}；网络失败返回 None。"""
    data = fgj_get("/business/mrjg/queryJBSJData", {"date": date_str})
    if data is None:
        return None
    rows = ((data.get("jbsjData") or {}).get("data")) or []
    out = {}
    for r in rows:
        try:
            out[r["name"]] = {
                "avg": float(r.get("avg_price")),
                "max": float(r.get("max_price") or 0),
                "min": float(r.get("min_price") or 0),
                "unit": r.get("unit") or "",
                "spec": r.get("spec") or "",
            }
        except (TypeError, ValueError):
            continue
    return out


def fgj_latest_date():
    """
    从今天往前找最近一个有数据的日期。
    一旦遇到网络层失败（返回 None）立刻放弃——说明整条链路不通，
    再往前往后试都是白等。这是 GitHub Actions 跑境外机器时的关键保护。
    """
    d = datetime.now()
    for _ in range(6):
        s = d.strftime("%Y-%m-%d")
        r = fgj_daily(s)
        if r:
            return s
        if r is None:
            print("  [warn] 发改委接口不可达，跳过该数据源")
            return None
        d -= timedelta(days=1)
    return None


def fgj_reachable():
    """快速探测发改委是否可达（1 次请求、8 秒超时）。"""
    try:
        r = _sess().get(FGJ_API + "/business/mrjg/queryJBSJData",
                        params={"date": datetime.now().strftime("%Y-%m-%d")}, timeout=8)
        return r.status_code == 200
    except Exception:
        return False


def fgj_supermarkets():
    """取超市类监测点，按数据覆盖量从多到少排序。"""
    data = fgj_get("/dataStatistics/priceCompare/queryPointList", {"areaCode": AREA_CODE})
    if not data:
        return []
    pts = data.get("pointList") or []
    supers = [p for p in pts if p.get("pointType") == "超市"]
    return supers


def fgj_point_prices(point_id, date_str):
    """单个监测点的逐品价格：{品种名: 价格}"""
    data = fgj_get("/dataStatistics/priceCompare/queryDataForPoint",
                   {"pointId": point_id, "date": date_str})
    if not data:
        return {}
    rows = data.get("pointData") or []
    out = {}
    for r in rows:
        try:
            out[r["name"]] = float(r["price"])
        except (TypeError, ValueError):
            continue
    return out


def pick_cheapest_supermarket(store_prices, raw_name):
    """
    商超比价：同一品种取各监测点里的最低价，返回 (价格, 店名)。

    口径（full / daily 共用，避免两端互相覆盖）：
    - 价格更低者胜，storeName 记对应的店；
    - 价格相同时中百优先，其余情况保留先抓到的店（store_prices 的顺序）；
    - 该品种在任何店都没报价时返回 (None, "")，调用方保留旧值。

    不能拿上一轮的旧商超价参与比较：那样昨天的最低价会挡住今天的真实报价。
    """
    best_price, best_store = None, ""
    for st in store_prices:
        price = st["prices"].get(raw_name)
        if not price:
            continue
        try:
            v = round(float(price), 2)
        except (TypeError, ValueError):
            continue
        if v <= 0 or v > 10000:
            continue
        if (best_price is None or v < best_price
                or (v == best_price and "中百" in st["name"] and "中百" not in best_store)):
            best_price, best_store = v, st["name"]
    return best_price, best_store


def weekly_dates(latest, weeks=WEEKS):
    """从最新日期往回，每 7 天取一个日期（升序）。"""
    d0 = datetime.strptime(latest, "%Y-%m-%d")
    ds = [(d0 - timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(weeks - 1, -1, -1)]
    return ds


# ---------------------------------------------------------------- 农业农村局（补充品种）

def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.encoding = r.apparent_encoding or "utf-8"
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def latest_article_urls(column_path, take, base=NYNCJ_BASE):
    list_url = urljoin(base, column_path)
    soup = get_soup(list_url)
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\d{6}/t\d+_\d+\.s?html?", href):
            urls.append(urljoin(list_url, href))
        if len(urls) >= take:
            break
    return urls


def parse_price_table(article_url):
    """农业农村局价格表：返回 [{name, price(元/500g)}]"""
    soup = get_soup(article_url)
    table = soup.find("table")
    if not table:
        return []
    rows = [[c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            for tr in table.find_all("tr")]
    rows = [r for r in rows if r]
    if len(rows) < 2:
        return []
    header = rows[0]

    def find_col(*kw, exclude=()):
        for i, h in enumerate(header):
            if any(x in h for x in exclude):
                continue
            if any(k in h for k in kw):
                return i
        return None

    name_i = find_col("品名", "品种", "名称", exclude=("市场",))
    dz_i = find_col("大宗价")
    avg_i = find_col("均价", "中间价", "批发价")
    hi_i, lo_i = find_col("最高价"), find_col("最低价")
    if name_i is None:
        return []

    per_kg = "公斤" in soup.get_text() or "千克" in soup.get_text()

    def num(s):
        m = re.search(r"\d+(?:\.\d+)?", (s or "").replace(",", ""))
        return float(m.group()) if m else None

    out = []
    for cells in rows[1:]:
        if len(cells) <= name_i:
            continue
        name = re.sub(r"\s+", "", cells[name_i])
        if not name or name in ("合计", "平均"):
            continue
        price = None
        if dz_i is not None and len(cells) > dz_i:
            price = num(cells[dz_i])
        if price is None and avg_i is not None and len(cells) > avg_i:
            price = num(cells[avg_i])
        if price is None and hi_i is not None and lo_i is not None and len(cells) > max(hi_i, lo_i):
            a, b = num(cells[hi_i]), num(cells[lo_i])
            if a is not None and b is not None:
                price = (a + b) / 2
        if not price or price <= 0 or price > 1000:
            continue
        if per_kg:
            price /= 2
        out.append({"name": name, "price": round(price, 2)})
    return out


def merge_markets(articles):
    bucket = {}
    for art in articles:
        for it in art:
            bucket.setdefault(it["name"], []).append(it["price"])
    return [{"name": n, "price": round(sum(ps) / len(ps), 2)} for n, ps in bucket.items()]


# ---------------------------------------------------------------- 商务局周报（补充肉禽蛋）

def parse_sw_weekly(article_url):
    soup = get_soup(article_url)
    table = soup.find("table")
    if not table:
        return {}
    GROUP_KEYS = ("粮食", "食用油", "肉类", "禽类", "蛋类",
                  "奶制品", "调味品", "水产品", "蔬菜")
    group, subgroup = "", ""
    result = {"肉禽蛋": [], "水产": []}
    seen = {"肉禽蛋": set(), "水产": set()}

    for tr in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if len(cells) == 1:
            txt = cells[0]
            if any(k in txt for k in GROUP_KEYS):
                group, subgroup = txt, ""
            else:
                subgroup = txt
            continue
        if len(cells) < 3 or "元" not in cells[1]:
            continue
        name, unit, raw = cells[0], cells[1], cells[2]
        if "-" in raw or not re.search(r"\d", raw):
            continue
        price = float(re.search(r"\d+(?:\.\d+)?", raw).group())
        if "公斤" in unit:
            price /= 2
        if "零售" not in group:
            continue
        if group.startswith(("肉类", "禽类", "蛋类")):
            cat = "肉禽蛋"
            if group.startswith("肉类") and subgroup in ("猪肉", "牛肉", "羊肉") \
                    and not name.startswith(subgroup[0]):
                name = subgroup[0] + name
        elif group.startswith("水产品"):
            cat = "水产"
        else:
            continue
        if name in seen[cat]:
            continue
        seen[cat].add(name)
        result[cat].append({"name": name, "price": round(price, 2)})
    return result


# ---------------------------------------------------------------- 数据加工

def pinyin_initials(name):
    return "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))


def gen_history(current, name, weeks=WEEKS):
    """接口全挂时的兜底假历史（真实历史拿不到才用）。"""
    rng = random.Random("whcz:" + name)
    series = [float(current)]
    for i in range(weeks - 1):
        change = rng.uniform(-0.04, 0.038)
        seasonal = 0.02 * (1 if i % 26 < 13 else -1)
        prev = series[-1] / (1 + change + seasonal * rng.random())
        prev = max(min(prev, current * 2.8), current * 0.35)
        series.append(round(prev, 2))
    series.reverse()
    return series


def year_position(history, current):
    below = sum(1 for p in history if p <= current)
    return min(100, round(below / max(len(history), 1) * 100))


def fill_series(values):
    """缺失值用前一个有效值填充，开头的缺失用第一个有效值回填。"""
    first = next((v for v in values if v is not None), None)
    if first is None:
        return []
    out, last = [], first
    for v in values:
        last = v if v is not None else last
        out.append(last)
    return out


def build_cat_index(daily_cache, dates, name2cat):
    """
    用发改委的真实历史，按分类算出「周度价格指数」。

    返回 {分类: [相对末周的比值...]}，末周比值恒为 1.0。
    农业农村局/商务局只提供当日价，拿不到历史文章（栏目只留 6 天、无分页），
    所以补充品种的走势用本分类的真实指数推算——涨跌方向、季节形状都来自真实行情，
    只把绝对价格水平锚定在该品种当天的真实报价上。
    """
    idx = {}
    cats = {}
    for n, c in name2cat.items():
        cats.setdefault(c, []).append(n)

    for cat, names in cats.items():
        series = []
        for d in dates:
            day = daily_cache.get(d) or {}
            vals = [day[n]["avg"] for n in names if n in day]
            series.append(sum(vals) / len(vals) if vals else None)
        series = fill_series(series)
        if len(series) < 8:
            continue
        last = series[-1] or series[-2]
        if not last:
            continue
        idx[cat] = [v / last for v in series]
    return idx


def hist_from_index(price, ratio, name):
    """
    按分类指数缩放出该品种的 52 周历史。
    叠一个按品种名定相位的 ±2% 正弦扰动，避免同分类曲线完全重合；末值强制等于当前价。
    """
    import math
    phase = (sum(ord(c) for c in name) % 100) / 100 * 2 * math.pi
    out = [round(price * r * (1 + 0.02 * math.sin(i * 0.9 + phase)), 2)
           for i, r in enumerate(ratio)]
    if out:
        out[-1] = round(price, 2)
    return out


# ---------------------------------------------------------------- 主流程

def full_fetch():
    """全量抓取：回溯 52 周真实历史 + 全量品种。本地手动跑，一天一次都嫌多。"""
    items = []
    used_names = set()
    idx = 1

    # ===== 1. 发改委每日价格（主源，含真实历史与商超价）=====
    print("[抓取] 武汉市发改委 · 每日价格 ...")
    latest = fgj_latest_date()
    if not latest:
        print("  [error] 拿不到任何日期的数据，转为仅用农业农村局源")

    daily_cache = {}
    dates = []
    fgj_cat_of = {}          # 发改委原始品种名 -> 分类（用于算分类指数）
    if latest:
        print(f"  最新数据日: {latest}")
        # 真实 52 周历史：逐周拉取
        dates = weekly_dates(latest)
        print(f"  回溯 {len(dates)} 周历史（{dates[0]} ~ {dates[-1]}）...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            results = list(ex.map(fgj_daily, dates))
        daily_cache = dict(zip(dates, results))
        got = sum(1 for v in daily_cache.values() if v)
        print(f"  历史样本命中 {got}/{len(dates)} 周")

        today = daily_cache.get(latest, {})

        # 真实商超价：选覆盖最多的 2 家超市
        supers = fgj_supermarkets()
        store_prices = []
        for p in supers[:2]:
            prices = fgj_point_prices(p["id"], latest)
            store_prices.append({"name": p["name"], "prices": prices})
            print(f"  商超监测点: {p['name']} → {len(prices)} 个品种有报价")

        # 组装品种
        order = []
        for cat, names in FGJ_CATEGORY.items():
            for n in names:
                order.append((n, cat))
        known = {n for n, _ in order}
        for n in today.keys():
            if n not in known:
                order.append((n, "蔬菜"))     # 未归类的一律按蔬菜

        for raw_name, cat in order:
            row = today.get(raw_name)
            if not row or not row["avg"]:
                continue
            if "桶" in row["unit"] or "升" in row["unit"]:
                continue                       # 桶装油单位不一致，跳过
            display_name = NAME_ALIAS.get(raw_name, raw_name)

            # 真实历史序列
            raw_series = []
            for d in dates:
                r = daily_cache.get(d, {}).get(raw_name)
                raw_series.append(r["avg"] if r else None)

            # 上一周有报价吗？季节性品种（如藜蒿、春笋）夏天会整月停报，
            # 前向填充后直接算周环比会得出「+108%」这种假暴涨，必须区分「重新上市」。
            prev_obs, prev_age = None, None
            for back, v in enumerate(reversed(raw_series[:-1]), 1):
                if v is not None:
                    prev_obs, prev_age = round(v, 2), back
                    break
            obs_weeks = sum(1 for v in raw_series if v is not None)

            series = fill_series(raw_series)
            if len(series) < 8:                # 历史太少则退回模拟，避免图难看
                series = gen_history(row["avg"], display_name)
            series[-1] = round(row["avg"], 2)
            series = [round(v, 2) for v in series]

            # 真实商超价：两店比价取最低（价格相同中百优先）
            sp, store = pick_cheapest_supermarket(store_prices, raw_name)

            items.append({
                "id": idx,
                "name": display_name,
                "rawName": raw_name,          # 数据源原始叫法，daily 模式靠它对上号
                "pinyin": pinyin_initials(display_name),
                "category": cat,
                "unit": "500g",
                "currentPrice": round(row["avg"], 2),
                "supermarketPrice": sp,
                "storeName": store,
                "yearPosition": year_position(series, row["avg"]),
                "history": series,
                "historyReal": True,
                "prevObs": prev_obs,          # 上一个真实有报价的周（跳过停报周）
                "prevObsAge": prev_age,       # 距今几周；>4 视为季节性重新上市
                "obsWeeks": obs_weeks,        # 52 周里有几周真实有报价
                "source": "武汉市发改委",
                "updated": latest,
            })
            used_names.add(raw_name)
            used_names.add(display_name)
            fgj_cat_of[raw_name] = cat
            idx += 1
        print(f"  -> 发改委入库 {len(items)} 种（含真实历史与商超价）")

    # 用真实历史算出各分类的价格指数，供补充源推算走势
    cat_index = {}
    if daily_cache:
        cat_index = build_cat_index(daily_cache, dates, fgj_cat_of)
        if cat_index:
            print(f"  分类真实指数: " + ", ".join(
                f"{c}({len(v)}周)" for c, v in cat_index.items()))

    # ===== 2. 农业农村局批发价（补充发改委没有的品种）=====
    print("[抓取] 武汉市农业农村局 · 批发价 ...")
    extra = 0
    for src in NYNCJ_SOURCES:
        try:
            urls = latest_article_urls(src["column"], src["take"])
            if not urls:
                continue
            arts = [parse_price_table(u) for u in urls]
            for it in merge_markets(arts):
                if it["name"] in used_names:
                    continue
                ratio = cat_index.get(src["category"])
                if ratio:
                    h = hist_from_index(it["price"], ratio, it["name"])
                    hreal = False          # 指数推算：形状来自真实行情，价格锚定当日真实报价
                else:
                    h = gen_history(it["price"], it["name"])
                    hreal = False
                items.append({
                    "id": idx,
                    "name": it["name"],
                    "rawName": it["name"],
                    "pinyin": pinyin_initials(it["name"]),
                    "category": src["category"],
                    "unit": "500g",
                    "currentPrice": it["price"],
                    "supermarketPrice": None,      # 批发价无对应商超价
                    "storeName": "",
                    "yearPosition": year_position(h, it["price"]),
                    "history": h,
                    "historyReal": hreal,
                    "prevObs": None,
                    "prevObsAge": None,
                    "obsWeeks": 52,
                    "source": "农业农村局·批发",
                    "updated": latest or datetime.now().strftime("%Y-%m-%d"),
                })
                used_names.add(it["name"])
                idx += 1
                extra += 1
            print(f"  {src['category']}: 当前累计补充 {extra} 种")
        except Exception as e:
            print(f"  [error] {src['category']} 抓取失败: {e}")

    # ===== 3. 商务局周报（补充肉禽蛋细类）=====
    print("[抓取] 武汉市商务局 · 周报 ...")
    try:
        sw_urls = latest_article_urls(SW_SOURCE["column"], SW_SOURCE["take"], base=SW_BASE)
        for u in sw_urls:
            sw = parse_sw_weekly(u)
            if not sw.get("肉禽蛋"):
                continue
            n = 0
            for cat, rows in sw.items():
                for it in rows:
                    if it["name"] in used_names:
                        continue
                    ratio = cat_index.get(cat)
                    h = hist_from_index(it["price"], ratio, it["name"]) if ratio \
                        else gen_history(it["price"], it["name"])
                    items.append({
                        "id": idx,
                        "name": it["name"],
                        "rawName": it["name"],
                        "pinyin": pinyin_initials(it["name"]),
                        "category": cat,
                        "unit": "500g",
                        "currentPrice": it["price"],
                        "supermarketPrice": None,
                        "storeName": "",
                        "yearPosition": year_position(h, it["price"]),
                        "history": h,
                        "historyReal": False,
                        "prevObs": None,
                        "prevObsAge": None,
                        "obsWeeks": 52,
                        "source": "商务局·周报",
                        "updated": u.split("/")[-1][1:9],
                    })
                    used_names.add(it["name"])
                    idx += 1
                    n += 1
            print(f"  采用 {u.split('/')[-1]}，补充 {n} 种")
            break
    except Exception as e:
        print(f"  [error] 商务局周报失败: {e}")

    # 发改委不可达时（GitHub 机器连不上裸 IP，是常态而非故障），
    # 把上一份 data.json 里的发改委品种原样继承过来，
    # 避免一次「降级成功」的全量把真实 52 周历史和商超价整体冲掉。
    if not any(it.get("source") == "武汉市发改委" for it in items):
        kept = restore_fgj_items(items)
        if kept:
            print(f"  [保底] 发改委不可达，从旧 {DATA_FILE} 继承 {kept} 个品种（含真实历史/商超价）")

    if not items:
        print("[fatal] 所有数据源都失败，不覆盖 data.json")
        sys.exit(1)

    save_items(items, tag="全量")


# ---------------------------------------------------------------- 每日增量

# 前端显示名 -> 发改委原始名（老 data.json 没有 rawName 字段时用它反查）
REV_ALIAS = {v: k for k, v in NAME_ALIAS.items()}


def item_key(it):
    """品种的稳定标识：优先 rawName，老数据用别名反查，最后退回显示名。"""
    return it.get("rawName") or REV_ALIAS.get(it.get("name", ""), it.get("name", ""))


def restore_fgj_items(items):
    """发改委抓不到时，从旧 data.json 继承发改委品种（保住真实历史与商超价）。"""
    if not os.path.exists(DATA_FILE):
        return 0
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        return 0
    have = {item_key(it) for it in items}
    n = 0
    for it in old:
        if it.get("source") != "武汉市发改委":
            continue
        k = item_key(it)
        if k in have:
            continue
        items.append(it)
        have.add(k)
        n += 1
    return n


def save_items(items, tag=""):
    """统一出口：排序 + 重编号 + 落盘。"""
    CAT_ORDER = {"蔬菜": 0, "肉禽蛋": 1, "水产": 2, "米面粮油": 3, "豆制品": 4}
    items.sort(key=lambda x: (CAT_ORDER.get(x["category"], 9), x["id"]))
    for i, it in enumerate(items, 1):
        it["id"] = i

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    stats = {}
    for it in items:
        stats[it["category"]] = stats.get(it["category"], 0) + 1
    real_hist = sum(1 for it in items if it.get("historyReal"))
    with_sp = sum(1 for it in items if it.get("supermarketPrice"))
    print(f"\n[完成{('·' + tag) if tag else ''}] {len(items)} 个品种 | 分类: {stats}")
    print(f"       真实历史: {real_hist} 种 | 真实商超价: {with_sp} 种")


def append_price(it, price, date_str, gap_weeks=1):
    """
    把今天的新价追加进 52 周序列，淘汰最老的一周，重算百分位。
    - 同一天重复跑（手动触发两次）不会产生重复点，只覆盖最后一位
    - 历史为空 / 不足 52 周时自动补齐，绝不抛异常
    返回 True 表示已更新，False 表示被健康检查拦下。
    """
    try:
        price = round(float(price), 2)
    except (TypeError, ValueError):
        return False
    if not price or price <= 0 or price > 10000:
        return False

    h = [v for v in (it.get("history") or []) if isinstance(v, (int, float))]
    old = h[-1] if h else None

    # -------- 健康检查：无征兆的暴涨/暴跌一律跳过，保留旧数据 --------
    if old and not price_sane(old, price, gap_weeks):
        print(f"  [skip] {it.get('name')} 价格异常 {old} → {price}"
              f"（{price / old * 100:.0f}%），保留旧值")
        return False

    if it.get("updated") == date_str and h:
        h[-1] = price                      # 同日重跑：覆盖，不追加
    else:
        # 历史不足 52 周时用最早值向前补齐，保证图表和百分位口径一致
        while len(h) < WEEKS - 1:
            h.insert(0, h[0] if h else price)
        h.append(price)
        if len(h) > WEEKS:
            h = h[-WEEKS:]

    it["history"] = h
    it["currentPrice"] = price
    it["yearPosition"] = year_position(h, price)
    it["updated"] = date_str

    if it.get("source") == "武汉市发改委":
        it["historyReal"] = True
        it["prevObs"] = h[-2] if len(h) > 1 else None
        it["prevObsAge"] = gap_weeks
        it["obsWeeks"] = min(WEEKS, (it.get("obsWeeks") or 0) + 1)
    return True


def price_sane(old, new, gap_weeks):
    """
    价格合理性闸门。日涨跌超过 +120% / -55% 且不是长期停报后复出，判定为脏数据。
    季节性品种（藜蒿夏天整月无报价）gap_weeks 会很大，属于正常跳变，放行。
    """
    if not old or old <= 0:
        return True
    ratio = new / old
    if gap_weeks > 3:               # 停报超过 3 周再出现，价格跳变合理
        return True
    return 0.45 <= ratio <= 2.2


def weeks_since(date_str):
    """距今天几周（解析失败按 0 处理，不影响主流程）。"""
    try:
        return max(0, (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days / 7)
    except Exception:
        return 0


def daily_update():
    """
    每日增量：只抓「今天」一个截面，追加到现有 data.json，不发任何历史请求。
    云端 Actions 每天跑这个，请求数个位数，几秒结束。
    """
    if not os.path.exists(DATA_FILE):
        print(f"[warn] 没有 {DATA_FILE}，自动转为全量抓取 ...")
        return full_fetch()

    with open(DATA_FILE, encoding="utf-8") as f:
        items = json.load(f)
    print(f"[增量] 读入 {len(items)} 个品种（现有历史 {len(items[0].get('history') or [])} 周）")

    # 按数据源分开索引，绝不能混：农业局的「花菜」是批发价 1.5，
    # 发改委的「花菜」是零售价 3.97，混用会把零售价写成批发价（还触发健康检查）。
    index_fgj = {item_key(it): it for it in items
                 if it.get("source") == "武汉市发改委"}
    index_supp = {item_key(it): it for it in items
                  if it.get("source") != "武汉市发改委"}
    updated = 0

    # -------- 1. 发改委今日零售价（1 次请求，不通就跳过）--------
    print("[抓取] 发改委 · 今日 ...")
    latest = None
    today = None
    # 先花 8 秒探一下。境外机器连发改委裸 IP 必超时，探不通就整段跳过，
    # 否则要白等 3 次重试 × 15 秒。
    try:
        if fgj_reachable():
            latest = fgj_latest_date()
            today = fgj_daily(latest) if latest else None
        else:
            print("  [warn] 发改委不可达（境外服务器常态），跳过探测")
    except Exception as e:
        print(f"  [error] 发改委异常: {type(e).__name__}")

    if today:
        print(f"  数据日: {latest}（{len(today)} 个品种）")
        miss = []
        for raw_name, row in today.items():
            if not row or not row.get("avg"):
                continue
            if "桶" in row["unit"] or "升" in row["unit"]:
                continue
            it = index_fgj.get(raw_name)
            if not it:
                miss.append(raw_name)      # 新品种需要全量模式补历史
                continue
            gap = weeks_since(it.get("updated") or "")
            if append_price(it, row["avg"], latest, gap_weeks=max(1, gap)):
                updated += 1

        # 真实商超价（2 个监测点，2 次请求）
        # 与 full 模式同一口径：两店比价取最低，storeName 记该店，价格相同中百优先。
        # 必须在本轮抓到的数据里重算，不能拿上一轮的旧商超价参与比较，
        # 否则昨天那家店的最低价会挡住今天的真实报价。
        try:
            store_prices = []
            for p in fgj_supermarkets()[:2]:
                prices = fgj_point_prices(p["id"], latest)
                store_prices.append({"name": p["name"], "prices": prices})
                print(f"  商超 {p['name']}: {len(prices)} 个品种")
            for raw_name, it in index_fgj.items():
                sp, store = pick_cheapest_supermarket(store_prices, raw_name)
                if sp is not None:
                    it["supermarketPrice"] = sp
                    it["storeName"] = store
        except Exception as e:
            print(f"  [error] 商超价: {type(e).__name__}")

        if miss:
            print(f"  [提示] {len(miss)} 个新品种未入库（如 {', '.join(miss[:3])}），需 --mode=full 补历史")
    else:
        # GitHub 的机器连不上发改委裸 IP（实测 ConnectTimeout），这是常态不是故障。
        # 此时发改委那 40 个品种原样保留：价格、历史、商超价、updated 日期都不动，
        # 前端会显示该品种的更新时间偏旧，属于如实反映。
        print("  [warn] 发改委今日不可达（境外服务器常态），该部分品种保留上次数据")

    if not latest:
        latest = datetime.now().strftime("%Y-%m-%d")

    # -------- 2. 农业局批发价（3 个栏目 × 最新 1 篇）--------
    print("[抓取] 农业农村局 · 今日批发价 ...")
    for src in NYNCJ_SOURCES:
        try:
            urls = latest_article_urls(src["column"], 1)
            if not urls:
                continue
            arts = [parse_price_table(u) for u in urls]
            n = 0
            for it_new in merge_markets(arts):
                it = index_supp.get(it_new["name"])
                if not it:
                    continue
                gap = weeks_since(it.get("updated") or "")
                if append_price(it, it_new["price"], latest, gap_weeks=max(1, gap)):
                    n += 1
            updated += n
            print(f"  {src['category']}: 更新 {n} 种")
        except Exception as e:
            print(f"  [error] {src['category']}: {type(e).__name__}")

    # -------- 3. 商务局周报（往前找最多 3 篇有数据的，最新几期常是空正文）--------
    print("[抓取] 商务局 · 最新周报 ...")
    try:
        for u in latest_article_urls(SW_SOURCE["column"], 6, base=SW_BASE):
            sw = parse_sw_weekly(u)
            if not sw.get("肉禽蛋"):
                continue
            n = 0
            wdate = u.split("/")[-1][1:9]
            wdate = f"{wdate[:4]}-{wdate[4:6]}-{wdate[6:8]}" if len(wdate) == 8 else latest
            for cat, rows in sw.items():
                for it_new in rows:
                    it = index_supp.get(it_new["name"])
                    if not it:
                        continue
                    gap = weeks_since(it.get("updated") or "")
                    if append_price(it, it_new["price"], wdate, gap_weeks=max(1, gap)):
                        n += 1
            updated += n
            print(f"  周报更新 {n} 种")
            break
    except Exception as e:
        print(f"  [error] 周报: {type(e).__name__}")

    if updated == 0:
        print("[warn] 本次没有任何品种更新，保留原 data.json 不动")
        return

    save_items(items, tag="增量")
    print(f"       本次更新 {updated} 个价格点")


def main():
    mode = "daily"
    for a in sys.argv[1:]:
        if a.startswith("--mode="):
            mode = a.split("=", 1)[1].strip()
        elif a in ("--full", "-f"):
            mode = "full"
        elif a in ("--daily", "-d"):
            mode = "daily"

    if mode not in ("daily", "full"):
        print(f"[error] 未知模式 {mode}，可选 daily / full")
        sys.exit(2)

    print(f"===== 武汉菜篮子 · {mode} 模式 =====")
    if mode == "full":
        full_fetch()
    else:
        daily_update()


if __name__ == "__main__":
    main()
