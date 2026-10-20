"""花束平台的核心领域逻辑。

这个模块只放纯 Python 逻辑，不直接依赖 Streamlit，方便单独测试：
花材数据清洗、推荐打分、预算调节、价格计算、生图提示词和结构示意图。
"""
from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CATEGORY_ORDER = ["主花", "配花", "叶材", "果材"]

CATEGORY_META: Dict[str, Dict[str, str]] = {
    "主花": {"emoji": "🌹", "color": "#C75C7A", "hint": "视觉焦点"},
    "配花": {"emoji": "✨", "color": "#8D77A8", "hint": "增加层次"},
    "叶材": {"emoji": "🌿", "color": "#6F9070", "hint": "收住轮廓"},
    "果材": {"emoji": "🍒", "color": "#B56A4A", "hint": "点睛之笔"},
}

SEASON_MONTHS = {
    1: "冬季",
    2: "冬季",
    3: "春季",
    4: "春季",
    5: "春季",
    6: "夏季",
    7: "夏季",
    8: "夏季",
    9: "秋季",
    10: "秋季",
    11: "秋季",
    12: "冬季",
}

TARGETS = ["恋人", "家人", "朋友", "老师", "自己", "客户", "孩子", "伴侣"]
OCCASIONS = [
    "日常惊喜",
    "生日",
    "表白",
    "纪念日",
    "毕业",
    "婚礼",
    "探望",
    "乔迁",
    "开业",
    "道歉",
    "母亲节",
    "情人节",
    "年节",
    "祝福",
]
COLOR_CHOICES = ["任意", "粉色", "红色", "白色", "紫色", "黄色", "橙色", "蓝色", "绿色", "香槟色"]
STYLE_CHOICES = [
    "任意",
    "浪漫",
    "清新自然",
    "简约高级",
    "温柔治愈",
    "阳光活力",
    "复古",
    "可爱",
    "华丽大气",
]
SEASON_CHOICES = ["当季", "不限", "春季", "夏季", "秋季", "冬季"]

COLOR_HEX: Dict[str, str] = {
    "红": "#D9535F",
    "玫红": "#D95C7A",
    "粉": "#F2A7BC",
    "白": "#FFF9F0",
    "黄": "#F2C94C",
    "金": "#D9AE55",
    "紫": "#9A7CCB",
    "蓝": "#6F93D2",
    "绿": "#78A984",
    "橙": "#EE8A4D",
    "香槟": "#E6CDA4",
    "褐": "#8C6A4A",
    "棕": "#8C6A4A",
    "灰": "#A7B3A3",
    "米白": "#F5EBDD",
    "多色": "#D98BA8",
}

COLOR_EN: Dict[str, str] = {
    "红": "red",
    "玫红": "raspberry-pink",
    "粉": "pink",
    "白": "white",
    "黄": "yellow",
    "金": "golden",
    "紫": "purple",
    "蓝": "blue",
    "绿": "green",
    "橙": "orange",
    "香槟": "champagne",
    "褐": "brown",
    "棕": "brown",
    "灰": "grey-green",
    "米白": "cream",
    "多色": "mixed-color",
}

STYLE_SYNONYMS = {
    "浪漫": ["浪漫", "甜美", "温柔", "梦幻"],
    "清新自然": ["清新", "自然", "田园", "森系"],
    "简约高级": ["简约", "高级", "优雅", "质感"],
    "温柔治愈": ["温柔", "治愈", "温暖", "柔软"],
    "阳光活力": ["阳光", "活力", "明亮", "元气"],
    "复古": ["复古", "秋色", "油画", "焦糖"],
    "可爱": ["可爱", "童趣", "小巧", "活泼"],
    "华丽大气": ["华丽", "大气", "饱满", "隆重"],
}

SIZE_CONFIG: Dict[str, Dict[str, Any]] = {
    "S": {
        "label": "S · 小巧",
        "dims": "10–15cm",
        "main_types": 2,
        "filler_types": 2,
        "foliage_types": 1,
        "fruit_types": 0,
        "main_qty": 3,
        "filler_qty": 2,
        "foliage_qty": 2,
        "fruit_qty": 1,
        "pack_base": 10,
        "labor": 30,
        "max_qty": 12,
    },
    "M": {
        "label": "M · 标准",
        "dims": "20–25cm",
        "main_types": 3,
        "filler_types": 2,
        "foliage_types": 1,
        "fruit_types": 1,
        "main_qty": 5,
        "filler_qty": 3,
        "foliage_qty": 3,
        "fruit_qty": 2,
        "pack_base": 18,
        "labor": 45,
        "max_qty": 18,
    },
    "L": {
        "label": "L · 大气",
        "dims": "30–35cm",
        "main_types": 3,
        "filler_types": 3,
        "foliage_types": 2,
        "fruit_types": 1,
        "main_qty": 8,
        "filler_qty": 4,
        "foliage_qty": 4,
        "fruit_qty": 2,
        "pack_base": 28,
        "labor": 65,
        "max_qty": 24,
    },
    "XL": {
        "label": "XL · 豪华",
        "dims": "40cm+",
        "main_types": 4,
        "filler_types": 3,
        "foliage_types": 2,
        "fruit_types": 2,
        "main_qty": 12,
        "filler_qty": 5,
        "foliage_qty": 5,
        "fruit_qty": 3,
        "pack_base": 40,
        "labor": 90,
        "max_qty": 30,
    },
}

PACKAGING_OPTIONS: Dict[str, Dict[str, Any]] = {
    "misty": {
        "label": "韩式雾面纸",
        "icon": "🎀",
        "premium": 12,
        "paper": ("#F6E6E9", "#E7D4DE"),
        "prompt": "matte Korean misty paper in soft ivory and blush",
        "note": "柔和哑光，最百搭",
    },
    "kraft": {
        "label": "自然牛皮纸",
        "icon": "📦",
        "premium": 4,
        "paper": ("#DCC19A", "#C49B67"),
        "prompt": "natural kraft paper with a clean folded edge",
        "note": "松弛自然，适合森系",
    },
    "organza": {
        "label": "欧根纱",
        "icon": "🫧",
        "premium": 16,
        "paper": ("#F6E9F2", "#E7D2E4"),
        "prompt": "translucent layered organza fabric",
        "note": "轻盈通透，拍照好看",
    },
    "newspaper": {
        "label": "复古报纸",
        "icon": "📰",
        "premium": 8,
        "paper": ("#EAE1D2", "#D6C7B2"),
        "prompt": "vintage newspaper-print wrapping paper",
        "note": "复古文艺，适合秋日",
    },
    "giftbox": {
        "label": "哑光礼盒",
        "icon": "🎁",
        "premium": 22,
        "paper": ("#E9DDEB", "#D6C4D8"),
        "prompt": "matte rigid gift box with a satin ribbon",
        "note": "仪式感强，适合送礼",
    },
    "bare": {
        "label": "无包装 · 环保",
        "icon": "🌿",
        "premium": 0,
        "paper": ("#F3EEE5", "#E5DCCD"),
        "prompt": "exposed natural stems tied with a simple ribbon",
        "note": "保留自然茎秆",
    },
}

