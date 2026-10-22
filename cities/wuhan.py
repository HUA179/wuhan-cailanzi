# -*- coding: utf-8 -*-
"""
武汉市配置
==========
武汉是本项目的一号城市，也是「湖北」这一层的代表样本：
武汉是湖北省会，我们只声明「湖北·武汉」，不假装手里有全省均价。

三个本地源（全部政府公开数据）：
    ① 武汉市发改委「价格监测平台」每日零售价（主源，支持回溯历史）
    ② 武汉市农业农村局 批发价（补品种）
    ③ 武汉市商务局 生活必需品周报（补肉禽蛋细类）
"""

from cities.base import make_city

CITY = make_city(
    id="wuhan",
    name="武汉",
    province="湖北",
    region="wuhan",
    title="武汉菜篮子",
    subtitle="官方菜价监测",
    area_code="420100",
    local_unit="500g",
    local_unit_label="元/500g",

    fgj={
        "api": "http://58.48.136.167:7600/prod-api",
        "referer": "http://58.48.136.167:7600/comparePrice",
        "source_name": "武汉市发改委",
    },
    nyncj_base="https://nyncj.wuhan.gov.cn",
    sw_base="https://sw.wuhan.gov.cn",

    nyncj_sources=[
        {"column": "/zwgk_25/fdzdgknr/snsj/scpfjg/", "category": "蔬菜",     "take": 2},
        {"column": "/zwgk_25/fdzdgknr/snsj/scppfjg/", "category": "水产",     "take": 1},
        {"column": "/zwgk_25/fdzdgknr/snsj/lypfjg/",  "category": "米面粮油", "take": 1},
    ],
    sw_source={"column": "/zfxxgk/fdzdgknr/sjfb/jgjczb/", "take": 10},

    category_map={
        "米面粮油": ["中籼米", "早籼米", "晚粳米", "特一粉", "食盐"],
        "肉禽蛋": ["猪排骨", "猪精瘦肉", "猪腿夹肉", "白条鸡", "白条鸭",
                   "良种鸡蛋", "鲜牛肉", "鲜羊肉"],
        "水产": ["胖头鱼", "草鱼", "鲫鱼", "鳊鱼"],
        "豆制品": ["豆腐", "千张", "干子"],
    },
    name_alias={
        "良种鸡蛋": "鸡蛋",
        "鲜牛肉": "牛肉",
        "鲜羊肉": "羊肉",
        "胖头鱼": "花鲢（胖头鱼）",
    },
)
