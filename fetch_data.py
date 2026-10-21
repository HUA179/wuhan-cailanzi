# -*- coding: utf-8 -*-
"""
武汉菜篮子 - 数据抓取脚本
=========================
数据源（全部为政府官网公开数据，无需登录、无反爬）
  武汉市农业农村局「数据发布」栏目（每日更新）
    - 蔬菜批发价格：四季美市场 + 白沙洲市场（每天各一篇）
    - 粮油批发价格：白沙洲市场
    - 水产品批发价格：白沙洲市场
  武汉市商务局「生活必需品市场价格监测」栏目（每周更新）
    - 猪肉 / 牛羊肉 / 白条鸡 / 鸡蛋 / 部分水产品 —— 唯一提供肉禽蛋的官方源

输出：data.json（与前端 MOCK_ITEMS 结构完全一致的数组）

运行：
    python fetch_data.py
依赖：
    pip install requests beautifulsoup4 pypinyin
"""

import json
import random
import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypinyin import lazy_pinyin, Style

BASE = "https://nyncj.wuhan.gov.cn"          # 武汉市农业农村局
SW_BASE = "https://sw.wuhan.gov.cn"          # 武汉市商务局（生活必需品周报，含肉禽蛋）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}
TIMEOUT = 20

# 栏目配置：column 路径 -> (前端分类, 抓最新几篇文章)
# 蔬菜每天发两篇（四季美/白沙洲各一篇），取最新 2 篇做两市场均价合并
SOURCES = [
    {"column": "/zwgk_25/fdzdgknr/snsj/scpfjg/", "category": "蔬菜",   "take": 2},
    {"column": "/zwgk_25/fdzdgknr/snsj/scppfjg/", "category": "水产",   "take": 1},
    {"column": "/zwgk_25/fdzdgknr/snsj/lypfjg/",  "category": "米面粮油", "take": 1},
]

# 武汉市商务局「生活必需品市场价格监测」周报：唯一提供肉禽蛋的官方源
SW_SOURCE = {"column": "/zfxxgk/fdzdgknr/sjfb/jgjczb/", "take": 10}

STORES = ["盒马", "小象超市"]

# 官网没有肉禽蛋栏目，用模拟数据补充（真实数据源找到后删掉这段即可）
POULTRY_MOCK = [
    {"name": "鸡蛋",     "currentPrice": 4.20},
    {"name": "猪后腿肉", "currentPrice": 15.80},
    {"name": "鸡胸肉",   "currentPrice": 9.50},
]


# ---------------------------------------------------------------- 网络

def get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.encoding = resp.apparent_encoding or "utf-8"
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def latest_article_urls(column_path, take, base=BASE):
    """从栏目列表页提取最新 take 篇文章的绝对 URL。"""
    list_url = urljoin(base, column_path)
    soup = get_soup(list_url)
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # 文章页形如 ./202610/t20261021_2865618.html 或 .shtml
        if re.search(r"\d{6}/t\d+_\d+\.s?html?", href):
            urls.append(urljoin(list_url, href))
        if len(urls) >= take:
            break
    return urls


# ---------------------------------------------------------------- 表格解析

