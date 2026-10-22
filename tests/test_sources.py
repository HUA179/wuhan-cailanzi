# -*- coding: utf-8 -*-
"""
离线单元测试（不联网）
=====================
覆盖三件最容易悄悄坏掉的事：
    1. 品种映射表（错一个，橘子价就会被苹果价污染）
    2. 周报表5解析（表格序号在历史期数里会变）
    3. 日报句子抽数（正则抽错一位，全国基准全歪）

再覆盖城市配置的载入与报错行为。

运行：python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cities import load_city              # noqa: E402
from sources import agri_national, variety_map, xinfadi   # noqa: E402


# ---------------------------------------------------------------- 映射表

class TestVarietyMap(unittest.TestCase):
    def test_apple(self):
        for name in ["富士", "花牛", "黄元帅", "嘎啦", "辽宁寒富苹果", "蛇果", "123沙果（K9）"]:
            if name.startswith("123"):
                # 沙果不是苹果，必须映射不到
                self.assertIsNone(variety_map.classify(name), name)
            else:
                self.assertEqual(variety_map.classify(name), "apple", name)

    def test_citrus(self):
        # 「金秋砂糖桔」含「糖」字，黑名单若不是整词就会误杀
        for name in ["蜜桔", "叶桔", "金秋砂糖桔", "爱媛", "沃柑", "丑橘"]:
            self.assertEqual(variety_map.classify(name), "citrus", name)

    def test_watermelon(self):
        # 「无籽西瓜」含「籽」字，黑名单若写成单字也会误杀
        for name in ["无籽西瓜", "甜王", "麒麟", "黑美人", "特小凤"]:
            self.assertEqual(variety_map.classify(name), "watermelon", name)

    def test_dried_and_nuts_excluded(self):
        for name in ["香蕉干", "葡萄干", "核桃", "板栗", "葵花籽", "五香花生米", "猕猴桃干"]:
            self.assertIsNone(variety_map.classify(name), name)

    def test_ambiguous_stays_unknown(self):
        # 青州蜜在多地指青州蜜桃，不能算橘子；橙/柚/柠檬也不算橘子
        for name in ["青州蜜", "脐橙", "蜜柚", "柠檬", "哈密瓜", "玉菇", "鸡心果"]:
            self.assertIsNone(variety_map.classify(name), name)

    def test_spec_suffix_stripped(self):
        self.assertEqual(variety_map.classify("红香酥梨（纸箱）"), None)   # 梨不在四类里
        self.assertEqual(variety_map.classify("富士（纸箱）"), "apple")

    def test_display_and_category(self):
        self.assertEqual(variety_map.display_of("citrus"), "橘子")
        self.assertEqual(variety_map.category_of("apple"), "水果")


# ---------------------------------------------------------------- 周报表5

FRUIT_TABLE_HTML = """
<div><p>表4 上涨蔬菜</p>
<table><tr><th>产品种类</th><th>上周</th><th>本周</th><th>环比</th></tr>
<tr><td>青椒</td><td>4.40</td><td>4.07</td><td>-7.5%</td></tr></table>
<p>表5 重点监测的水果价格及变化幅度</p>
<table>
<tr><th>产品种类</th><th>上周</th><th>本周</th><th>去年同期</th><th>环比</th><th>同比</th></tr>
<tr><td>单位（元/公斤）</td><td>（%）</td></tr>
<tr><td>鸭梨</td><td>5.37</td><td>5.28</td><td>5.52</td><td>-1.7%</td><td>-4.3%</td></tr>
<tr><td>富士苹果</td><td>8.96</td><td>8.91</td><td>9.34</td><td>-0.6%</td><td>-4.6%</td></tr>
<tr><td>巨峰葡萄</td><td>9.84</td><td>9.82</td><td>9.98</td><td>-0.2%</td><td>-1.6%</td></tr>
<tr><td>香蕉</td><td>4.94</td><td>4.89</td><td>4.99</td><td>-1.0%</td><td>-2.0%</td></tr>
<tr><td>菠萝</td><td>7.45</td><td>7.39</td><td>8.86</td><td>-0.8%</td><td>-16.6%</td></tr>
<tr><td>西瓜</td><td>3.52</td><td>3.65</td><td>3.69</td><td>3.7%</td><td>-1.1%</td></tr>
</table></div>
"""


class TestWeeklyParse(unittest.TestCase):
    def test_parse_table5(self):
        got = agri_national.parse_fruit_table(FRUIT_TABLE_HTML)
        self.assertEqual(len(got), 6)
        self.assertEqual(got["富士苹果"], 8.91)
        self.assertEqual(got["西瓜"], 3.65)
        # 蔬菜表不能被当成水果表
        self.assertNotIn("青椒", got)

    def test_empty(self):
        self.assertEqual(agri_national.parse_fruit_table(""), {})
        self.assertEqual(agri_national.parse_fruit_table("<p>无表格</p>"), {})

    def test_grid_length(self):
        dates = agri_national._grid("2026-10-12", 5)
        self.assertEqual(len(dates), 5)
        self.assertEqual(dates[-1], "2026-10-12")
        self.assertEqual(dates[0], "2026-09-14")

    def test_pick_tolerance(self):
        pts = [("2026-10-01", 5.0), ("2026-10-08", 6.0)]
        self.assertEqual(agri_national._pick(pts, "2026-10-09"), 6.0)       # 1 天内
        self.assertIsNone(agri_national._pick(pts, "2026-10-20"))           # 超出容差 → None


# ---------------------------------------------------------------- 日报抽数

DAILY_ROW = {
    "daylyDate": "2026-10-21 00:00:00",
    "fruitsConclusion": "重点监测的6种水果平均价格为6.78元/公斤，比昨天上升1.6%。",
    "vegetablesConclusion": "重点监测的28种蔬菜平均价格为4.18元/公斤，比昨天上升0.7%；",
    "animalConclusion": ("猪肉平均价格为15.76元/公斤，比昨天下降0.6%；牛肉72.81元/公斤，"
                         "比昨天下降1.0%；羊肉67.32元/公斤，比昨天下降1.5%；"
                         "鸡蛋9.48元/公斤，比昨天下降0.9%；白条鸡17.02元/公斤，比昨天下降1.2%。"),
    "aquaticConclusion": ("鲫鱼19.56元/公斤，比昨天上升0.8%；鲤鱼13.99元/公斤，比昨天上升0.9%；"
                          "白鲢鱼10.2元/公斤，比昨天上升1.6%；大带鱼42.09元/公斤，比昨天上升0.5%。"),
}


class TestDailyParse(unittest.TestCase):
    def test_values(self):
        v = agri_national.parse_daily_row(DAILY_ROW)
        self.assertEqual(v["fruits"]["均价"], 6.78)
        self.assertEqual(v["vegetables"]["均价"], 4.18)
        self.assertEqual(v["animal"]["猪肉"], 15.76)
        self.assertEqual(v["animal"]["牛肉"], 72.81)
        self.assertEqual(v["animal"]["白条鸡"], 17.02)
        self.assertEqual(v["aquatic"]["鲫鱼"], 19.56)
        self.assertEqual(v["aquatic"]["大带鱼"], 42.09)

    def test_missing_fields_do_not_raise(self):
        v = agri_national.parse_daily_row({"daylyDate": "2026-01-01 00:00:00"})
        self.assertEqual(v["fruits"], {})
        self.assertEqual(v["animal"], {})

    def test_every_daily_item_has_parser(self):
        """DAILY_ITEMS 里每一项都必须能从日报里抽出来，否则就是配置写错了。"""
        v = agri_national.parse_daily_row(DAILY_ROW)
        for display, _cat, field in agri_national.DAILY_ITEMS:
            key = "均价" if field in ("vegetables", "fruits") else display.replace("全国", "")
            self.assertIn(key, v[field], "%s 抽不到" % display)


# ---------------------------------------------------------------- 新发地聚合

XINFADI_ROWS = [
    {"prodCat": "水果", "prodName": "富士", "avgPrice": "3.8", "unitInfo": "斤"},
    {"prodCat": "水果", "prodName": "花牛", "avgPrice": "4.2", "unitInfo": "斤"},
    {"prodCat": "水果", "prodName": "黄元帅", "avgPrice": "4.0", "unitInfo": "斤"},
    {"prodCat": "水果", "prodName": "香蕉干", "avgPrice": "20", "unitInfo": "斤"},
    {"prodCat": "水果", "prodName": "蜜桔", "avgPrice": "2.5", "unitInfo": "斤"},
    {"prodCat": "水果", "prodName": "澳柑", "avgPrice": "9.9", "unitInfo": "箱"},
    {"prodCat": "水果", "prodName": "青州蜜", "avgPrice": "3.0", "unitInfo": "斤"},
    {"prodCat": "蔬菜", "prodName": "大白菜", "avgPrice": "0.38", "unitInfo": "斤"},
]


class TestXinfadiAggregate(unittest.TestCase):
    def test_median_and_unit(self):
        agg, _unm = xinfadi.aggregate(XINFADI_ROWS)
        # 苹果三个品种 3.8/4.2/4.0 斤价 → ×2 = 7.6/8.4/8.0，中位数 8.0
        self.assertEqual(agg["apple"]["price"], 8.0)
        self.assertEqual(agg["apple"]["n"], 3)
        # 橘子只认蜜桔（澳柑按箱卖，口径不同，跳过）
        self.assertEqual(agg["citrus"]["price"], 5.0)
        self.assertEqual(agg["citrus"]["n"], 1)

    def test_no_blacklisted_or_vegetable(self):
        agg, unm = xinfadi.aggregate(XINFADI_ROWS)
        self.assertNotIn("banana", agg)              # 香蕉干不算香蕉
        self.assertNotIn("watermelon", agg)
        self.assertEqual(unm.get("香蕉干"), 1)
        self.assertEqual(unm.get("青州蜜"), 1)
        self.assertNotIn("大白菜", unm)               # 蔬菜根本不进水果统计


# ---------------------------------------------------------------- 城市配置

class TestCity(unittest.TestCase):
    def test_wuhan(self):
        c = load_city("wuhan")
        self.assertEqual(c["id"], "wuhan")
        self.assertEqual(c["name"], "武汉")
        self.assertEqual(c["area_code"], "420100")
        self.assertEqual(c["local_unit_label"], "元/500g")
        self.assertTrue(c["fgj"]["api"])
        self.assertTrue(c["category_map"]["肉禽蛋"])
        self.assertTrue(c["use_national"])

    def test_unknown_city_raises(self):
        with self.assertRaises(ValueError):
            load_city("atlantis")

    def test_required_fields(self):
        from cities.base import make_city
        with self.assertRaises(ValueError):
            make_city(id="x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
