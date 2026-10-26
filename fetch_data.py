# -*- coding: utf-8 -*-
"""
菜篮子 - 数据抓取脚本（多源版 · 城市可配置）
=============================================
主城市：武汉（湖北）—— 见 cities/wuhan.py

数据源分两类：

【本地源】由城市配置决定站点参数（cities/<id>.py 里的 fgj / nyncj / sw 字段）
  ① 市发改委「价格监测平台」每日零售价（主源，支持回溯真实历史）
  ② 市农业农村局 批发价（补品种）
  ③ 市商务局 生活必需品周报（补肉禽蛋细类）

【参考源】全国口径，与城市无关（sources/ 下）
  ④ 农业农村部「全国农产品批发市场价格信息系统」
     周报 246 期（分品种水果，元/公斤）+ 日报 1369 期（全国均价基准）
     → source = "全国参考"
  ⑤ 北京新发地 分品种水果批发价（元/斤，×2 转元/公斤）
     → source = "新发地·批发"
     补上官方 6 种水果里没有的「橘子」

输出：data.json（与前端结构一致，含 source / unit / region /
      historyDates / historyKind / historyReal 等字段）

运行：
    python fetch_data.py --mode=full    # 全量：回溯 52 周真实历史（历史是死数据，
                                        # 只在补历史/换季新品种时跑）
    python fetch_data.py --mode=daily   # 增量：只抓今天一个截面，请求数个位数
    python fetch_data.py --city=wuhan   # 选城市（默认读环境变量 CAILANZI_CITY，再退回武汉）

为什么分两种：本地政务网对境外/异地机器极不稳定，52 个历史日期并发去拉必然超时。
历史数据本身不会变，每天重爬纯属浪费。

依赖：
    pip install requests beautifulsoup4 pypinyin
"""

import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypinyin import lazy_pinyin, Style

from cities import CATEGORY_ORDER, load_city
from sources import agri_national, xinfadi

# ---------------------------------------------------------------- 城市配置

CITY = {}
FGJ_API = ""
FGJ_REFERER = ""
LOCAL_SOURCE_NAME = ""
AREA_CODE = ""
NYNCJ_BASE = ""
SW_BASE = ""
NYNCJ_SOURCES = []
SW_SOURCE = None
FGJ_CATEGORY = {}
NAME_ALIAS = {}
SUPER_EXTRA = {}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
TIMEOUT = 15                   # 单次请求超时（异地机器访问政务网偶有丢包，超过 15s 基本没救）
RETRY = 2                      # 重试次数
MAX_WORKERS = 6                # 历史日期并发数（串行 52 周在异地机器上要跑十几分钟）
WEEKS = 52                     # 走势图窗口
DATA_FILE = "data.json"

# 数据源陈旧阈值（天）。超过就 WARNING，并且**不计入当日有效更新数**。
# 为什么要有这道闸：2026-09-14 起商务局周报正文改成图片，解析器拿不到表格一路回溯到
# 9-11，日志却照样打印「周报更新 7 种」——静默失败比直接报错危险得多。
STALE_DAYS = 3
# 商超比价快照是周更（实测 pointDataDate=2026-10-21），阈值单独放宽
SUPER_SNAPSHOT_STALE_DAYS = 10


def configure(city_id=None):
    """
    载入城市配置，把站点参数铺到模块级变量。

    所有抓取函数只在**调用时**读这些变量，所以这里改一次就全流程生效，
    main() 的 --city 参数靠它切换，其他代码一行不用改。
    """
    global CITY, FGJ_API, FGJ_REFERER, LOCAL_SOURCE_NAME, AREA_CODE
    global NYNCJ_BASE, SW_BASE, NYNCJ_SOURCES, SW_SOURCE, FGJ_CATEGORY, NAME_ALIAS
    global SUPER_EXTRA

    CITY = load_city(city_id)
    fgj = CITY.get("fgj") or {}
    FGJ_API = fgj.get("api") or ""
    FGJ_REFERER = fgj.get("referer") or ""
    LOCAL_SOURCE_NAME = fgj.get("source_name") or "本地价格监测"
    AREA_CODE = CITY.get("area_code") or ""
    NYNCJ_BASE = CITY.get("nyncj_base") or ""
    SW_BASE = CITY.get("sw_base") or ""
    NYNCJ_SOURCES = CITY.get("nyncj_sources") or []
    SW_SOURCE = CITY.get("sw_source")
    FGJ_CATEGORY = CITY.get("category_map") or {}
    NAME_ALIAS = CITY.get("name_alias") or {}
    SUPER_EXTRA = CITY.get("super_extra") or {}
    return CITY


configure(os.environ.get("CAILANZI_CITY"))

_local = threading.local()


def _sess():
    """每个线程一个 Session，避免共享连接池在多线程下互相干扰。"""
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        _local.s = s
    # Referer 每次刷新：城市配置可能在本进程内被 configure() 换掉
    s.headers.update({"User-Agent": HEADERS["User-Agent"], "Referer": FGJ_REFERER})
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


# ---------------------------------------------------------------- 商超快照（补发改委均价表没有的品种）