SHAPE_OPTIONS: Dict[str, Dict[str, Any]] = {
    "round": {
        "label": "圆形手捧",
        "icon": "⚪",
        "premium": 0,
        "prompt": "round hand-tied bouquet with a domed silhouette",
        "note": "经典饱满，四面可看",
    },
    "fan": {
        "label": "扇形展开",
        "icon": "🪭",
        "premium": 6,
        "prompt": "fan-shaped open bouquet with an airy silhouette",
        "note": "舒展大气，适合开业/毕业",
    },
    "one_sided": {
        "label": "韩式单面",
        "icon": "🌙",
        "premium": 8,
        "prompt": "Korean-style one-sided bouquet with layered wrapping",
        "note": "层次感强，适合拍照",
    },
    "box": {
        "label": "方形花盒",
        "icon": "⬜",
        "premium": 18,
        "prompt": "compact square hat-box arrangement",
        "note": "稳定耐放，适合桌面",
    },
    "basket": {
        "label": "手提花篮",
        "icon": "🧺",
        "premium": 20,
        "prompt": "flower basket with a curved handle",
        "note": "适合乔迁/开业/探望",
    },
    "cascade": {
        "label": "瀑布式",
        "icon": "💧",
        "premium": 12,
        "prompt": "cascading waterfall bouquet with a flowing silhouette",
        "note": "隆重，适合婚礼/纪念日",
    },
}

RIBBON_OPTIONS: Dict[str, Dict[str, str]] = {
    "champagne": {"label": "香槟金", "hex": "#C9A86A", "prompt": "champagne-gold satin ribbon"},
    "rose": {"label": "豆沙粉", "hex": "#C9879A", "prompt": "dusty-rose satin ribbon"},
    "ivory": {"label": "奶油白", "hex": "#F1E7D8", "prompt": "ivory satin ribbon"},
    "blue": {"label": "雾霾蓝", "hex": "#7E97AE", "prompt": "dusty-blue satin ribbon"},
    "wine": {"label": "酒红", "hex": "#8E3E4C", "prompt": "burgundy satin ribbon"},
}

COLORFUL_PALETTES = [
    "#D9535F",
    "#F2A7BC",
    "#F2C94C",
    "#9A7CCB",
    "#6F93D2",
    "#EE8A4D",
]

CN_TZ = timezone(timedelta(hours=8))

EMOJI_RULES = [
    ("泡泡玫瑰", "🌹"),
    ("玫瑰", "🌹"),
    ("水仙百合", "🌺"),
    ("百合", "🌷"),
    ("康乃馨", "🌸"),
    ("绣球", "💠"),
    ("向日葵", "🌻"),
    ("郁金香", "🌷"),
    ("满天星", "✨"),
    ("勿忘我", "💜"),
    ("茉莉", "🤍"),
    ("栀子", "🤍"),
    ("荷花", "🪷"),
    ("睡莲", "🪷"),
    ("莲蓬", "🪷"),
    ("梅花", "🌺"),
    ("腊梅", "💛"),
    ("桃花", "🌸"),
    ("樱花", "🌸"),
    ("芍药", "🌸"),
    ("牡丹", "🌸"),
    ("洋牡丹", "🌸"),
    ("大丽花", "🌺"),
    ("银莲花", "🌼"),
    ("香雪兰", "🌼"),
    ("丁香", "💜"),
    ("紫罗兰", "💜"),
    ("风铃", "🔔"),
    ("飞燕", "💙"),
    ("百子莲", "💙"),
    ("蓝星", "💙"),
    ("蝴蝶兰", "🦋"),
    ("跳舞兰", "💛"),
    ("石斛", "🌺"),
    ("蕙兰", "🌺"),
    ("天堂鸟", "🦜"),
    ("红掌", "❤️"),
    ("马蹄莲", "🤍"),
    ("天鹅绒", "🤍"),
    ("晚香玉", "🤍"),
    ("姜花", "🤍"),
    ("金鱼草", "🐟"),
    ("扶郎", "🌼"),
    ("乒乓菊", "⚪"),
    ("牡丹菊", "🌺"),
    ("大花蕙兰", "🌺"),
    ("洋甘菊", "🌼"),
    ("雏菊", "🌼"),
    ("翠菊", "💜"),
    ("波斯菊", "🌸"),
    ("黑心菊", "🌼"),
    ("麦秆菊", "🌼"),
    ("黄金球", "🟡"),
    ("澳洲米花", "🌾"),
    ("澳洲腊梅", "💛"),
    ("雪柳", "🤍"),
    ("小手球", "🤍"),
    ("蕾丝", "🤍"),
    ("翠珠", "💠"),
    ("松虫", "💜"),
    ("鼠尾草", "💜"),
    ("情人草", "💜"),
    ("水晶草", "✨"),
    ("相思梅", "💗"),
    ("红豆", "🍒"),
    ("冬青", "🍒"),
    ("火棘", "🍒"),
    ("灯笼果", "🏮"),
    ("蔷薇果", "🍒"),
    ("棉花", "☁️"),
    ("尤加利", "🌿"),
    ("龟背", "🍃"),
    ("散尾", "🌴"),
    ("南天竹", "🍃"),
    ("蓬莱松", "🌿"),
    ("排草", "🌿"),
    ("鸟巢蕨", "🌿"),
    ("羊齿", "🌿"),
    ("剑叶", "🌿"),
    ("龙柳", "🌿"),
    ("红瑞木", "🌿"),
    ("蒲棒", "🌾"),
    ("芦苇", "🌾"),
]


def flower_emoji(flower_or_name: Any, category: Optional[str] = None) -> str:
    if isinstance(flower_or_name, dict):
        name = str(flower_or_name.get("name", ""))
        category = str(flower_or_name.get("category", category or "配花"))
    else:
        name = str(flower_or_name or "")
    for keyword, emoji in EMOJI_RULES:
        if keyword in name:
            return emoji
    return CATEGORY_META.get(category or "配花", {}).get("emoji", "💐")


