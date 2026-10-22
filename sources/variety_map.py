# -*- coding: utf-8 -*-
"""
新发地「具体规格名 → 品类」映射表
==================================
新发地的 prodName 不是品类，而是「产地+品种+规格」的碎片：
    富士 / 花牛 / 黄元帅 / 嘎啦 / 辽宁寒富苹果   → 苹果
    蜜桔 / 叶桔 / 金秋砂糖桔 / 爱媛              → 橘子
    甜王 / 麒麟 / 黑美人 / 无籽西瓜              → 西瓜
    国产香蕉 / 进口香蕉 / 泰国香蕉               → 香蕉

三条铁律（都是踩过坑总结的）：

1. **只认白名单，不猜。** 没命中 RULES 的名字一律不归类，
   宁可这个品类当日少一条报价，也不把「青州蜜」这种歧义名硬塞进橘子
   （青州蜜在多个市场指青州蜜桃，不是柑橘）。

2. **先过黑名单。** 新发地不少干果/坚果/种子的 prodCat 也是「水果」：
   香蕉干、葡萄干、核桃、瓜子、板栗…… 直接按关键词排除，
   否则「葡萄干 12 元/斤」会被算进葡萄价。

3. **单位统一。** 新发地是元/斤，本项目参考口径是元/公斤，×2。
   单位不确定的（缺 unitInfo 又非斤）跳过，不做猜测换算。
"""

# ---------------------------------------------------------------- 黑名单
# 命中任一即跳过：干果、坚果、种子、加工品、非目标品类。
#
# 注意两个不能加进来的字：
#   「籽」—— 无籽西瓜 会被误杀
#   「糖」—— 金秋砂糖桔 会被误杀
# 所以同类词一律写成完整词（瓜子 / 葵花籽），不用单字。
BLACKLIST = (
    "干", "仁", "瓜子", "葵花籽", "花生", "核桃", "榛", "松子", "腰果",
    "巴旦木", "开心果", "板栗", "栗", "白果", "莲子", "芝麻",
    "汁", "酱", "罐头", "蜜饯", "果脯",
)

# ---------------------------------------------------------------- 归类规则
# 顺序无关（全表扫），但关键词要写得足够具体，避免误吞
RULES = [
    {
        "key": "apple",
        "display": "苹果",
        "category": "水果",
        "keywords": ["苹果", "富士", "花牛", "黄元帅", "嘎啦", "国光", "寒富", "王林",
                     "阿克苏", "青苹果", "蛇果", "秦冠", "乔纳金", "金冠",
                     "元帅", "红星苹果", "蜜脆"],
    },
    {
        "key": "banana",
        "display": "香蕉",
        "category": "水果",
        "keywords": ["香蕉"],
    },
    {
        "key": "watermelon",
        "display": "西瓜",
        "category": "水果",
        "keywords": ["西瓜", "甜王", "麒麟", "黑美人", "特小凤", "蜜童",
                     "京欣", "早春红玉", "冠龙"],
    },
    {
        "key": "citrus",
        "display": "橘子",
        "category": "水果",
        # 只收柑橘属里的「橘/柑」，橙、柚、柠檬另算，不混进来
        "keywords": ["蜜桔", "蜜橘", "叶桔", "砂糖桔", "沙糖桔", "金秋砂糖桔",
                     "爱媛", "沃柑", "椪柑", "芦柑", "丑橘", "不知火",
                     "贡桔", "南丰蜜桔", "温州蜜桔", "桔子", "橘子", "柑橘"],
    },
]

# 品类顺序（决定 data.json 里的排列先后）
ORDER = ["apple", "banana", "watermelon", "citrus"]


def _norm(name):
    """去掉全角/半角括号里的规格补充，避免 (K9)、(纸箱) 干扰匹配。"""
    s = (name or "").strip()
    for l, r in (("（", "）"), ("(", ")")):
        while l in s and r in s[l.index(l):]:
            a = s.index(l)
            b = s.index(r, a)
            s = s[:a] + s[b + 1:]
    return s


def classify(name):
    """
    返回品类 key（apple/banana/watermelon/citrus），未命中返回 None。

    None 是正常返回值，不是错误：调用方据此把该条报价排除，
    并在日志里记下未映射名字，方便以后按需补规则。
    """
    s = _norm(name)
    if not s:
        return None
    for bad in BLACKLIST:
        if bad in s:
            return None
    for rule in RULES:
        for kw in rule["keywords"]:
            if kw in s:
                return rule["key"]
    return None


def display_of(key):
    for rule in RULES:
        if rule["key"] == key:
            return rule["display"]
    return key


def category_of(key):
    for rule in RULES:
        if rule["key"] == key:
            return rule["category"]
    return "水果"