def fgj_point_snapshot(point_id, date_str=None):
    """
    单个监测点的逐品价格 + **平台真实快照日**。

    实测（2026-10-26，同一监测点分别传 date=2026-10-26 / 2026-01-05 / 2025-06-10）：
    三次返回完全一致，响应里的 pointDataDate 恒为 2026-10-21。
    ⇒ queryDataForPoint 的 date 参数不生效，只能取「当前快照」。

    所以这里必须把 pointDataDate 原样带出来当 updated，
    绝不能用传进去的日期或今天顶替——那是伪造更新时间。
    """
    data = fgj_get("/dataStatistics/priceCompare/queryDataForPoint",
                   {"pointId": point_id,
                    "date": date_str or datetime.now().strftime("%Y-%m-%d")})
    if not data:
        return {}, None
    snap = (data.get("pointDataDate") or "")[:10] or None
    out = {}
    for r in data.get("pointData") or []:
        try:
            out[r["name"]] = float(r["price"])
        except (TypeError, ValueError):
            continue
    return out, snap


def fgj_supermarket_extras(store_prices):
    """
    商超监测点里有、但发改委「每日均价表」没有的品种，补成独立条目。

    目前只有「猪五花肉」：商务局周报图片化之后，五花肉在武汉找不到第二个
    公开官方源，而 7 家商超监测点的比价清单里一直有它。
    口径仍是零售价（元/500g，与主表一致），差别只是数据节奏为周更快照。
    """
    out = []
    for name, cat in (SUPER_EXTRA.get("items") or {}).items():
        price, store = pick_cheapest_supermarket(store_prices, name)
        if price is None:
            print(f"  [warn] 商超快照里没有「{name}」报价，跳过")
            continue
        out.append({"name": name, "price": price, "category": cat, "store": store})
    return out


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
#
# 2026-09-14 起，武汉市商务局把「生活必需品市场监测情况」的正文从 HTML 表格换成了
# 6 张 JPG（实测：table 数 0 / 正文图 6 张，且页面无任何 xls/xlsx/doc/pdf 附件）。
# 也就是说这条路**已经没有可解析的数据**，不是偶发失败。
#
# 处理原则：
#   1. 解析器保留（万一哪天改回表格，自动复活），但必须能明确说出「为什么没数据」；
#   2. 拿到的数据先过 stale_check，陈旧就不计入当日有效更新数；
#   3. 绝不再出现「解析失败 → 一路回溯 → 日志照报更新 N 种」这种静默失败。

SW_IMG_RE = re.compile(r"(logo|beian|jiucuo|icon|sublogo|hxsw|whsw|red)", re.I)


def parse_sw_table(table):
    """商务局周报表格 → {"肉禽蛋": [...], "水产": [...]}（纯解析，不做网络 IO）。"""
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


def parse_sw_weekly(article_url):
    """兼容旧调用：抓页面 → 取第一张表 → 解析（拿不到表格返回 {}）。"""
    return parse_sw_table(get_soup(article_url).find("table"))


def sw_articles(take=6):
    """商务局周报栏目 → [(文章URL, 标题)]。标题里带日期区间，比 URL 发布日更准。"""
    if not SW_SOURCE:
        return []
    list_url = urljoin(SW_BASE, SW_SOURCE["column"])
    soup = get_soup(list_url)
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"\d{6}/t\d+_\d+\.s?html?", href):
            out.append((urljoin(list_url, href), a.get_text(strip=True)))
        if len(out) >= take:
            break
    return out


def sw_fetch(max_try=3):
    """
    取商务局「最新一期仍能解析」的周报，并给出可读结论。

    返回 {"ok", "date", "rows", "reason", "url", "title"}
        ok=False 时 reason 说明到底为什么（图片化 / 无表格 / 栏目打不开），
        调用方直接打 WARNING，不再自己猜。

    为什么不再「for 循环回溯 6 篇、break 到第一篇有数据的」：
    图片化之后每一篇都解析不出东西，回溯只会一路退到 9-11 的老表格，
    然后用两个月前的价格冒充今天的数据。现在最多看 max_try 篇，
    并在每一篇上都留下失败原因。
    """
    if not SW_SOURCE:
        return {"ok": False, "date": None, "rows": {}, "reason": "未配置商务局栏目",
                "url": "", "title": ""}
    try:
        arts = sw_articles(max(max_try, 1))
    except Exception as e:
        return {"ok": False, "date": None, "rows": {},
                "reason": f"栏目页抓取失败: {type(e).__name__}", "url": "", "title": ""}

    reasons = []
    for url, title in arts[:max_try]:
        tag = parse_cn_date(title) or article_date(url) or "日期未知"
        try:
            soup = get_soup(url)
        except Exception as e:
            reasons.append(f"{tag} 打开失败: {type(e).__name__}")
            continue

        table = soup.find("table")
        if not table:
            imgs = [i for i in soup.find_all("img")
                    if not SW_IMG_RE.search(i.get("src", ""))
                    and not re.search(r"/\d{2}\.jpg$", i.get("src", ""))]
            reasons.append(f"{tag} 正文已图片化（0 表格 / {len(imgs)} 图）" if imgs
                           else f"{tag} 正文没有表格")
            continue

        rows = parse_sw_table(table)
        if not rows.get("肉禽蛋") and not rows.get("水产"):
            reasons.append(f"{tag} 表格里没有肉禽蛋/水产行")
            continue

        return {"ok": True, "date": tag, "rows": rows, "reason": "",
                "url": url, "title": title}

    return {"ok": False, "date": None, "rows": {},
            "reason": "；".join(reasons) or "栏目里没有可用文章", "url": "", "title": ""}


# ---------------------------------------------------------------- 数据加工

