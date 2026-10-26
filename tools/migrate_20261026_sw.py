# -*- coding: utf-8 -*-
"""
一次性数据迁移：下线商务局周报，改挂商超快照的「猪五花肉」

背景（2026-10-26 实测）
-----------------------
武汉市商务局「生活必需品市场监测情况」自 2026-09-14 起，正文从 HTML 表格改成
6 张 JPG，页面也没有任何 xls/xlsx/doc/pdf 附件。解析器拿不到表格，一路回溯到
2026-09-11 那一期，于是 7 个品种的价格和 updated 全卡在 9-11，日志却照打「更新 7 种」。

侦察结论：这 7 个品种**没有同口径的公开官方替代源**（湖北省发改委被瑞数 WAF 挡在
412、商务部商务预报只到全国口径、白沙洲批发没有带鱼/黄鱼）。所以：

    猪后腿肉   → 与发改委「猪腿夹肉」（规格：后腿夹肉）同部位，重复，下线
    猪五花肉   → 商超监测点有真报价，改挂「发改委·商超」快照，**保留**
    牛腿肉     → 与发改委「牛肉（去骨肉）」重叠且无源更新，下线
    羊腿肉     → 与发改委「羊肉（带骨肉）」重叠且无源更新，下线
    鲢鱼       → 已有农业农村局「鲢子鱼」批发价，零售口径无源，下线
    大带鱼     → 已有「全国大带鱼」参考口径，重复，下线
    大黄鱼     → 全网无公开官方源，下线

用法：
    python tools/migrate_20261026_sw.py            # 只看会改什么（dry-run）
    python tools/migrate_20261026_sw.py --apply    # 真写 data.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_data as F

DROP_SOURCE = "商务局·周报"
DROP_NAMES = ["猪后腿肉", "牛腿肉", "羊腿肉", "鲢鱼", "大带鱼", "大黄鱼"]
KEEP_REPLACE = "猪五花肉"


def main():
    apply = "--apply" in sys.argv
    F.configure()

    with open(F.DATA_FILE, encoding="utf-8") as f:
        items = json.load(f)
    before = len(items)

    drop = [it for it in items if it.get("source") == DROP_SOURCE]
    kept = [it for it in items if it.get("source") != DROP_SOURCE]

    print(f"[迁移] 现有 {before} 个品种，商务局来源 {len(drop)} 个：")
    for it in drop:
        print(f"   - {it['name']:<8} {it['currentPrice']:>7}  {it.get('updated')}")

    print(f"\n[迁移] 下线 {len(DROP_NAMES)} 个（重复/无源），保留并改源 {KEEP_REPLACE}")
    for n in DROP_NAMES:
        hit = [it["name"] for it in drop if it["name"] == n]
        print(f"   drop  {n:<8} {'✓ 已找到' if hit else '（不在商务局来源里，跳过）'}")

    # 取商超快照里的猪五花肉
    store_prices, snap = [], None
    for p in F.fgj_supermarkets()[:2]:
        prices, s = F.fgj_point_snapshot(p["id"])
        store_prices.append({"name": p["name"], "prices": prices})
        snap = s or snap
    ex = {e["name"]: e for e in F.fgj_supermarket_extras(store_prices)}
    pork = ex.get(KEEP_REPLACE)
    if not pork:
        print("[迁移] 商超快照里没有猪五花肉，中止")
        return 1
    fresh, age = F.stale_check(F.SUPER_EXTRA.get("source") or "商超快照",
                               snap, F.SUPER_SNAPSHOT_STALE_DAYS)
    print(f"\n[迁移] 猪五花肉 {pork['price']} 元/500g @ {pork['store']}，快照日 {snap}（{age} 天）")

    old = next((it for it in drop if it["name"] == KEEP_REPLACE), None)
    if old:
        old_updated, old_price = old.get("updated"), old.get("currentPrice")
        old.update({
            "currentPrice": pork["price"],
            "supermarketPrice": pork["price"],
            "storeName": pork["store"],
            "source": F.SUPER_EXTRA.get("source") or "商超快照",
            "updated": snap,
            # 没有历史：商超接口忽略 date 参数，回溯不了；宁可空着也不画假曲线
            "history": [None] * (F.WEEKS - 1) + [pork["price"]],
            "historyDates": F.dates_ending(F.WEEKS, snap),
            "historyKind": "none",
            "historyReal": False,
            "yearPosition": None,
            "prevObs": None,
            "prevObsAge": None,
            "obsWeeks": 1,
        })
        kept.append(old)
        print(f"[迁移] 「{KEEP_REPLACE}」{old_price} @{old_updated}（商务局）"
              f" → {pork['price']} @{snap}（{pork['store']} 商超快照）")
    else:
        print(f"[迁移] 老数据里没有「{KEEP_REPLACE}」，改用 full 模式新建成条目")

    # 其余待下线品种：确认它们确实不在保留集里
    after = len(kept)
    print(f"\n[迁移] {before} → {after} 个品种")
    if not apply:
        print("[迁移] dry-run，未写盘。确认后加 --apply")
        return 0

    F.save_items(kept, tag="迁移")
    print("[迁移] 已写入", F.DATA_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