def parse_price_table(article_url):
    """
    解析一篇价格公示文章，返回 [{name, price(元/公斤), date}]。
    自动识别表头里的「名称列」和「价格列」（优先大宗价，其次均价，
    再次取最高价/最低价的均值）。
    """
    soup = get_soup(article_url)
    table = soup.find("table")
    if not table:
        print(f"  [warn] 页面没有表格: {article_url}")
        return []

    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if cells:
            rows.append(cells)
    if len(rows) < 2:
        return []

    header = rows[0]

    def find_col(*keywords, exclude=()):
        for i, h in enumerate(header):
            if any(x in h for x in exclude):
                continue
            if any(k in h for k in keywords):
                return i
        return None

    # 名称列：排除「市场名称」这种干扰列
    name_i = find_col("品名", "品种", "名称", exclude=("市场",))
    dz_i   = find_col("大宗价")          # 大宗价（最有代表性）
    avg_i  = find_col("均价", "中间价", "批发价")
    hi_i   = find_col("最高价")
    lo_i   = find_col("最低价")
    date_i = find_col("时间", "日期")

    if name_i is None:
        print(f"  [warn] 识别不了表头: {header}")
        return []

    # 判断单位：标题/表头提到「公斤」则前端需要除以 2 换算成 元/500g
    page_text = soup.get_text()
    per_kg = "公斤" in page_text or "千克" in page_text

    def to_float(s):
        m = re.search(r"\d+(?:\.\d+)?", s.replace(",", ""))
        return float(m.group()) if m else None

    items = []
    for cells in rows[1:]:
        if len(cells) <= name_i:
            continue
        name = re.sub(r"\s+", "", cells[name_i])
        if not name or name in ("合计", "平均"):
            continue

        price = None
        if dz_i is not None and len(cells) > dz_i:
            price = to_float(cells[dz_i])
        if price is None and avg_i is not None and len(cells) > avg_i:
            price = to_float(cells[avg_i])
        if price is None and hi_i is not None and lo_i is not None \
                and len(cells) > max(hi_i, lo_i):
            hi, lo = to_float(cells[hi_i]), to_float(cells[lo_i])
            if hi is not None and lo is not None:
                price = (hi + lo) / 2
        if price is None or price <= 0 or price > 1000:
            continue

        date = cells[date_i] if date_i is not None and len(cells) > date_i else ""
        if per_kg:
            price = price / 2  # 元/公斤 -> 元/500g，与前端单位一致
        items.append({"name": name, "price": round(price, 2), "date": date})
    return items


def merge_markets(articles):
    """同一菜品在多个市场的价格取平均（如四季美 + 白沙洲）。"""
    bucket = {}
    for art in articles:
        for it in art:
            bucket.setdefault(it["name"], []).append(it["price"])
    return [{"name": n, "price": round(sum(ps) / len(ps), 2)}
            for n, ps in bucket.items()]


def parse_sw_weekly(article_url):
    """
    解析武汉市商务局「生活必需品市场监测」周报。
    表格是分组结构（单格行表示分组），例如：
        肉类（零售） / 猪肉 / 后腿肉 元/公斤 25.37 ...
    返回 {"肉禽蛋": [...], "水产": [...]}，价格已换算成 元/500g。
    """
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
        cells = [c for c in cells if c != ""]

        # 单格行 = 分组标题
        if len(cells) == 1:
            txt = cells[0]
            if any(k in txt for k in GROUP_KEYS):
                group, subgroup = txt, ""
            else:
                subgroup = txt          # 如 猪肉 / 牛肉 / 羊肉 / 生猪
            continue

        # 数据行：名称, 单位, 本期价格, ...
        if len(cells) < 3 or "元" not in cells[1]:
            continue
        name, unit, raw = cells[0], cells[1], cells[2]
        if "-" in raw or not re.search(r"\d", raw):
            continue                 # 空值（官网用 "-" 占位）
        price = float(re.search(r"\d+(?:\.\d+)?", raw).group())
        if "公斤" in unit:
            price = price / 2        # 元/公斤 -> 元/500g

        # 只取「零售」分组，跳过周报后半段的「批发」分组
        if "零售" not in group:
            continue

        if group.startswith(("肉类", "禽类", "蛋类")):
            cat = "肉禽蛋"
            if group.startswith("肉类") and subgroup in ("猪肉", "牛肉", "羊肉") \
                    and not name.startswith(subgroup[0]):
                name = subgroup[0] + name     # 后腿肉 -> 猪后腿肉，牛腿肉保持
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
    """西红柿 -> xhs"""
    return "".join(lazy_pinyin(name, style=Style.FIRST_LETTER))


def gen_history(current, name, weeks=52):
    """
    生成 52 周模拟历史（以当前价为终点反向随机游走 + 轻微季节波动）。
    用菜品名做随机种子，保证每次运行结果一致、不同菜走势不同。
    """
    rng = random.Random("whcz:" + name)
    series = [float(current)]
    for i in range(weeks - 1):
        change = rng.uniform(-0.04, 0.038)          # 周环比
        seasonal = 0.02 * (1 if i % 26 < 13 else -1)  # 粗略季节项
        prev = series[-1] / (1 + change + seasonal * rng.random())
        prev = max(prev, current * 0.35)            # 防止跌出合理区间
        prev = min(prev, current * 2.8)
        series.append(round(prev, 2))
    series.reverse()
    return series