def pinyin_initials(name):
    return "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))


def year_position(history, current):
    """
    当前价在 52 周里的百分位。只统计真实有报价的周，断档（None）不参与分母。
    一条全空的历史返回 None —— 没有样本就不该给出百分位。
    """
    vals = [p for p in history if isinstance(p, (int, float))]
    if not vals or current is None:
        return None
    below = sum(1 for p in vals if p <= current)
    return min(100, round(below / len(vals) * 100))


def blank_history(weeks=WEEKS):
    """
    拿不到真实历史时的占位：整条留空。

    这里以前是 gen_history()，用 random.Random("whcz:" + name) 生成 52 周随机序列，
    只在分类指数缺失时兜底。但那等于凭空编造一条价格曲线，前端完全无法识别，
    与「绝不造假」的底线冲突，已彻底删除。缺数据就该显示缺数据。
    """
    return [None] * weeks


def norm_history(raw, weeks=WEEKS):
    """把历史序列规整成定长数组：保留 None（断档占位），只剔除非法类型与负值。"""
    out = []
    for v in (raw or []):
        if v is None:
            out.append(None)
        elif isinstance(v, (int, float)) and v > 0:
            out.append(round(float(v), 2))
        else:
            out.append(None)
    if len(out) < weeks:
        out = [None] * (weeks - len(out)) + out
    return out[-weeks:]


def dates_ending(n, last_date):
    """按末位日期往前推 n 周的升序日期数组，保证与 history 等长。"""
    try:
        d0 = datetime.strptime(last_date, "%Y-%m-%d")
    except Exception:
        return [None] * n
    return [(d0 - timedelta(weeks=i)).strftime("%Y-%m-%d") for i in range(n - 1, -1, -1)]


def article_date(url):
    """
    从政府站文章 URL 提取 ISO 日期。
    URL 形如 .../t20260911_2846915.shtml，文件名前 8 位是日期。
    返回 None 表示解析失败，交给调用方回退到数据日。
    """
    raw = url.split("/")[-1][1:9]
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def parse_cn_date(text):
    """
    从中文标题里抽最后一个日期，返回 ISO 日期。
    标题形如「武汉市生活必需品市场监测情况（2026年9月28日—2026年10月4日）」，
    取区间右端（= 该期数据覆盖的最后一天），比 URL 的发布日更接近数据口径。
    """
    pts = re.findall(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text or "")
    best = None
    for y, m, d in pts:
        try:
            cur = datetime(int(y), int(m), int(d))
        except ValueError:
            continue
        if best is None or cur > best:
            best = cur
    return best.strftime("%Y-%m-%d") if best else None


def days_old(date_str):
    """数据日期距今天几天；解析失败返回 None。"""
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (datetime.now().date() - d).days


def stale_check(label, date_str, days=STALE_DAYS):
    """
    数据源陈旧闸门。返回 (fresh, age)。

    fresh=False 时调用方**必须**把这个源当天的产出从「有效更新数」里剔除，
    否则日志会虚报——这正是商务局那 7 个品种卡在 9-11 却天天报「更新 7 种」的原因。

    日期解析不出来也按陈旧处理：宁可少报，也不虚报。
    """
    age = days_old(date_str)
    if age is None:
        print(f"  [WARNING] 数据源陈旧 | {label}：数据日期无法解析（{date_str!r}），本日不计入更新")
        return False, None
    if age > days:
        print(f"  [WARNING] 数据源陈旧 | {label}：最新数据停在 {date_str}，"
              f"已 {age} 天未更新（阈值 {days} 天），本日不计入更新")
        return False, age
    return True, age


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
        # 不再前向填充：缺失的那周保持 None，指数曲线该断就断。
        # 原来 fill_series 会把空周填成前值，等于凭空造出一段「价格平稳」。
        anchors = [v for v in series if v is not None]
        if len(anchors) < 8:
            continue
        last = anchors[-1]
        if not last:
            continue
        idx[cat] = [round(v / last, 6) if v is not None else None for v in series]
    return idx


def hist_from_index(price, ratio):
    """
    按分类真实指数缩放出该品种的 52 周历史。

    曲线形状完全由真实分类指数决定，不叠加任何人为扰动
    （旧版按品种名相位叠了 ±2% 正弦波，纯粹为了让同分类曲线不重合而凭空抖动，
    已去掉）。指数缺失的周同样留 None，不插值，保证断档可辨。
    """
    out = [round(price * r, 2) if r is not None else None for r in ratio]
    if not out:
        return []
    if out[-1] is None:
        out[-1] = round(price, 2)      # 末位有今日真实报价，指数却缺 → 用真价锚定
    return out


# ---------------------------------------------------------------- 参考源（全国口径）

# 参考源元信息：source 字段 → 明细/区域/粒度
REF_SOURCES = {
    "全国参考": {
        "detail": "农业农村部 · 全国农产品批发市场价格信息系统",
        "region": "national",
        "granularity": "weekly",
        "data_level": "official",
    },
    "新发地·批发": {
        "detail": "北京新发地农产品批发市场 · 分品种日价",
        "region": "beijing",
        "granularity": "daily",
        "data_level": "official",
    },
}


def prev_obs_of(series):
    """序列末尾之前，最近一个真实观测值及其距今周数。"""
    for back, v in enumerate(reversed((series or [])[:-1]), 1):
        if v is not None:
            return round(float(v), 2), back
    return None, None


