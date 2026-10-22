# -*- coding: utf-8 -*-
"""
抓取模块
========
local 类（ città 配置决定）：武汉发改委 / 农业农村局 / 商务局 —— 见 fetch_data.py
reference 类（全国口径，各城市通用）：
    agri_national  农业农村部全国周报 + 日报
    xinfadi        北京新发地分品种水果日价

每个 reference 模块都提供 collect(weeks=..., log=...) -> 同构结果：
    {"dates": [...], "latest": "...", "series": {显示名: {category, values, obs}}, "stats": {...}}
values 与 dates 等长，缺数据为 None（绝不插值）。
"""

from sources import agri_national, variety_map, xinfadi

__all__ = ["agri_national", "xinfadi", "variety_map"]
