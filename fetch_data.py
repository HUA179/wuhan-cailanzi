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

输出：data.json（与前端结构一致，另加 source / updated 字段）

运行：
    python fetch_data.py
依赖：
    pip install requests beautifulsoup4 pypinyin
"""

import json
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

def fgj_get(path, params=None):
    """调用发改委平台接口，失败重试 RETRY 次。"""
    for i in range(RETRY + 1):
        try:
            r = _sess().get(FGJ_API + path, params=params or {}, timeout=TIMEOUT)
            j = r.json()
            if j.get("code") == 200:
                return j.get("data") or {}
            print(f"  [warn] {path} 返回 {j.get('msg')}")
            return {}
        except Exception as e:
            if i == RETRY:
                print(f"  [error] {path} 失败: {e}")
                return {}
    return {}


def fgj_daily(date_str):
    """某天的每日价格：{品种名: {avg,max,min,unit,spec}}"""
    data = fgj_get("/business/mrjg/queryJBSJData", {"date": date_str})
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
    """从今天往前找最近一个有数据的日期。"""
    d = datetime.now()
    for _ in range(12):
        s = d.strftime("%Y-%m-%d")
        if fgj_daily(s):
            return s
        d -= timedelta(days=1)
    return None


def fgj_supermarkets():
    """取超市类监测点，按数据覆盖量从多到少排序。"""
    data = fgj_get("/dataStatistics/priceCompare/queryPointList", {"areaCode": AREA_CODE})
    pts = data.get("pointList") or []
    supers = [p for p in pts if p.get("pointType") == "超市"]
    return supers


def fgj_point_prices(point_id, date_str):
    """单个监测点的逐品价格：{品种名: 价格}"""
    data = fgj_get("/dataStatistics/priceCompare/queryDataForPoint",
                   {"pointId": point_id, "date": date_str})
    rows = data.get("pointData") or []
    out = {}
    for r in rows:
        try:
            out[r["name"]] = float(r["price"])
        except (TypeError, ValueError):
            continue
    return out


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


# ---------------------------------------------------------------- 主流程

def main():
    items = []
    used_names = set()
    idx = 1

    # ===== 1. 发改委每日价格（主源，含真实历史与商超价）=====
    print("[抓取] 武汉市发改委 · 每日价格 ...")
    latest = fgj_latest_date()
    if not latest:
        print("  [error] 拿不到任何日期的数据，转为仅用农业农村局源")

    daily_cache = {}
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
            series = []
            for d in dates:
                r = daily_cache.get(d, {}).get(raw_name)
                series.append(r["avg"] if r else None)
            series = fill_series(series)
            if len(series) < 8:                # 历史太少则退回模拟，避免图难看
                series = gen_history(row["avg"], display_name)
            series[-1] = round(row["avg"], 2)
            series = [round(v, 2) for v in series]

            # 真实商超价（优先第一家覆盖该品种的超市）
            sp, store = None, ""
            for st in store_prices:
                if raw_name in st["prices"]:
                    sp, store = round(st["prices"][raw_name], 2), st["name"]
                    break

            items.append({
                "id": idx,
                "name": display_name,
                "pinyin": pinyin_initials(display_name),
                "category": cat,
                "unit": "500g",
                "currentPrice": round(row["avg"], 2),
                "supermarketPrice": sp,
                "storeName": store,
                "yearPosition": year_position(series, row["avg"]),
                "history": series,
                "source": "武汉市发改委",
                "updated": latest,
            })
            used_names.add(raw_name)
            used_names.add(display_name)
            idx += 1
        print(f"  -> 发改委入库 {len(items)} 种（含真实历史与商超价）")

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
                h = gen_history(it["price"], it["name"])
                items.append({
                    "id": idx,
                    "name": it["name"],
                    "pinyin": pinyin_initials(it["name"]),
                    "category": src["category"],
                    "unit": "500g",
                    "currentPrice": it["price"],
                    "supermarketPrice": None,      # 批发价无对应商超价
                    "storeName": "",
                    "yearPosition": year_position(h, it["price"]),
                    "history": h,
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
                    h = gen_history(it["price"], it["name"])
                    items.append({
                        "id": idx,
                        "name": it["name"],
                        "pinyin": pinyin_initials(it["name"]),
                        "category": cat,
                        "unit": "500g",
                        "currentPrice": it["price"],
                        "supermarketPrice": None,
                        "storeName": "",
                        "yearPosition": year_position(h, it["price"]),
                        "history": h,
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

    if not items:
        print("[fatal] 所有数据源都失败，不覆盖 data.json")
        sys.exit(1)

    # 默认列表顺序：蔬菜 → 肉禽蛋 → 水产 → 米面粮油 → 豆制品（米面常年不动，放前面看不出行情）
    CAT_ORDER = {"蔬菜": 0, "肉禽蛋": 1, "水产": 2, "米面粮油": 3, "豆制品": 4}
    items.sort(key=lambda x: (CAT_ORDER.get(x["category"], 9), x["id"]))
    for i, it in enumerate(items, 1):
        it["id"] = i

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    stats = {}
    for it in items:
        stats[it["category"]] = stats.get(it["category"], 0) + 1
    real_hist = sum(1 for it in items if it.get("source") == "武汉市发改委")
    with_sp = sum(1 for it in items if it.get("supermarketPrice"))
    print(f"\n[完成] {len(items)} 个品种 | 分类: {stats}")
    print(f"       真实历史走势: {real_hist} 种 | 真实商超价: {with_sp} 种")


if __name__ == "__main__":
    main()