def build_ref_items(result, source):
    """
    把 sources.*.collect() 的结果转成 data.json 的 item 列表。

    丢数据的三种情况，都按「不入库」处理，绝不补值：
        · 整条序列一个真实报价都没有（obs == 0）
        · 现价取不到（末位 None 且前面也全空）
    """
    meta = REF_SOURCES[source]
    dates = result.get("dates") or []
    latest = result.get("latest")
    out = []

    for name, info in (result.get("series") or {}).items():
        values = norm_history(info.get("values"), len(dates))
        obs = sum(1 for v in values if v is not None)
        if obs == 0 or not dates:
            continue

        cur, updated = values[-1], latest
        if cur is None:
            # 本周官方还没发（或该点落在停更窗口）→ 用最近一次真实报价，
            # updated 跟着挪到那天，前端「数据截至」会如实显示旧日期
            last_i = max(i for i, v in enumerate(values) if v is not None)
            cur, updated = values[last_i], dates[last_i]

        prev, age = prev_obs_of(values)
        out.append({
            "id": 0,                                   # 由 save_items 统一重排
            "name": name,
            "rawName": name,
            "pinyin": pinyin_initials(name),
            "category": info.get("category") or "水果",
            "unit": "kg",
            "unitLabel": "元/公斤",
            "currentPrice": round(float(cur), 2),
            "supermarketPrice": None,                  # 批发/全国口径没有商超价
            "storeName": "",
            "yearPosition": year_position(values, cur),
            "history": values,
            "historyDates": dates,
            "historyKind": "real",
            "historyReal": True,
            "prevObs": prev,
            "prevObsAge": age,
            "obsWeeks": obs,
            "source": source,
            "sourceDetail": meta["detail"],
            "region": meta["region"],
            "granularity": meta["granularity"],
            "dataLevel": meta["data_level"],
            "updated": updated,
        })
    return out


def add_reference(items, idx):
    """
    追加「全国参考」和「新发地·批发」两组品种。返回 (items, idx)。

    两组源都是全国/北京口径，与城市无关，所以开关写在城市配置里
    （use_national / use_xinfadi），换城市不用改这里。
    """
    have = {it.get("name") for it in items}

    if CITY.get("use_national"):
        print("[抓取] 农业农村部 · 全国参考（周报+日报）...")
        try:
            res = agri_national.collect(weeks=CITY.get("fruit_weeks", WEEKS))
            got = [it for it in build_ref_items(res, "全国参考") if it["name"] not in have]
            for it in got:
                it["id"] = idx
                idx += 1
            items.extend(got)
            have.update(it["name"] for it in got)
            st = res.get("stats") or {}
            span = st.get("weekly_span") or ("-", "-")
            print("  -> 入库 %d 种 | 周报 %d 期（表5 解析成功 %d 期，%s~%s）| 日报 %d 期"
                  % (len(got), st.get("weekly_issues", 0), st.get("weekly_parsed", 0),
                     span[0], span[1], st.get("daily_rows", 0)))
        except Exception as e:
            print("  [error] 全国参考失败: %s: %s" % (type(e).__name__, e))

    if CITY.get("use_xinfadi"):
        print("[抓取] 北京新发地 · 水果分品种日价 ...")
        try:
            res = xinfadi.collect(weeks=CITY.get("fruit_weeks", WEEKS))
            got = [it for it in build_ref_items(res, "新发地·批发") if it["name"] not in have]
            for it in got:
                it["id"] = idx
                idx += 1
            items.extend(got)
            have.update(it["name"] for it in got)
            st = res.get("stats") or {}
            print("  -> 入库 %d 种 | 52 周命中 %d 周"
                  % (len(got), st.get("weeks_hit", 0)))
            unm = st.get("unmapped") or []
            if unm:
                print("     未映射品种（不计入，仅备查）: %s%s"
                      % ("、".join("%s×%d" % (n, c) for n, c in unm[:8]),
                         " 等 %d 个" % len(unm) if len(unm) > 8 else ""))
        except Exception as e:
            print("  [error] 新发地失败: %s: %s" % (type(e).__name__, e))

    return items, idx


# ---------------------------------------------------------------- 主流程

