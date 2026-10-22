# -*- coding: utf-8 -*-
"""城市配置注册表：按 id 载入 cities/<id>.py 里的 CITY。"""

import importlib
import os

from cities.base import CATEGORY_ORDER, make_city

DEFAULT_CITY = "wuhan"

_cache = {}


def load_city(city_id=None):
    """
    载入城市配置。city_id 为空时读环境变量 CAILANZI_CITY，再退回默认武汉。
    载入失败直接抛错而不是静默回退 —— 拼错城市名却跑出武汉的数据最危险。
    """
    cid = (city_id or os.environ.get("CAILANZI_CITY") or DEFAULT_CITY).strip().lower()
    if cid in _cache:
        return _cache[cid]
    try:
        mod = importlib.import_module("cities." + cid)
    except ImportError as e:
        raise ValueError("没有这个城市的配置: cities/%s.py（%s）" % (cid, e))
    city = getattr(mod, "CITY", None)
    if not city:
        raise ValueError("cities/%s.py 里没有 CITY 变量" % cid)
    _cache[cid] = city
    return city


def available():
    """列出所有已实现的城市配置。"""
    here = os.path.dirname(os.path.abspath(__file__))
    out = []
    for fn in sorted(os.listdir(here)):
        if fn.endswith(".py") and fn not in ("__init__.py", "base.py"):
            out.append(fn[:-3])
    return out


__all__ = ["load_city", "available", "make_city", "CATEGORY_ORDER", "DEFAULT_CITY"]