def current_season(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(CN_TZ)
    return SEASON_MONTHS.get(now.month, "全年")


def normalize_season_tags(season_text: str) -> List[str]:
    text = str(season_text or "")
    if "全年" in text:
        tags = ["全年"]
        for season in ["春季", "夏季", "秋季", "冬季"]:
            if season in text:
                tags.append(season)
        return tags
    if "春夏" in text:
        return ["春季", "夏季"]
    if "夏秋" in text:
        return ["夏季", "秋季"]
    if "秋冬" in text:
        return ["秋季", "冬季"]
    if "冬春" in text or "春冬" in text:
        return ["冬季", "春季"]
    tags = [season for season in ["春季", "夏季", "秋季", "冬季"] if season in text]
    return tags or ["全年"]


def color_roots(color_text: str) -> List[str]:
    text = str(color_text or "")
    ordered = [
        "香槟",
        "玫红",
        "米白",
        "多色",
        "红",
        "粉",
        "白",
        "黄",
        "金",
        "紫",
        "蓝",
        "绿",
        "橙",
        "褐",
        "棕",
        "灰",
    ]
    found: List[str] = []
    for root in ordered:
        if root in text and root not in found:
            found.append(root)
    return found or ["多色"]


def palette_from_color(color_text: str) -> List[str]:
    roots = color_roots(color_text)
    palette: List[str] = []
    for root in roots:
        hex_color = COLOR_HEX.get(root)
        if hex_color and hex_color not in palette:
            palette.append(hex_color)
    if len(palette) == 1:
        palette.append("#E9C7D1")
    if not palette:
        palette = COLORFUL_PALETTES[:3]
    return palette


def infer_category(name: str) -> str:
    """旧版知识库没有 category 字段时的兜底分类。"""
    text = str(name or "")
    leaf_keywords = [
        "叶",
        "蕨",
        "松",
        "柳",
        "竹",
        "南天竹",
        "红瑞木",
        "排草",
        "鸟巢",
        "羊齿",
        "散尾",
        "龟背",
        "蓬莱",
        "尤加利",
    ]
    fruit_keywords = ["红豆", "冬青", "火棘", "灯笼果", "蔷薇果", "棉花"]
    filler_keywords = [
        "满天星",
        "勿忘我",
        "情人草",
        "水晶草",
        "翠珠",
        "蓝星",
        "松虫",
        "蕾丝",
        "相思梅",
        "翠菊",
        "波斯菊",
        "黑心菊",
        "麦秆菊",
        "黄金球",
        "澳洲米花",
        "澳洲腊梅",
        "小手球",
        "雪柳花",
        "洋甘菊",
        "小雏菊",
        "蒲棒",
        "芦苇",
    ]
    if any(keyword in text for keyword in fruit_keywords):
        return "果材"
    if any(keyword in text for keyword in filler_keywords):
        return "配花"
    if any(keyword in text for keyword in leaf_keywords):
        return "叶材"
    return "主花"


def enrich_flower(flower: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(flower)
    if item.get("category") not in CATEGORY_ORDER:
        item["category"] = infer_category(str(item.get("name", "")))
    item.setdefault("english_name", item.get("name", "flower"))
    item.setdefault("season_tags", normalize_season_tags(item.get("season", "全年")))
    item.setdefault("palette", palette_from_color(item.get("color", "")))
    item.setdefault("fragrant", False)
    item.setdefault("unit_price", 5)
    item["id"] = int(item["id"])
    item["unit_price"] = float(item["unit_price"])
    return item


def load_flowers(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return [enrich_flower(item) for item in data]


def qty_for(quantities: Dict[Any, Any], flower_id: int) -> int:
    if flower_id in quantities:
        return int(quantities[flower_id] or 0)
    return int(quantities.get(str(flower_id), 0) or 0)


def default_quantity(flower: Dict[str, Any], size_key: str) -> int:
    config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
    category = flower.get("category", "配花")
    if category == "主花":
        return int(config["main_qty"])
    if category == "配花":
        return int(config["filler_qty"])
    if category == "叶材":
        return int(config["foliage_qty"])
    return int(config["fruit_qty"]) or 1


def max_quantity(flower: Dict[str, Any], size_key: str) -> int:
    config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
    category = flower.get("category", "配花")
    if category == "叶材":
        return min(14, max(6, int(config["max_qty"]) // 2))
    if category == "果材":
        return min(12, max(5, int(config["max_qty"]) // 2))
    return int(config["max_qty"])


def _wrap_qty(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def price_breakdown(
    selected: Sequence[Dict[str, Any]],
    quantities: Dict[Any, Any],
    size_key: str,
    packaging_key: str = "misty",
    shape_key: str = "round",
    delivery_threshold: int = 199,
    delivery_fee: int = 15,
) -> Dict[str, Any]:
    config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
    packaging = PACKAGING_OPTIONS.get(packaging_key, PACKAGING_OPTIONS["misty"])
    shape = SHAPE_OPTIONS.get(shape_key, SHAPE_OPTIONS["round"])
    detail: List[Dict[str, Any]] = []
    flower_cost = 0.0
    for flower in selected:
        quantity = max(0, qty_for(quantities, int(flower["id"])))
        unit_price = float(flower.get("unit_price", 5))
        subtotal = quantity * unit_price
        flower_cost += subtotal
        detail.append(
            {
                "id": int(flower["id"]),
                "name": flower.get("name", ""),
                "english_name": flower.get("english_name", ""),
                "category": flower.get("category", "配花"),
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
            }
        )
    packaging_cost = float(config["pack_base"]) + float(packaging["premium"]) + float(shape["premium"])
    labor_cost = float(config["labor"]) + (10.0 if shape_key in {"cascade", "basket"} else 0.0)
    before_delivery = flower_cost + packaging_cost + labor_cost
    actual_delivery = 0.0 if before_delivery >= delivery_threshold else float(delivery_fee)
    total = before_delivery + actual_delivery
    return {
        "flower_cost": flower_cost,
        "packaging_cost": packaging_cost,
        "labor_cost": labor_cost,
        "delivery_fee": actual_delivery,
        "delivery_threshold": delivery_threshold,
        "subtotal_before_delivery": before_delivery,
        "total_price": total,
        "flower_detail": detail,
        "packaging_label": packaging["label"],
        "shape_label": shape["label"],
    }


def tune_quantities_to_budget(
    selected: Sequence[Dict[str, Any]],
    quantities: Dict[Any, Any],
    size_key: str,
    packaging_key: str,
    shape_key: str,
    budget: float,
) -> Dict[int, int]:
    tuned = {int(flower["id"]): max(1, qty_for(quantities, int(flower["id"]))) for flower in selected}
    if not tuned:
        return tuned

    def total() -> float:
        return price_breakdown(selected, tuned, size_key, packaging_key, shape_key)["total_price"]

    # 先压到预算内：从最贵的一支开始减，保留每种花至少 1 支。
    for _ in range(500):
        if total() <= budget:
            break
        candidates = [
            (int(flower["id"]), tuned[int(flower["id"])] * float(flower.get("unit_price", 5)))
            for flower in selected
            if tuned.get(int(flower["id"]), 0) > 1
        ]
        if not candidates:
            break
        flower_id = max(candidates, key=lambda pair: pair[1])[0]
        tuned[flower_id] -= 1

    # 再把预算用起来，避免推荐结果总是贴着最低支数。
    target_floor = budget * 0.64
    increase_cursor = 0
    for _ in range(400):
        if total() >= target_floor:
            break
        added = False
        for offset in range(len(selected)):
            index = (increase_cursor + offset) % len(selected)
            flower = selected[index]
            flower_id = int(flower["id"])
            if tuned[flower_id] >= max_quantity(flower, size_key):
                continue
            tuned[flower_id] += 1
            if total() > budget:
                tuned[flower_id] -= 1
                continue
            increase_cursor = (index + 1) % len(selected)
            added = True
            break
        if not added:
            break
    return tuned


def size_for_budget(budget: float) -> str:
    if budget < 170:
        return "S"
    if budget < 330:
        return "M"
    if budget < 560:
        return "L"
    return "XL"


def _style_score(flower_style: str, wanted_style: str) -> float:
    if not wanted_style or wanted_style == "任意":
        return 0.0
    flower_style = str(flower_style or "")
    synonyms = STYLE_SYNONYMS.get(wanted_style, [wanted_style])
    if any(word and word in flower_style for word in synonyms):
        return 3.4
    if wanted_style and wanted_style in flower_style:
        return 3.0
    return 0.0


def _color_score(flower_color: str, wanted_color: str) -> float:
    if not wanted_color or wanted_color == "任意":
        return 0.0
    if wanted_color in str(flower_color):
        return 5.0
    if wanted_color == "红色" and "玫红" in str(flower_color):
        return 3.0
    return 0.0


def _jitter(flower_id: int, seed: int) -> float:
    digest = hashlib.md5(f"{flower_id}:{seed}".encode("utf-8")).hexdigest()
    return int(digest[:6], 16) / 0xFFFFFF * 0.9


def score_flower(
    flower: Dict[str, Any],
    prefs: Dict[str, Any],
    season: str,
    seed: int = 0,
) -> float:
    score = 0.0
    target = str(prefs.get("target", ""))
    occasion = str(prefs.get("occasion", ""))
    color = str(prefs.get("color", "任意"))
    style = str(prefs.get("style", "任意"))
    if target and target in [str(value) for value in flower.get("target", [])]:
        score += 6.0
    if occasion and occasion in [str(value) for value in flower.get("occasion", [])]:
        score += 6.0
    score += _color_score(str(flower.get("color", "")), color)
    score += _style_score(str(flower.get("style", "")), style)
    season_tags = flower.get("season_tags", [])
    if season in season_tags or "全年" in season_tags:
        score += 1.8
    if float(flower.get("unit_price", 5)) <= 8:
        score += 0.5
    score += _jitter(int(flower["id"]), seed)
    return score


def _pick_category(
    flowers: Sequence[Dict[str, Any]],
    category: str,
    count: int,
    prefs: Dict[str, Any],
    season: str,
    seed: int,
    used_ids: set,
) -> List[Dict[str, Any]]:
    if count <= 0:
        return []
    pool = [flower for flower in flowers if flower.get("category") == category and int(flower["id"]) not in used_ids]
    wanted_color = str(prefs.get("color", "任意"))
    if wanted_color not in {"", "任意"}:
        color_pool = [flower for flower in pool if wanted_color in str(flower.get("color", ""))]
        if len(color_pool) >= count:
            pool = color_pool
    if season:
        seasonal_pool = [
            flower
            for flower in pool
            if season in flower.get("season_tags", []) or "全年" in flower.get("season_tags", [])
        ]
        if len(seasonal_pool) >= count:
            pool = seasonal_pool
    pool.sort(key=lambda flower: score_flower(flower, prefs, season, seed), reverse=True)
    picked: List[Dict[str, Any]] = []
    for flower in pool[:count]:
        picked.append(flower)
        used_ids.add(int(flower["id"]))
    return picked


def recommendation_reasons(
    flower: Dict[str, Any],
    prefs: Dict[str, Any],
    season: str,
) -> List[str]:
    reasons: List[str] = []
    target = str(prefs.get("target", ""))
    occasion = str(prefs.get("occasion", ""))
    color = str(prefs.get("color", "任意"))
    if target and target in [str(value) for value in flower.get("target", [])]:
        reasons.append(f"适合送{target}")
    if occasion and occasion in [str(value) for value in flower.get("occasion", [])]:
        reasons.append(f"契合{occasion}")
    if color not in {"", "任意"} and color.replace("色", "") in str(flower.get("color", "")):
        reasons.append(f"{color}调")
    if season in flower.get("season_tags", []) or "全年" in flower.get("season_tags", []):
        reasons.append("当季好养")
    if not reasons:
        reasons.append(f"{flower.get('style', '百搭')}气质")
    return reasons[:2]


def _fallback_rationale(
    main: Sequence[Dict[str, Any]],
    filler: Sequence[Dict[str, Any]],
    foliage: Sequence[Dict[str, Any]],
    fruit: Sequence[Dict[str, Any]],
    prefs: Dict[str, Any],
) -> str:
    main_names = "、".join(flower["name"] for flower in main[:3]) or "主花"
    filler_names = "、".join(flower["name"] for flower in filler[:2])
    foliage_names = "、".join(flower["name"] for flower in foliage[:2])
    fruit_names = "、".join(flower["name"] for flower in fruit[:2])
    style = str(prefs.get("style", "自然"))
    if style == "任意":
        style = "自然"
    target = str(prefs.get("target", "TA"))
    occasion = str(prefs.get("occasion", "这份心意"))
    parts = [f"以{main_names}撑起视觉焦点"]
    if filler_names:
        parts.append(f"用{filler_names}增加轻盈层次")
    if foliage_names:
        parts.append(f"再以{foliage_names}收住轮廓")
    if fruit_names:
        parts.append(f"点缀{fruit_names}，让画面更有记忆点")
    return (
        "，".join(parts)
        + f"。整体走{style}路线，适合{occasion}送给{target}；颜色与花型都尽量保持统一，不会喧宾夺主。"
    )


def compose_recommendation(
    main: Sequence[Dict[str, Any]],
    filler: Sequence[Dict[str, Any]],
    foliage: Sequence[Dict[str, Any]],
    fruit: Sequence[Dict[str, Any]],
    prefs: Dict[str, Any],
    size_key: str,
    budget: float,
    packaging_key: str = "misty",
    shape_key: str = "round",
    title: Optional[str] = None,
    rationale: Optional[str] = None,
    source: str = "local",
    seed: int = 0,
) -> Dict[str, Any]:
    selected: List[Dict[str, Any]] = []
    seen: set = set()
    for group in (main, filler, foliage, fruit):
        for flower in group:
            flower_id = int(flower["id"])
            if flower_id not in seen:
                seen.add(flower_id)
                selected.append(flower)
    quantities = {int(flower["id"]): default_quantity(flower, size_key) for flower in selected}
    tuned = tune_quantities_to_budget(
        selected,
        quantities,
        size_key,
        packaging_key,
        shape_key,
        budget,
    )
    if not title:
        color = str(prefs.get("color", "自然"))
        if color == "任意":
            color = "自然"
        title = f"{color}系 · {prefs.get('occasion', '专属')}花束"
    if not rationale:
        rationale = _fallback_rationale(main, filler, foliage, fruit, prefs)
    return {
        "success": True,
        "title": title,
        "rationale": rationale,
        "main": list(main),
        "filler": list(filler),
        "foliage": list(foliage),
        "fruit": list(fruit),
        "selected": selected,
        "quantities": tuned,
        "prefs": dict(prefs),
        "size": size_key,
        "budget": budget,
        "source": source,
        "seed": seed,
    }


def recommend_local(
    flowers: Sequence[Dict[str, Any]],
    prefs: Dict[str, Any],
    size_key: str,
    budget: float,
    packaging_key: str = "misty",
    shape_key: str = "round",
    seed: int = 0,
) -> Dict[str, Any]:
    config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
    main_types = int(config["main_types"])
    filler_types = int(config["filler_types"])
    foliage_types = int(config["foliage_types"])
    fruit_types = int(config["fruit_types"])

    if budget < 120:
        main_types, filler_types, foliage_types, fruit_types = 1, 1, 0, 0
    elif budget < 190:
        main_types, filler_types, foliage_types, fruit_types = min(2, main_types), 1, 1, 0

    season_pref = str(prefs.get("season", "当季"))
    if season_pref in {"", "当季"}:
        season = current_season()
    elif season_pref == "不限":
        season = ""
    else:
        season = season_pref

    used_ids: set = set()
    main = _pick_category(flowers, "主花", main_types, prefs, season, seed, used_ids)
    filler = _pick_category(flowers, "配花", filler_types, prefs, season, seed + 3, used_ids)
    foliage = _pick_category(flowers, "叶材", foliage_types, prefs, season, seed + 7, used_ids)
    fruit = _pick_category(flowers, "果材", fruit_types, prefs, season, seed + 11, used_ids)
    if not foliage and foliage_types > 0:
        foliage = _pick_category(flowers, "叶材", 1, {}, season, seed + 13, used_ids)
    if not main:
        main = _pick_category(flowers, "主花", 1, {}, season, seed, used_ids)
    return compose_recommendation(
        main,
        filler,
        foliage,
        fruit,
        prefs,
        size_key,
        budget,
        packaging_key,
        shape_key,
        source="local",
        seed=seed,
    )


def shortlist_for_llm(
    flowers: Sequence[Dict[str, Any]],
    prefs: Dict[str, Any],
    season: str,
    limit_per_category: int = 10,
) -> List[Dict[str, Any]]:
    shortlist: List[Dict[str, Any]] = []
    for category in CATEGORY_ORDER:
        pool = [flower for flower in flowers if flower.get("category") == category]
        pool.sort(
            key=lambda flower: (
                0
                if (not season or season in flower.get("season_tags", []) or "全年" in flower.get("season_tags", []))
                else 1,
                -score_flower(flower, prefs, season, 0),
            )
        )
        shortlist.extend(pool[:limit_per_category])
    return shortlist


def fill_from_local(
    result_groups: Dict[str, List[Dict[str, Any]]],
    local_result: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    mapping = {
        "main": ("main", "主花"),
        "filler": ("filler", "配花"),
        "foliage": ("foliage", "叶材"),
        "fruit": ("fruit", "果材"),
    }
    for key, (local_key, _) in mapping.items():
        group = list(result_groups.get(key, []))
        seen = {int(flower["id"]) for group_values in result_groups.values() for flower in group_values}
        for candidate in local_result.get(local_key, []):
            if int(candidate["id"]) in seen:
                continue
            if len(group) < len(local_result.get(local_key, [])):
                group.append(candidate)
        result_groups[key] = group
    return result_groups


def color_en_for(flower: Dict[str, Any], preferred_color: str = "任意") -> str:
    roots = color_roots(str(flower.get("color", "")))
    preferred_root = str(preferred_color or "").replace("色", "")
    if preferred_root and preferred_root != "任意":
        for root in roots:
            if root == preferred_root or preferred_root in root:
                return COLOR_EN.get(root, "mixed-color")
    return COLOR_EN.get(roots[0], "mixed-color") if roots else "mixed-color"


def build_image_prompt(
    selected: Sequence[Dict[str, Any]],
    quantities: Dict[Any, Any],
    size_key: str,
    shape_key: str,
    packaging_key: str,
    ribbon_key: str,
    color_preference: str = "任意",
) -> str:
    config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
    shape = SHAPE_OPTIONS.get(shape_key, SHAPE_OPTIONS["round"])
    packaging = PACKAGING_OPTIONS.get(packaging_key, PACKAGING_OPTIONS["misty"])
    ribbon = RIBBON_OPTIONS.get(ribbon_key, RIBBON_OPTIONS["champagne"])
    manifest: List[str] = []
    palette: List[str] = []
    for flower in selected:
        quantity = max(1, qty_for(quantities, int(flower["id"])))
        color_en = color_en_for(flower, color_preference)
        english_name = str(flower.get("english_name") or flower.get("name") or "flower")
        manifest.append(f"{quantity} stems of {color_en} {english_name}")
        for color in palette_from_color(str(flower.get("color", ""))):
            if color not in palette:
                palette.append(color)
    recipe = "; ".join(manifest)
    palette_text = ", ".join(palette[:5])
    return (
        f"Professional floral studio photograph of a {size_key}-size bouquet ({config['dims']}) "
        f"{shape['prompt']}. Exact flower recipe: {recipe}. "
        f"Wrapping: {packaging['prompt']}; ribbon: {ribbon['prompt']}. "
        f"Overall color palette: {palette_text}. "
        "Only the listed flower varieties, colors and stem counts; no extra flower species, "
        "no substitutions, no duplicated blooms. Keep the bouquet balanced and natural, with stems visible at the handle. "
        "Soft diffused daylight, warm cream background, editorial florist photography, 50mm lens, "
        "shallow depth of field, realistic petal textures, high detail, clean composition. "
        "No text, no watermark, no logo, no people, no hands, no vase."
    )


def build_negative_prompt() -> str:
    return (
        "extra flowers, wrong flower species, substituted flowers, duplicated blooms, "
        "missing flowers, text, watermark, logo, people, hands, vase, plastic look, "
        "wilted petals, overcrowded, blurry, low quality"
    )


def _nice_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _svg_leaf(x: float, y: float, angle: float, color: str, scale: float = 1.0) -> str:
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) rotate({angle:.1f})">'
        f'<ellipse rx="{10 * scale:.1f}" ry="{4.8 * scale:.1f}" cx="0" cy="0" '
        f'fill="{color}" opacity="0.92"/>'
        f'<line x1="{-8 * scale:.1f}" y1="0" x2="{8 * scale:.1f}" y2="0" '
        f'stroke="#4E6E52" stroke-width="0.7" opacity="0.45"/>'
        "</g>"
    )


def _svg_bloom(
    x: float,
    y: float,
    color: str,
    angle: float = 0.0,
    scale: float = 1.0,
    kind: str = "main",
    glyph: str = "daisy",
) -> str:
    if kind == "fruit":
        return (
            f'<g transform="translate({x:.1f},{y:.1f})">'
            f'<circle r="{5.4 * scale:.1f}" fill="{color}"/>'
            f'<circle r="{1.8 * scale:.1f}" cx="{-1.6 * scale:.1f}" cy="{-1.8 * scale:.1f}" '
            f'fill="#FFFFFF" opacity="0.38"/>'
            "</g>"
        )

    if kind == "filler":
        if glyph == "spike":
            dots = []
            for index in range(5):
                dy = (-5 + index * 2.5) * scale
                dx = (2 if index % 2 else -2) * scale
                dots.append(
                    f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="{1.8 * scale:.1f}" '
                    f'fill="{color}" opacity="0.95"/>'
                )
            return f'<g transform="translate({x:.1f},{y:.1f})">' + "".join(dots) + "</g>"
        dots = []
        for dx, dy in [(0, 0), (-4, -3), (4, -3), (-5, 3), (5, 3), (0, -6), (0, 6)]:
            dots.append(
                f'<circle cx="{dx * scale:.1f}" cy="{dy * scale:.1f}" '
                f'r="{2.0 * scale:.1f}" fill="{color}" opacity="0.94"/>'
            )
        return (
            f'<g transform="translate({x:.1f},{y:.1f})">'
            + "".join(dots)
            + f'<circle r="{1.0 * scale:.1f}" fill="#FFF7E8" opacity="0.9"/>'
            + "</g>"
        )

    transform = f'translate({x:.1f},{y:.1f}) rotate({angle:.1f})'
    if glyph == "rose":
        petals = []
        for count, radius, opacity, rx, ry in [
            (8, 9.4, 0.62, 3.6, 5.6),
            (6, 6.2, 0.82, 3.2, 5.0),
            (4, 3.3, 0.96, 2.8, 4.4),
        ]:
            for index in range(count):
                petals.append(
                    f'<ellipse rx="{rx * scale:.1f}" ry="{ry * scale:.1f}" '
                    f'transform="rotate({index * 360.0 / count:.1f}) translate(0,{-radius * scale:.1f})" '
                    f'fill="{color}" opacity="{opacity}"/>'
                )
        return (
            f'<g transform="{transform}">'
            + "".join(petals)
            + f'<circle r="{3.6 * scale:.1f}" fill="#F8D98B"/>'
            + f'<circle r="{1.6 * scale:.1f}" fill="#B98345" opacity="0.72"/>'
            + "</g>"
        )
    if glyph == "cup":
        return (
            f'<g transform="{transform}">'
            f'<path d="M {-7 * scale:.1f} {8 * scale:.1f} '
            f'C {-9 * scale:.1f} {-2 * scale:.1f} {-5 * scale:.1f} {-11 * scale:.1f} 0 {-13 * scale:.1f} '
            f'C {5 * scale:.1f} {-11 * scale:.1f} {9 * scale:.1f} {-2 * scale:.1f} {7 * scale:.1f} {8 * scale:.1f} '
            f'C {4 * scale:.1f} {13 * scale:.1f} {-4 * scale:.1f} {13 * scale:.1f} {-7 * scale:.1f} {8 * scale:.1f} Z" '
            f'fill="{color}"/>'
            f'<path d="M 0 {7 * scale:.1f} C {-3 * scale:.1f} {2 * scale:.1f} {-3 * scale:.1f} {-4 * scale:.1f} 0 {-8 * scale:.1f} '
            f'C {3 * scale:.1f} {-4 * scale:.1f} {3 * scale:.1f} {2 * scale:.1f} 0 {7 * scale:.1f} Z" '
            f'fill="#FFF8EC" opacity="0.78"/>'
            f'<circle r="{1.7 * scale:.1f}" fill="#E8B84A"/>'
            + "</g>"
        )
    if glyph == "spike":
        dots = []
        for index in range(6):
            dy = (-12 + index * 4.4) * scale
            dx = (2.3 if index % 2 else -2.3) * scale
            dots.append(
                f'<ellipse cx="{dx:.1f}" cy="{dy:.1f}" rx="{2.3 * scale:.1f}" ry="{3.4 * scale:.1f}" '
                f'fill="{color}" opacity="0.95"/>'
            )
        return (
            f'<g transform="{transform}">'
            f'<line x1="0" y1="{14 * scale:.1f}" x2="0" y2="{-15 * scale:.1f}" '
            f'stroke="#6F9070" stroke-width="{1.2 * scale:.1f}"/>'
            + "".join(dots)
            + "</g>"
        )
    if glyph == "cluster":
        dots = []
        for dx, dy, radius in [
            (0, 0, 3.0),
            (-4, -3, 2.7),
            (4, -3, 2.7),
            (-5, 3, 2.5),
            (5, 3, 2.5),
            (0, -6, 2.5),
            (0, 6, 2.5),
            (-2, -7, 2.0),
            (3, 6, 2.0),
        ]:
            dots.append(
                f'<circle cx="{dx * scale:.1f}" cy="{dy * scale:.1f}" '
                f'r="{radius * scale:.1f}" fill="{color}" opacity="0.94"/>'
            )
        return (
            f'<g transform="{transform}">'
            + "".join(dots)
            + f'<circle r="{1.2 * scale:.1f}" fill="#FFF7E8" opacity="0.85"/>'
            + "</g>"
        )
    if glyph == "orchid":
        petals = []
        for index in range(5):
            petals.append(
                f'<ellipse rx="{3.3 * scale:.1f}" ry="{8.4 * scale:.1f}" '
                f'transform="rotate({index * 72:.1f}) translate(0,{-5.5 * scale:.1f})" '
                f'fill="{color}" opacity="0.92"/>'
            )
        return (
            f'<g transform="{transform}">'
            + "".join(petals)
            + f'<circle r="{2.8 * scale:.1f}" fill="#F8D98B"/>'
            + f'<circle r="{1.2 * scale:.1f}" fill="#B98345" opacity="0.7"/>'
            + "</g>"
        )
    if glyph == "lotus":
        petals = []
        for index in range(8):
            petals.append(
                f'<path d="M 0 {-2 * scale:.1f} C {3 * scale:.1f} {-7 * scale:.1f} '
                f'{3 * scale:.1f} {-12 * scale:.1f} 0 {-16 * scale:.1f} '
                f'C {-3 * scale:.1f} {-12 * scale:.1f} {-3 * scale:.1f} {-7 * scale:.1f} 0 {-2 * scale:.1f} Z" '
                f'transform="rotate({index * 45:.1f})" fill="{color}" opacity="0.92"/>'
            )
        return (
            f'<g transform="{transform}">'
            + "".join(petals)
            + f'<circle r="{3.0 * scale:.1f}" fill="#F8D98B"/>'
            + "</g>"
        )

    petals = []
    for index in range(8):
        petals.append(
            f'<ellipse rx="{3.3 * scale:.1f}" ry="{7.6 * scale:.1f}" '
            f'transform="rotate({index * 45:.1f}) translate(0,{-6.4 * scale:.1f})" '
            f'fill="{color}" opacity="0.94"/>'
        )
    return (
        f'<g transform="{transform}">'
        + "".join(petals)
        + f'<circle r="{3.8 * scale:.1f}" fill="#F8D98B" opacity="0.95"/>'
        + f'<circle r="{1.8 * scale:.1f}" fill="#B98345" opacity="0.72"/>'
        + "</g>"
    )


def preview_color(flower: Dict[str, Any], preferred_color: str = "任意", index: int = 0) -> str:
    palette = flower.get("palette") or palette_from_color(str(flower.get("color", "")))
    preferred = str(preferred_color or "任意").replace("色", "")
    if preferred and preferred != "任意":
        for root in color_roots(str(flower.get("color", ""))):
            if preferred == root or preferred in root:
                return COLOR_HEX.get(root, palette[0])
    return palette[index % len(palette)] if palette else "#F2A7BC"


def flower_glyph(flower: Dict[str, Any]) -> str:
    name = str(flower.get("name", ""))
    if "玫瑰" in name:
        return "rose"
    if "牡丹菊" in name:
        return "daisy"
    if any(keyword in name for keyword in ["芍药", "牡丹", "洋牡丹", "洋桔梗", "康乃馨"]):
        return "rose"
    if any(keyword in name for keyword in ["菊", "扶郎", "向日葵", "大丽花", "梅花", "桃花", "樱花", "茉莉", "栀子"]):
        return "daisy"
    if any(keyword in name for keyword in ["百合", "马蹄莲", "郁金香", "银莲花", "香雪兰", "红掌"]):
        return "cup"
    if any(
        keyword in name
        for keyword in [
            "绣球",
            "满天星",
            "勿忘我",
            "情人草",
            "水晶草",
            "蕾丝",
            "翠珠",
            "蓝星",
            "松虫",
            "相思梅",
            "澳洲米花",
            "腊梅",
            "雪柳",
            "小手球",
            "丁香",
            "黄金球",
            "百子莲",
        ]
    ):
        return "cluster"
    if any(keyword in name for keyword in ["紫罗兰", "金鱼草", "剑兰", "飞燕", "风铃", "晚香玉", "姜花", "蒲棒", "芦苇"]):
        return "spike"
    if "兰" in name or "天堂鸟" in name:
        return "orchid"
    if any(keyword in name for keyword in ["荷", "睡莲", "莲蓬"]):
        return "lotus"
    return "daisy"


def foliage_color(flower: Dict[str, Any]) -> str:
    greens = {"#78A984", "#A7B3A3", "#4F7A58", "#3F6B4A", "#B5C95A", "#6F9070"}
    for color in flower.get("palette") or []:
        if color in greens:
            return color
    return "#6F9070"


def _region_for_shape(shape_key: str) -> Tuple[float, float, float, float]:
    if shape_key == "box":
        return 230.0, 220.0, 108.0, 86.0
    if shape_key == "basket":
        return 230.0, 210.0, 118.0, 92.0
    if shape_key == "fan":
        return 230.0, 228.0, 152.0, 118.0
    if shape_key == "cascade":
        return 230.0, 222.0, 112.0, 140.0
    if shape_key == "one_sided":
        return 238.0, 215.0, 128.0, 112.0
    return 230.0, 214.0, 126.0, 108.0


def _points_in_region(count: int, region: Tuple[float, float, float, float], seed: int = 0) -> List[Tuple[float, float]]:
    if count <= 0:
        return []
    cx, cy, rx, ry = region
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    points: List[Tuple[float, float]] = []
    for index in range(count):
        ratio = math.sqrt((index + 0.65) / count)
        angle = index * golden_angle + seed * 0.37
        x = cx + math.cos(angle) * rx * ratio
        y = cy + math.sin(angle) * ry * ratio
        points.append((x, y))
    return points


def _wrapping_svg(shape_key: str, packaging_key: str, ribbon_key: str) -> str:
    packaging = PACKAGING_OPTIONS.get(packaging_key, PACKAGING_OPTIONS["misty"])
    ribbon = RIBBON_OPTIONS.get(ribbon_key, RIBBON_OPTIONS["champagne"])
    light, dark = packaging["paper"]
    ribbon_hex = ribbon["hex"]
    paper_gradient = (
        '<defs>'
        f'<linearGradient id="paper" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{light}"/>'
        f'<stop offset="100%" stop-color="{dark}"/>'
        "</linearGradient>"
        '<linearGradient id="ribbon" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{ribbon_hex}" stop-opacity="0.75"/>'
        f'<stop offset="50%" stop-color="{ribbon_hex}"/>'
        f'<stop offset="100%" stop-color="{ribbon_hex}" stop-opacity="0.72"/>'
        "</linearGradient>"
        '<filter id="softShadow" x="-30%" y="-30%" width="160%" height="160%">'
        '<feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#6B4A5A" flood-opacity="0.14"/>'
        "</filter>"
        "</defs>"
    )
    if shape_key == "box":
        paper = (
            '<g filter="url(#softShadow)">'
            '<rect x="122" y="218" width="216" height="158" rx="18" fill="url(#paper)"/>'
            '<rect x="112" y="205" width="236" height="34" rx="12" fill="#FFFFFF" opacity="0.28"/>'
            '<rect x="122" y="218" width="216" height="158" rx="18" fill="none" stroke="#FFFFFF" stroke-opacity="0.35"/>'
            "</g>"
        )
        bow_y = 330
    elif shape_key == "basket":
        paper = (
            '<g filter="url(#softShadow)">'
            '<path d="M128 242 L332 242 L304 386 Q302 398 288 398 L172 398 Q158 398 156 386 Z" fill="url(#paper)"/>'
            '<path d="M154 252 Q230 150 306 252" fill="none" stroke="#A97852" stroke-width="9" stroke-linecap="round" opacity="0.75"/>'
            '<path d="M134 278 L326 278" stroke="#FFFFFF" stroke-width="2" opacity="0.35"/>'
            "</g>"
        )
        bow_y = 300
    elif shape_key == "fan":
        paper = (
            '<g filter="url(#softShadow)">'
            '<path d="M72 310 C92 186 162 106 230 92 C298 106 368 186 388 310 Z" fill="url(#paper)"/>'
            '<path d="M176 306 L230 416 L284 306 Z" fill="url(#paper)" opacity="0.95"/>'
            '<path d="M96 300 C120 200 170 140 230 124" fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.28"/>'
            "</g>"
        )
        bow_y = 310
    elif shape_key == "one_sided":
        paper = (
            '<g filter="url(#softShadow)">'
            '<path d="M104 312 C124 184 196 104 258 94 C322 118 352 198 358 312 L286 312 L230 416 L170 312 Z" fill="url(#paper)"/>'
            '<path d="M116 300 C140 194 204 130 262 120" fill="none" stroke="#FFFFFF" stroke-width="2.4" opacity="0.32"/>'
            '<path d="M268 120 C320 158 344 226 348 300" fill="none" stroke="#FFFFFF" stroke-width="2.4" opacity="0.22"/>'
            "</g>"
        )
        bow_y = 312
    elif shape_key == "cascade":
        paper = (
            '<g filter="url(#softShadow)">'
            '<path d="M146 286 C156 168 198 96 230 86 C262 96 304 168 314 286 '
            'C332 348 300 404 230 420 C160 404 128 348 146 286 Z" fill="url(#paper)"/>'
            '<path d="M164 286 C176 190 208 132 230 118" fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.3"/>'
            "</g>"
        )
        bow_y = 300
    else:
        paper = (
            '<g filter="url(#softShadow)">'
            '<path d="M108 306 C122 186 176 104 230 94 C284 104 338 186 352 306 Z" fill="url(#paper)"/>'
            '<path d="M178 304 L230 416 L282 304 Z" fill="url(#paper)" opacity="0.96"/>'
            '<path d="M128 290 C146 200 184 140 230 118" fill="none" stroke="#FFFFFF" stroke-width="2" opacity="0.3"/>'
            "</g>"
        )
        bow_y = 306
    ribbon_svg = (
        f'<g transform="translate(230,{bow_y})">'
        f'<path d="M0 0 C-30 -18 -48 4 -18 12 C-8 15 -2 8 0 2 Z" fill="url(#ribbon)"/>'
        f'<path d="M0 0 C30 -18 48 4 18 12 C8 15 2 8 0 2 Z" fill="url(#ribbon)"/>'
        f'<path d="M-4 6 C-18 30 -26 48 -18 58 C-8 50 -4 30 4 12 Z" fill="url(#ribbon)" opacity="0.9"/>'
        f'<path d="M4 6 C18 30 26 48 18 58 C8 50 4 30 -4 12 Z" fill="url(#ribbon)" opacity="0.9"/>'
        f'<circle r="6" fill="{ribbon_hex}"/>'
        "</g>"
    )
    return paper_gradient + paper + ribbon_svg


def build_svg_preview(
    selected: Sequence[Dict[str, Any]],
    quantities: Dict[Any, Any],
    size_key: str,
    shape_key: str,
    packaging_key: str,
    ribbon_key: str,
    width: int = 460,
    height: int = 460,
    color_preference: str = "任意",
) -> str:
    region = _region_for_shape(shape_key)
    foliage = [flower for flower in selected if flower.get("category") == "叶材"]
    filler = [flower for flower in selected if flower.get("category") == "配花"]
    fruit = [flower for flower in selected if flower.get("category") == "果材"]
    main = [flower for flower in selected if flower.get("category") == "主花"]
    if not (foliage or filler or fruit or main):
        main = list(selected)

    layers: List[str] = []
    total_flowers = sum(max(1, qty_for(quantities, int(flower["id"]))) for flower in selected)
    scale = 1.35 if total_flowers <= 36 else (1.1 if total_flowers <= 64 else (0.88 if total_flowers <= 100 else 0.72))

    # 叶材打底
    leaf_points = _points_in_region(
        sum(max(1, qty_for(quantities, int(flower["id"]))) for flower in foliage),
        (region[0], region[1] + 8, region[2] * 1.04, region[3] * 1.08),
        seed=9,
    )
    cursor = 0
    for flower in foliage:
        quantity = max(1, qty_for(quantities, int(flower["id"])))
        color = foliage_color(flower)
        for index in range(quantity):
            if cursor >= len(leaf_points):
                break
            x, y = leaf_points[cursor]
            for leaf_index in range(3):
                leaf_x = x + ((leaf_index % 2) - 0.5) * 9 * scale
                leaf_y = y + (leaf_index - 1) * 4 * scale
                leaf_angle = (index * 47 + flower["id"] * 13 + leaf_index * 68) % 360
                layers.append(_svg_leaf(leaf_x, leaf_y, leaf_angle, color, 0.95 * scale))
            cursor += 1

    # 配花
    filler_points = _points_in_region(
        sum(max(1, qty_for(quantities, int(flower["id"]))) for flower in filler),
        (region[0], region[1], region[2] * 0.94, region[3] * 0.94),
        seed=21,
    )
    cursor = 0
    for flower in filler:
        quantity = max(1, qty_for(quantities, int(flower["id"])))
        for index in range(quantity):
            if cursor >= len(filler_points):
                break
            x, y = filler_points[cursor]
            layers.append(
                _svg_bloom(
                    x,
                    y,
                    preview_color(flower, color_preference, index),
                    0,
                    scale,
                    "filler",
                    flower_glyph(flower),
                )
            )
            cursor += 1

    # 主花
    main_points = _points_in_region(
        sum(max(1, qty_for(quantities, int(flower["id"]))) for flower in main),
        (region[0], region[1] - 2, region[2] * 0.82, region[3] * 0.82),
        seed=37,
    )
    cursor = 0
    for flower in main:
        quantity = max(1, qty_for(quantities, int(flower["id"])))
        for index in range(quantity):
            if cursor >= len(main_points):
                break
            x, y = main_points[cursor]
            layers.append(
                _svg_bloom(
                    x,
                    y,
                    preview_color(flower, color_preference, index),
                    (index * 31 + flower["id"] * 7) % 360,
                    scale,
                    "main",
                    flower_glyph(flower),
                )
            )
            cursor += 1

    # 果材点睛
    fruit_points = _points_in_region(
        sum(max(1, qty_for(quantities, int(flower["id"]))) for flower in fruit),
        (region[0], region[1] + 6, region[2] * 0.76, region[3] * 0.76),
        seed=53,
    )
    cursor = 0
    for flower in fruit:
        quantity = max(1, qty_for(quantities, int(flower["id"])))
        for index in range(quantity):
            if cursor >= len(fruit_points):
                break
            x, y = fruit_points[cursor]
            layers.append(
                _svg_bloom(
                    x,
                    y,
                    preview_color(flower, color_preference, index),
                    0,
                    scale,
                    "fruit",
                )
            )
            cursor += 1

    shape = SHAPE_OPTIONS.get(shape_key, SHAPE_OPTIONS["round"])
    packaging = PACKAGING_OPTIONS.get(packaging_key, PACKAGING_OPTIONS["misty"])
    config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 460 460" role="img" aria-label="花束结构示意图">'
        '<defs>'
        '<radialGradient id="bg" cx="50%" cy="35%" r="75%">'
        '<stop offset="0%" stop-color="#FFFDF9"/>'
        '<stop offset="100%" stop-color="#F7EDF0"/>'
        "</radialGradient>"
        '<radialGradient id="halo" cx="50%" cy="45%" r="55%">'
        '<stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.75"/>'
        '<stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>'
        "</radialGradient>"
        "</defs>"
        '<rect width="460" height="460" rx="28" fill="url(#bg)"/>'
        '<circle cx="230" cy="220" r="178" fill="url(#halo)"/>'
        '<ellipse cx="230" cy="420" rx="122" ry="12" fill="#7C5A6A" opacity="0.10"/>'
        + _wrapping_svg(shape_key, packaging_key, ribbon_key)
        + "".join(layers)
        + f'<text x="26" y="38" font-family="PingFang SC, Microsoft YaHei, sans-serif" '
        f'font-size="13" fill="#6D5866" opacity="0.85">{_nice_text(shape["label"])} · {_nice_text(config["label"])}</text>'
        f'<text x="26" y="58" font-family="PingFang SC, Microsoft YaHei, sans-serif" '
        f'font-size="11" fill="#9A8792">{_nice_text(packaging["label"])} · 按当前支数绘制</text>'
        f'<text x="434" y="438" text-anchor="end" font-family="PingFang SC, Microsoft YaHei, sans-serif" '
        f'font-size="10" fill="#A18F9A">结构示意 · 非 AI 生成</text>'
        "</svg>"
    )


def svg_data_uri(svg: str) -> str:
    import base64

    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def parse_json_object(text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = str(text).strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = cleaned[start : end + 1]
    attempts = [
        candidate,
        re.sub(
            r",\s*([}\]])",
            r"\1",
            candidate.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'"),
        ),
    ]
    for attempt in attempts:
        try:
            value = json.loads(attempt)
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def parse_free_text_local(text: str) -> Dict[str, Any]:
    text = str(text or "")
    parsed: Dict[str, Any] = {}
    target_keywords = {
        "妈妈": "家人",
        "母亲": "家人",
        "爸爸": "家人",
        "父亲": "家人",
        "老婆": "恋人",
        "女友": "恋人",
        "女朋友": "恋人",
        "男友": "恋人",
        "男朋友": "恋人",
        "老公": "恋人",
        "恋人": "恋人",
        "朋友": "朋友",
        "闺蜜": "朋友",
        "老师": "老师",
        "客户": "客户",
        "孩子": "孩子",
        "自己": "自己",
    }
    for keyword, target in target_keywords.items():
        if keyword in text:
            parsed["target"] = target
            break
    for occasion in sorted(OCCASIONS, key=len, reverse=True):
        if occasion in text:
            parsed["occasion"] = occasion
            break
    color_keywords = ["香槟", "红", "粉", "白", "紫", "黄", "橙", "蓝", "绿"]
    for color in color_keywords:
        if color in text:
            if re.search(rf"(不要|别|避开|不喜欢)\s*太?{re.escape(color)}", text):
                continue
            parsed["color"] = color if color == "香槟" else color + "色"
            break
    style_keywords = {
        "温柔": "温柔治愈",
        "治愈": "温柔治愈",
        "清新": "清新自然",
        "自然": "清新自然",
        "简约": "简约高级",
        "高级": "简约高级",
        "复古": "复古",
        "可爱": "可爱",
        "华丽": "华丽大气",
        "大气": "华丽大气",
        "阳光": "阳光活力",
        "浪漫": "浪漫",
    }
    for keyword, style in style_keywords.items():
        if keyword in text:
            parsed["style"] = style
            break
    budget_match = re.search(r"(?:预算|不超过|控制在|大概|大约)?\s*(\d{2,4})\s*(?:元|块|rmb|RMB)?", text)
    if budget_match:
        value = int(budget_match.group(1))
        if 50 <= value <= 2000:
            parsed["budget"] = value
    return parsed


def filter_flowers(
    flowers: Sequence[Dict[str, Any]],
    search: str = "",
    category: str = "全部",
    color: str = "任意",
    season: str = "当季",
    max_price: float = 999,
    sort_key: str = "当季优先",
) -> List[Dict[str, Any]]:
    current = current_season()
    tokens = [token for token in re.split(r"[\s,，、。;；]+", search.strip()) if token]
    results: List[Dict[str, Any]] = []
    for flower in flowers:
        if category not in {"全部", "", None} and flower.get("category") != category:
            continue
        if color not in {"任意", "", None} and color not in str(flower.get("color", "")):
            continue
        if season not in {"不限", "", None}:
            target_season = current if season == "当季" else season
            tags = flower.get("season_tags", [])
            if target_season not in tags and "全年" not in tags:
                continue
        if float(flower.get("unit_price", 0)) > max_price:
            continue
        if tokens:
            text = " ".join(
                [
                    str(flower.get("name", "")),
                    str(flower.get("english_name", "")),
                    str(flower.get("color", "")),
                    str(flower.get("language", "")),
                    str(flower.get("style", "")),
                    " ".join(str(value) for value in flower.get("occasion", [])),
                    " ".join(str(value) for value in flower.get("target", [])),
                ]
            )
            if not any(token in text for token in tokens):
                continue
        results.append(flower)

    if sort_key == "价格从低到高":
        results.sort(key=lambda flower: (float(flower.get("unit_price", 0)), flower.get("name", "")))
    elif sort_key == "价格从高到低":
        results.sort(key=lambda flower: (-float(flower.get("unit_price", 0)), flower.get("name", "")))
    elif sort_key == "名称":
        results.sort(key=lambda flower: str(flower.get("name", "")))
    else:
        results.sort(
            key=lambda flower: (
                0 if current in flower.get("season_tags", []) else (1 if "全年" in flower.get("season_tags", []) else 2),
                -float(flower.get("unit_price", 0)),
            )
        )
    return results


def build_order_summary(order: Dict[str, Any]) -> str:
    items = order.get("items", [])
    item_lines = [
        f"- {item.get('name', '')}（{item.get('category', '配花')}）× {item.get('quantity', 0)} 支：¥{item.get('subtotal', 0):.0f}"
        for item in items
    ]
    price = order.get("price", {})
    lines = [
        f"订单号：{order.get('order_id', '')}",
        f"收花人：{order.get('recipient', '')}  {order.get('phone', '')}",
        f"配送：{order.get('delivery_date', '')} {order.get('delivery_slot', '')}  {order.get('address', '')}",
        f"尺寸：{order.get('size_label', '')}",
        f"形态：{order.get('shape_label', '')} · 包装：{order.get('packaging_label', '')} · 丝带：{order.get('ribbon_label', '')}",
        "花材：",
        *item_lines,
        f"花材费：¥{price.get('flower_cost', 0):.0f}",
        f"包装与手工：¥{price.get('packaging_cost', 0) + price.get('labor_cost', 0):.0f}",
        f"配送费：¥{price.get('delivery_fee', 0):.0f}",
        f"合计：¥{price.get('total_price', 0):.0f}",
        f"祝福语：{order.get('message', '') or '无'}",
    ]
    return "\n".join(lines)