def full_fetch():
    """全量抓取：回溯 52 周真实历史 + 全量品种。本地手动跑，一天一次都嫌多。"""
    items = []
    used_names = set()
    idx = 1

    # ===== 1. 发改委每日价格（主源，含真实历史与商超价）=====
    print("[抓取] %s · 每日价格 ..." % CITY.get("name", ""))
    latest = fgj_latest_date()
    if not latest:
        print("  [error] 拿不到任何日期的数据，转为仅用农业农村局源")

    daily_cache = {}
    dates = []
    fgj_cat_of = {}          # 发改委原始品种名 -> 分类（用于算分类指数）
    if latest:
        print(f"  最新数据日: {latest}")
        # 全量模式是「重建」，陈旧也照建（建出来就是官方最新值）；
        # 但必须把状态喊出来，别让人以为数据是今天的。
        stale_check(LOCAL_SOURCE_NAME, latest)
        # 真实 52 周历史：逐周拉取
        dates = weekly_dates(latest)
        print(f"  回溯 {len(dates)} 周历史（{dates[0]} ~ {dates[-1]}）...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            results = list(ex.map(fgj_daily, dates))
        daily_cache = dict(zip(dates, results))
        got = sum(1 for v in daily_cache.values() if v)
        print(f"  历史样本命中 {got}/{len(dates)} 周")

        today = daily_cache.get(latest, {})

        # 真实商超价：选覆盖最多的 2 家超市（顺带取平台的真实快照日）
        supers = fgj_supermarkets()
        store_prices = []
        super_snapshot = None
        for p in supers[:2]:
            prices, snap = fgj_point_snapshot(p["id"], latest)
            store_prices.append({"name": p["name"], "prices": prices})
            super_snapshot = snap or super_snapshot
            print(f"  商超监测点: {p['name']} → {len(prices)} 个品种有报价")
        if super_snapshot and super_snapshot != latest:
            print(f"  [note] 商超快照日 {super_snapshot}（接口忽略 date 参数，只能取当前快照）")

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

            # 真实报价缺的周一律留 None：不补齐、不生成、不插值。
            # 以前这里 fill_series 前向填充、不足 8 周还退回随机数，
            # 结果停报周变成一条水平假线，图上完全看不出断档。
            series = norm_history(raw_series)
            series[-1] = round(row["avg"], 2)      # 末位是今日真实价

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
                "historyDates": dates,          # 与 history 一一对应的真实周日期
                "historyKind": "real",          # real=逐周实测 / index=分类指数推算 / none=无数据
                "historyReal": True,
                "prevObs": prev_obs,          # 上一个真实有报价的周（跳过停报周）
                "prevObsAge": prev_age,       # 距今几周；>4 视为季节性重新上市
                "obsWeeks": obs_weeks,        # 52 周里有几周真实有报价
                "source": LOCAL_SOURCE_NAME,
                "updated": latest,
            })
            used_names.add(raw_name)
            used_names.add(display_name)
            fgj_cat_of[raw_name] = cat
            idx += 1
        print(f"  -> 发改委入库 {len(items)} 种（含真实历史与商超价）")

        # 商超独有品种（目前只有猪五花肉）：商务局停更后，武汉唯一还能拿到的五花肉零售价。
        # 它没有历史（接口忽略 date 参数，回溯不了），所以 history 只保留末位一个真实点。
        extras = fgj_supermarket_extras(store_prices)
        if extras:
            fresh, _age = stale_check(SUPER_EXTRA.get("source") or "商超快照",
                                      super_snapshot, SUPER_SNAPSHOT_STALE_DAYS)
            if not fresh:
                print(f"          商超快照补充 0 种（{len(extras)} 种候选被陈旧闸门拦下）")
            else:
                for ex in extras:
                    h = blank_history()
                    h[-1] = ex["price"]
                    items.append({
                        "id": idx,
                        "name": ex["name"],
                        "rawName": ex["name"],
                        "pinyin": pinyin_initials(ex["name"]),
                        "category": ex["category"],
                        "unit": "500g",
                        "currentPrice": ex["price"],
                        "supermarketPrice": ex["price"],
                        "storeName": ex["store"],
                        "yearPosition": None,      # 只有一个快照点，不给百分位
                        "history": h,
                        "historyDates": dates_ending(WEEKS, super_snapshot or latest),
                        "historyKind": "none",     # 无历史，前端按「无数据」处理，不给假曲线
                        "historyReal": False,
                        "prevObs": None,
                        "prevObsAge": None,
                        "obsWeeks": 1,
                        "source": SUPER_EXTRA.get("source") or "商超快照",
                        "updated": super_snapshot or latest,
                    })
                    used_names.add(ex["name"])
                    idx += 1
                print(f"  -> 商超快照补充 {len(extras)} 种（数据日 {super_snapshot}）："
                      + "、".join(f"{e['name']} {e['price']}" for e in extras))

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
                    h = hist_from_index(it["price"], ratio)
                    hkind = "index"        # 形状来自分类真实指数，价格锚定当日真实报价
                else:
                    h = blank_history()    # 连分类指数都没有 → 整条留空，绝不生成
                    hkind = "none"
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
                    "historyDates": dates,
                    "historyKind": hkind,
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

    # ===== 3. 商务局周报（正文已图片化，解析器保留待其恢复）=====
    print("[抓取] 武汉市商务局 · 周报 ...")
    sw = sw_fetch(max_try=3)
    if not sw["ok"]:
        print(f"  [WARNING] 数据源陈旧 | 商务局·周报：{sw['reason']}")
        print("          该源本日贡献 0 种（源端没有结构化数据，不是网络问题）")
    else:
        fresh, _age = stale_check("商务局·周报", sw["date"])
        cand = len(sw["rows"].get("肉禽蛋") or []) + len(sw["rows"].get("水产") or [])
        if not fresh:
            print(f"          该源本日贡献 0 种（{cand} 种候选被陈旧闸门拦下）")
        else:
            n = 0
            for cat, rows in sw["rows"].items():
                for it in rows:
                    if it["name"] in used_names:
                        continue
                    ratio = cat_index.get(cat)
                    if ratio:
                        h, hkind = hist_from_index(it["price"], ratio), "index"
                    else:
                        h, hkind = blank_history(), "none"   # 无指数可用 → 留空
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
                        "historyDates": dates,
                        "historyKind": hkind,
                        "historyReal": False,
                        "prevObs": None,
                        "prevObsAge": None,
                        "obsWeeks": 52,
                        "source": "商务局·周报",
                        # 一律 ISO 日期：数据日取标题里的区间右端，比 URL 发布日更准
                        "updated": sw["date"] or latest,
                    })
                    used_names.add(it["name"])
                    idx += 1
                    n += 1
            print(f"  采用 {(sw.get('title') or sw['url'].split('/')[-1])[:26]}"
                  f"（数据日 {sw['date']}），补充 {n} 种")

    # ===== 4. 参考源：全国口径（水果 + 全国均价基准）=====
    # 放在本地源之后：重名时以本地实测为准（本地零售口径更贴近菜篮子）
    items, idx = add_reference(items, idx)

    # 发改委不可达时（GitHub 机器连不上裸 IP，是常态而非故障），
    # 把上一份 data.json 里的发改委品种原样继承过来，
    # 避免一次「降级成功」的全量把真实 52 周历史和商超价整体冲掉。
    if not any(it.get("source") == LOCAL_SOURCE_NAME for it in items):
        kept = restore_fgj_items(items)
        if kept:
            print(f"  [保底] 发改委不可达，从旧 {DATA_FILE} 继承 {kept} 个品种（含真实历史/商超价）")

    if not items:
        print("[fatal] 所有数据源都失败，不覆盖 data.json")
        sys.exit(1)

    save_items(items, tag="全量")


