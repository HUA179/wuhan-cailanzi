# -*- coding: utf-8 -*-
"""
城市配置基座
============
把「一个城市怎么抓、怎么命名、怎么归类」全部收进一份 dict，
fetch_data.py 只认这份 dict，不再出现任何写死的城市常量和站点地址。

换城市的正确做法：
    新建 cities/<城市拼音>.py，调用 make_city(...) 声明该城市的站点参数，
    然后 `python fetch_data.py --city=xxx --mode=full`。

注意（诚实声明）：
    这份配置能覆盖的是「同一类数据源换个城市参数」的情况（比如同样用
    价格监测平台的地市）。如果新城市用的是完全不同的政务站点，
    仍然要在 sources/ 下新写一个抓取模块 —— 因为 HTML 结构不一样，
    这不是配置能抽象掉的东西。抽象掉的是命名、单位、归类、开关。
"""

# 前端分类的展示顺序（index.html 的 categories() 用同一套顺序）
CATEGORY_ORDER = ["蔬菜", "水果", "肉禽蛋", "水产", "米面粮油", "豆制品"]

REQUIRED = ("id", "name", "region", "title")


def make_city(**kw):
    """
    构造并校验一份城市配置。

    必填：id / name / region / title
    其余给默认值，避免每个城市都要写全 20 个键。
    """
    city = {
        "id": "",
        "name": "",
        "province": "",
        "region": "local",          # data.json 里的 region 值：wuhan/hubei/national
        "title": "",                # 页面标题，如「武汉菜篮子」
        "subtitle": "官方菜价监测",
        "area_code": "",            # 价格监测平台的行政区划码
        "local_unit": "500g",       # 本地零售口径
        "local_unit_label": "元/500g",

        # 价格监测平台（发改委）接口
        "fgj": {"api": "", "referer": "", "source_name": ""},

        # 农业农村局 / 商务局 政务站
        "nyncj_base": "",
        "sw_base": "",
        "nyncj_sources": [],        # [{"column":..., "category":..., "take":...}]
        "sw_source": None,          # {"column":..., "take":...}

        # 品种 → 分类 / 展示名归一
        "category_map": {},         # {分类: [原始品种名...]}
        "name_alias": {},           # {原始名: 展示名}

        # 参考源开关（全国口径对所有城市都适用，默认开）
        "use_national": True,       # 农业农村部全国周报/日报
        "use_xinfadi": True,        # 北京新发地（分品种水果日价）
        "fruit_weeks": 52,          # 水果历史窗口
    }
    city.update({k: v for k, v in kw.items() if v is not None})

    missing = [k for k in REQUIRED if not city.get(k)]
    if missing:
        raise ValueError("城市配置缺少必填项: %s" % ", ".join(missing))
    if city["category_map"] and not city["local_unit"]:
        raise ValueError("声明了 category_map 却没给 local_unit，单位口径会错")
    return city