def year_position(history, current):
    """当前价在近一年序列中的百分位（0-100，越高越贵）。"""
    below = sum(1 for p in history if p <= current)
    return min(100, round(below / len(history) * 100))


def build_item(idx, name, category, market_price):
    rng = random.Random("store:" + name)
    supermarket_price = round(market_price * (1 + rng.uniform(-0.08, 0.15)), 2)
    history = gen_history(market_price, name)
    return {
        "id": idx,
        "name": name,
        "pinyin": pinyin_initials(name),
        "category": category,
        "unit": "500g",
        "currentPrice": market_price,
        "supermarketPrice": supermarket_price,   # 暂无商超数据源，按市场价随机浮动模拟
        "storeName": rng.choice(STORES),
        "yearPosition": year_position(history, market_price),
        "history": history,
    }


# ---------------------------------------------------------------- 主流程

def main():
    all_items = []
    idx = 1

    for src in SOURCES:
        print(f"[抓取] {src['category']} 栏目 ...")
        try:
            urls = latest_article_urls(src["column"], src["take"])
            if not urls:
                print(f"  [warn] 列表页没找到文章，跳过 {src['category']}")
                continue
            print(f"  最新文章: {[u.split('/')[-1] for u in urls]}")
            articles = []
            for u in urls:
                parsed = parse_price_table(u)
                print(f"  解析 {u.split('/')[-1]}: {len(parsed)} 条")
                articles.append(parsed)
            merged = merge_markets(articles)
            for it in merged:
                all_items.append(build_item(idx, it["name"], src["category"], it["price"]))
                idx += 1
            print(f"  -> {src['category']} 入库 {len(merged)} 种")
        except Exception as e:
            print(f"  [error] {src['category']} 抓取失败: {e}")

    # ---- 武汉市商务局周报：肉禽蛋 + 补全水产（大带鱼、大黄鱼等白沙洲没有的）----
    # 部分期次正文为空（数据未渲染），因此从最新一期往前找，取第一篇有数据的
    print("[抓取] 商务局周报（肉禽蛋）...")
    poultry_ok = False
    try:
        sw_urls = latest_article_urls(SW_SOURCE["column"], SW_SOURCE["take"], base=SW_BASE)
        for u in sw_urls:
            sw = parse_sw_weekly(u)
            if not sw.get("肉禽蛋"):
                print(f"  {u.split('/')[-1]} 无有效数据，继续往前找")
                continue
            print(f"  采用: {u.split('/')[-1]}")
            for it in sw["肉禽蛋"]:
                all_items.append(build_item(idx, it["name"], "肉禽蛋", it["price"]))
                idx += 1
            # 水产：只补已有列表里没有的品种，避免和批发价重复
            exist = {it["name"] for it in all_items}
            added = 0
            for it in sw.get("水产", []):
                if it["name"] not in exist:
                    all_items.append(build_item(idx, it["name"], "水产", it["price"]))
                    idx += 1
                    added += 1
            print(f"  -> 肉禽蛋 {len(sw['肉禽蛋'])} 种，新增水产 {added} 种")
            poultry_ok = True
            break
        if not sw_urls:
            print("  [warn] 列表页没找到周报")
    except Exception as e:
        print(f"  [error] 商务局周报抓取失败: {e}")

    # 兜底：商务局抓不到时，用内置模拟数据保证分类不为空
    if not poultry_ok:
        print("  [warn] 使用内置模拟数据兜底肉禽蛋")
        for m in POULTRY_MOCK:
            all_items.append(build_item(idx, m["name"], "肉禽蛋", m["currentPrice"]))
            idx += 1

    if not all_items:
        print("[fatal] 什么数据都没抓到，不生成 data.json（避免覆盖旧文件）")
        sys.exit(1)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    cats = {}
    for it in all_items:
        cats[it["category"]] = cats.get(it["category"], 0) + 1
    print(f"\n[完成] data.json 共 {len(all_items)} 个菜品: {cats}")


if __name__ == "__main__":
    main()