# ---------------------------------------------------------------- 每日增量


def rev_alias():
    """前端显示名 -> 原始名的反查表。名字归一随城市配置变，所以每次现算。"""
    return {v: k for k, v in NAME_ALIAS.items()}


def item_key(it):
    """品种的稳定标识：优先 rawName，老数据用别名反查，最后退回显示名。"""
    return it.get("rawName") or rev_alias().get(it.get("name", ""), it.get("name", ""))


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
        if it.get("source") != LOCAL_SOURCE_NAME:
            continue
        k = item_key(it)
        if k in have:
            continue
        items.append(it)
        have.add(k)
        n += 1
    return n


def finalize_history(items):
    """
    统一兜底：history / historyDates 必须等长，historyKind 必须存在。

    主力场景是 restore_fgj_items 继承进来的老格式数据——那些 item 没有
    historyDates 字段，直接落盘会让前端读到空日期轴。
    """
    for it in items:
        h = norm_history(it.get("history"))
        it["history"] = h
        dts = it.get("historyDates") or []
        if len(dts) != len(h) or any(d is None for d in dts):
            dts = dates_ending(len(h), it.get("updated")
                               or datetime.now().strftime("%Y-%m-%d"))
        it["historyDates"] = dts
        if not it.get("historyKind"):
            if it.get("historyReal"):
                it["historyKind"] = "real"
            elif any(v is not None for v in h):
                it["historyKind"] = "index"
            else:
                it["historyKind"] = "none"


def save_items(items, tag=""):
    """统一出口：排序 + 重编号 + 落盘。"""
    CAT_ORDER = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    items.sort(key=lambda x: (CAT_ORDER.get(x["category"], 9), x["id"]))
    for i, it in enumerate(items, 1):
        it["id"] = i

    finalize_history(items)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    stats = {}
    for it in items:
        stats[it["category"]] = stats.get(it["category"], 0) + 1
    real_hist = sum(1 for it in items if it.get("historyReal"))
    with_sp = sum(1 for it in items if it.get("supermarketPrice"))
    kinds = {}
    for it in items:
        kinds[it.get("historyKind")] = kinds.get(it.get("historyKind"), 0) + 1
    blanks = sum(1 for it in items if all(v is None for v in (it.get("history") or [])))
    print(f"\n[完成{('·' + tag) if tag else ''}] {len(items)} 个品种 | 分类: {stats}")
    print(f"       真实历史: {real_hist} 种 | 真实商超价: {with_sp} 种")
    print(f"       历史来源: {kinds} | 整条留空: {blanks} 种")


def append_price(it, price, date_str, gap_weeks=1):
    """
    把今天的新价追加进 52 周序列，淘汰最老的一周，重算百分位。
    - 同一天重复跑（手动触发两次）不会产生重复点，只覆盖最后一位
    - 历史为空 / 不足 52 周时用 None 对齐长度，不用旧价冒充历史
    - historyDates 与 history 同步右移，保证日期和价格永不错位
    返回 True 表示已更新，False 表示被健康检查拦下。
    """
    try:
        price = round(float(price), 2)
    except (TypeError, ValueError):
        return False
    if not price or price <= 0 or price > 10000:
        return False

    # 必须保留 None（断档占位）。原来这里用 isinstance(v, (int, float)) 过滤，
    # 会把 null 全部剔除、序列被压缩变短，与 historyDates 整体错位。
    h = norm_history(it.get("history"))
    old = next((v for v in reversed(h) if v is not None), None)

    # -------- 健康检查：无征兆的暴涨/暴跌一律跳过，保留旧数据 --------
    if old and not price_sane(old, price, gap_weeks):
        print(f"  [skip] {it.get('name')} 价格异常 {old} → {price}"
              f"（{price / old * 100:.0f}%），保留旧值")
        return False

    # 不许把 updated 往回拨。
    # 周末/节假日 fgj_latest_date() 会平滑回退到最近一个有数据的日期，
    # 那个日期可能比 data.json 里已经存着的还早（比如数据集已到 10-26，
    # 而这一轮只拿到 10-23）。此时追加会在序列尾部多出一个倒着的点，
    # historyDates 也会整体倒退，图上就是一条倒退的时间轴。
    prev_date = str(it.get("updated") or "")[:10]
    if prev_date and date_str < prev_date:
        print(f"  [skip] {it.get('name')} 数据日 {date_str} 早于现有 {prev_date}，不回溯覆盖")
        return False

    if it.get("updated") == date_str:
        h[-1] = price                      # 同日重跑：覆盖，不追加
    else:
        # 长度对齐用 None 补，绝不拿最早一周的旧价向前填充
        while len(h) < WEEKS - 1:
            h.insert(0, None)
        h.append(price)
        if len(h) > WEEKS:
            h = h[-WEEKS:]

    it["history"] = h
    it["historyDates"] = dates_ending(len(h), date_str)   # 日期随价格同步右移
    it["currentPrice"] = price
    it["yearPosition"] = year_position(h, price)
    it["updated"] = date_str

    if it.get("source") == LOCAL_SOURCE_NAME:
        it["historyReal"] = True
        it["historyKind"] = "real"
        # 上一周真实有报价的值（跳过停报周留下的 None）
        it["prevObs"] = next((v for v in reversed(h[:-1]) if v is not None), None)
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
                 if it.get("source") == LOCAL_SOURCE_NAME}
    index_supp = {item_key(it): it for it in items
                  if it.get("source") != LOCAL_SOURCE_NAME}
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
        # 陈旧闸门：数据日照旧写（写的是官方最新值，不造假），但不计入当日有效更新数。
        fgj_fresh, _age = stale_check(LOCAL_SOURCE_NAME, latest)
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
            if append_price(it, row["avg"], latest, gap_weeks=max(1, gap)) and fgj_fresh:
                updated += 1

        if miss:
            print(f"  [提示] {len(miss)} 个新品种未入库（如 {', '.join(miss[:3])}），需 --mode=full 补历史")
    else:
        # GitHub 的机器连不上发改委裸 IP（实测 ConnectTimeout），这是常态不是故障。
        # 此时发改委那 40 个品种原样保留：价格、历史、商超价、updated 日期都不动，
        # 前端会显示该品种的更新时间偏旧，属于如实反映。
        print("  [warn] 发改委今日不可达（境外服务器常态），该部分品种保留上次数据")

    if not latest:
        latest = datetime.now().strftime("%Y-%m-%d")

    # -------- 1b. 商超快照（与发改委每日均价表相互独立）--------
    # 与 full 模式同一口径：两店比价取最低，storeName 记该店，价格相同中百优先。
    # 必须在本轮抓到的数据里重算，不能拿上一轮的旧商超价参与比较，
    # 否则昨天那家店的最低价会挡住今天的真实报价。
    try:
        store_prices = []
        super_snapshot = None
        for p in fgj_supermarkets()[:2]:
            prices, snap = fgj_point_snapshot(p["id"], latest)
            store_prices.append({"name": p["name"], "prices": prices})
            super_snapshot = snap or super_snapshot
            print(f"  商超 {p['name']}: {len(prices)} 个品种")
        if super_snapshot and super_snapshot != latest:
            print(f"  [note] 商超快照日 {super_snapshot}（接口忽略 date 参数，只能取当前快照）")

        for raw_name, it in index_fgj.items():
            sp, store = pick_cheapest_supermarket(store_prices, raw_name)
            if sp is not None:
                it["supermarketPrice"] = sp
                it["storeName"] = store

        # 商超独有品种（猪五花肉）走独立陈旧闸门：它是周更快照，不能按日更的 3 天算
        extras = fgj_supermarket_extras(store_prices)
        if extras:
            fresh, _age = stale_check(SUPER_EXTRA.get("source") or "商超快照",
                                      super_snapshot, SUPER_SNAPSHOT_STALE_DAYS)
            n = 0
            if fresh:
                for ex in extras:
                    it = index_supp.get(ex["name"])
                    if not it:
                        print(f"  [提示] 商超快照有新品种「{ex['name']}」，需 --mode=full 建条目")
                        continue
                    gap = weeks_since(it.get("updated") or "")
                    if append_price(it, ex["price"], super_snapshot, gap_weeks=max(1, gap)):
                        it["supermarketPrice"] = ex["price"]
                        it["storeName"] = ex["store"]
                        n += 1
                updated += n
            print(f"  商超快照补充 {n} 种（{len(extras)} 种候选，数据日 {super_snapshot}）")
    except Exception as e:
        print(f"  [error] 商超价: {type(e).__name__}")

    # -------- 2. 农业局批发价（3 个栏目 × 最新 1 篇）--------
    # 数据日必须用文章自己的日期（形如 t20261026_...），不能借用发改委的 latest：
    # 两个源更新节奏不同，借用等于把批发价改标成零售价那天，陈旧检测也会失灵。
    print("[抓取] 农业农村局 · 今日批发价 ...")
    for src in NYNCJ_SOURCES:
        try:
            urls = latest_article_urls(src["column"], 1)
            if not urls:
                print(f"  [WARNING] 数据源陈旧 | 农业农村局·{src['category']}：栏目里没有文章")
                continue
            adate = article_date(urls[0]) or latest
            cand = merge_markets([parse_price_table(u) for u in urls])
            fresh, _age = stale_check(f"农业农村局·{src['category']}", adate)
            if fresh:
                n = 0
                for it_new in cand:
                    it = index_supp.get(it_new["name"])
                    if not it:
                        continue
                    gap = weeks_since(it.get("updated") or "")
                    if append_price(it, it_new["price"], adate, gap_weeks=max(1, gap)):
                        n += 1
                updated += n
                print(f"  {src['category']}: 更新 {n} 种（数据日 {adate}）")
            else:
                print(f"  {src['category']}: 更新 0 种（{len(cand)} 种候选被陈旧闸门拦下）")
        except Exception as e:
            print(f"  [error] {src['category']}: {type(e).__name__}")

    # -------- 3. 商务局周报（正文已图片化：能解析才更新，解析不了就明说）--------
    print("[抓取] 商务局 · 最新周报 ...")
    sw = sw_fetch(max_try=3)
    if not sw["ok"]:
        print(f"  [WARNING] 数据源陈旧 | 商务局·周报：{sw['reason']}")
        print("          该源本日贡献 0 种（源端没有结构化数据，不是网络问题）")
    else:
        fresh, _age = stale_check("商务局·周报", sw["date"])
        cand = sum(len(v) for v in sw["rows"].values())
        if fresh:
            n = 0
            for cat, rows in sw["rows"].items():
                for it_new in rows:
                    it = index_supp.get(it_new["name"])
                    if not it:
                        continue
                    gap = weeks_since(it.get("updated") or "")
                    if append_price(it, it_new["price"], sw["date"], gap_weeks=max(1, gap)):
                        n += 1
            updated += n
            print(f"  周报更新 {n} 种（数据日 {sw['date']}）")
        else:
            print(f"  周报更新 0 种（{cand} 种候选被陈旧闸门拦下）")

    # -------- 4. 参考源：全国口径（周报/日报 + 新发地）--------
    try:
        updated += refresh_reference(items)
    except Exception as e:
        print(f"  [error] 参考源: {type(e).__name__}")

    if updated == 0:
        print("[warn] 本次没有任何品种更新，保留原 data.json 不动")
        return

    save_items(items, tag="增量")
    print(f"       本次更新 {updated} 个价格点")


def refresh_reference(items):
    """
    增量模式下刷新参考源：只取最新一期周报 / 最新一天日价，追加到序列末尾。

    不做 52 周回溯（那是 full 模式的事），请求数控制在个位数，
    本地政务网挂了也不影响参考源照样更新。
    """
    ref = [it for it in items if it.get("source") in REF_SOURCES]
    if not ref:
        print("[参考] 现有 data.json 里没有参考源品种，跳过（跑 --mode=full 补）")
        return 0
    by_name = {it["name"]: it for it in ref}
    n = 0

    if CITY.get("use_national"):
        print("[抓取] 全国参考 · 最新一期 ...")
        try:
            # 周报：分品种水果（只取最新 3 期，取到有表5 的那期为止）
            rows = agri_national.fetch_weekly_rows(page_size=3)
            for row in rows:
                fruits = agri_national.parse_fruit_table(row["content"])
                if not fruits:
                    continue
                for fruit, price in fruits.items():
                    it = by_name.get("全国" + fruit)
                    if it and append_price(it, price, row["date"]):
                        n += 1
                print("  周报 %s：%d 种水果" % (row["date"], len(fruits)))
                break

            # 日报：全国均价基准
            drows = agri_national.fetch_daily_rows(days=10)
            if drows:
                last = drows[-1]
                for display, _cat, field in agri_national.DAILY_ITEMS:
                    it = by_name.get(display)
                    if not it:
                        continue
                    bucket = (last["values"] or {}).get(field) or {}
                    v = bucket.get("均价") if field in ("vegetables", "fruits") \
                        else bucket.get(display.replace("全国", ""))
                    if v and append_price(it, v, last["date"]):
                        n += 1
                print("  日报 %s：全国基准已刷新" % last["date"])
        except Exception as e:
            print("  [error] 全国参考: %s: %s" % (type(e).__name__, e))

    if CITY.get("use_xinfadi"):
        print("[抓取] 新发地 · 最新一天 ...")
        try:
            day, snap = xinfadi.day_snapshot(datetime.now().strftime("%Y-%m-%d"))
            if day:
                for key, price in snap.items():
                    it = by_name.get(xinfadi.variety_map.display_of(key))
                    if it and append_price(it, price, day):
                        n += 1
                print("  %s：%d 个水果品类" % (day, len(snap)))
            else:
                print("  [warn] 最近 4 天新发地无报价")
        except Exception as e:
            print("  [error] 新发地: %s: %s" % (type(e).__name__, e))

    return n


def main():
    mode = "daily"
    city = None
    for a in sys.argv[1:]:
        if a.startswith("--mode="):
            mode = a.split("=", 1)[1].strip()
        elif a.startswith("--city="):
            city = a.split("=", 1)[1].strip()
        elif a in ("--full", "-f"):
            mode = "full"
        elif a in ("--daily", "-d"):
            mode = "daily"

    if mode not in ("daily", "full"):
        print(f"[error] 未知模式 {mode}，可选 daily / full")
        sys.exit(2)

    if city:
        configure(city)

    print(f"===== {CITY.get('title') or '菜篮子'} · {mode} 模式 =====")
    print(f"      城市: {CITY.get('province')}{CITY.get('name')}({CITY.get('id')})"
          f" | 本地口径: {CITY.get('local_unit_label')}"
          f" | 全国参考: {'开' if CITY.get('use_national') else '关'}"
          f" | 新发地: {'开' if CITY.get('use_xinfadi') else '关'}")
    if mode == "full":
        full_fetch()
    else:
        daily_update()


if __name__ == "__main__":
    main()
