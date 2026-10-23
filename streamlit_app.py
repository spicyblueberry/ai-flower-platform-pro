"""
AI 花束定制平台 · 优化版

本版围绕四个目标重做：
1. 更可靠的 AI 搭配与生图：OpenAI 兼容接口、英文花材清单、可选视觉一致性校验。
2. 更精致的前端：统一色系、卡片化花材、三步式工作台、移动端适配。
3. 包装材质与花束形态：材质、形态、丝带均影响预览、价格和生图提示词。
4. 双入口选花：AI 智能推荐 + 当季花材库直接挑选。
"""
from __future__ import annotations

import base64
import hashlib
import html as html_lib
from io import BytesIO
import json
import os
import re
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
import streamlit as st
from dotenv import load_dotenv

from bouquet_core import (
    CATEGORY_META,
    CATEGORY_ORDER,
    COLOR_CHOICES,
    OCCASIONS,
    PACKAGING_OPTIONS,
    RIBBON_OPTIONS,
    SEASON_CHOICES,
    SHAPE_OPTIONS,
    SIZE_CONFIG,
    STYLE_CHOICES,
    TARGETS,
    build_image_prompt,
    build_negative_prompt,
    build_order_summary,
    build_svg_preview,
    color_roots,
    compose_recommendation,
    current_season,
    default_quantity,
    filter_flowers,
    flower_emoji,
    load_flowers,
    max_quantity,
    parse_free_text_local,
    parse_json_object,
    price_breakdown,
    qty_for,
    recommend_local,
    score_flower,
    shortlist_for_llm,
    size_for_budget,
    svg_data_uri,
    tune_quantities_to_budget,
)


# ============================================================
# 页面与主题
# ============================================================
st.set_page_config(
    page_title="信心花舍 · AI 花束定制",
    page_icon="💐",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv()

_SECRETS_STATE: Optional[bool] = None


def _secrets_ready() -> bool:
    global _SECRETS_STATE
    if _SECRETS_STATE is None:
        try:
            _SECRETS_STATE = bool(st.secrets.load_if_toml_exists())
        except Exception:
            _SECRETS_STATE = False
    return _SECRETS_STATE


def _setting(name: str, default: str = "") -> str:
    if _secrets_ready():
        try:
            value = st.secrets.get(name, None)
            if value not in (None, ""):
                return str(value)
        except Exception:
            pass
    return os.getenv(name, default)


def _usable_key(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and "你的" not in text and text not in {"sk-...", "...", "YOUR_API_KEY"}


ECNU_KEY = _setting("ECNU_API_KEY")
OPENAI_KEY = _setting("OPENAI_API_KEY")
GENERIC_KEY = _setting("LLM_API_KEY")
ARK_KEY = _setting("ARK_API_KEY")
ARK_BASE = _setting("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
ARK_MODEL = _setting("ARK_MODEL")
ARK_IMAGE_MODEL = _setting("ARK_IMAGE_MODEL")
LLM_PROVIDER = _setting("LLM_PROVIDER").strip().lower()

LLM_KEY = ""
LLM_BASE = _setting("ECNU_API_BASE", "https://chat.ecnu.edu.cn/open/api/v1").rstrip("/")
LLM_MODEL = _setting("ECNU_MODEL", "ecnu-plus")
LLM_PROVIDER_LABEL = "未配置"

if LLM_PROVIDER == "generic" and _usable_key(GENERIC_KEY):
    LLM_KEY = GENERIC_KEY
    LLM_BASE = _setting("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    LLM_MODEL = _setting("LLM_MODEL", "gpt-4o-mini")
    LLM_PROVIDER_LABEL = "OpenAI 兼容"
elif LLM_PROVIDER == "ark" and _usable_key(ARK_KEY) and _usable_key(ARK_MODEL):
    LLM_KEY = ARK_KEY
    LLM_BASE = ARK_BASE
    LLM_MODEL = ARK_MODEL
    LLM_PROVIDER_LABEL = "Ark / 豆包"
elif LLM_PROVIDER == "ecnu" and _usable_key(ECNU_KEY):
    LLM_KEY = ECNU_KEY
    LLM_BASE = _setting("ECNU_API_BASE", "https://chat.ecnu.edu.cn/open/api/v1").rstrip("/")
    LLM_MODEL = _setting("ECNU_MODEL", "ecnu-plus")
    LLM_PROVIDER_LABEL = "ECNU"
elif LLM_PROVIDER == "openai" and _usable_key(OPENAI_KEY):
    LLM_KEY = OPENAI_KEY
    LLM_BASE = _setting("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    LLM_MODEL = _setting("OPENAI_MODEL", "gpt-4o-mini")
    LLM_PROVIDER_LABEL = "OpenAI"
elif _usable_key(GENERIC_KEY):
    LLM_KEY = GENERIC_KEY
    LLM_BASE = _setting("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    LLM_MODEL = _setting("LLM_MODEL", "gpt-4o-mini")
    LLM_PROVIDER_LABEL = "OpenAI 兼容"
elif _usable_key(ARK_KEY) and _usable_key(ARK_MODEL):
    LLM_KEY = ARK_KEY
    LLM_BASE = ARK_BASE
    LLM_MODEL = ARK_MODEL
    LLM_PROVIDER_LABEL = "Ark / 豆包"
elif _usable_key(ECNU_KEY):
    LLM_KEY = ECNU_KEY
    LLM_BASE = _setting("ECNU_API_BASE", "https://chat.ecnu.edu.cn/open/api/v1").rstrip("/")
    LLM_MODEL = _setting("ECNU_MODEL", "ecnu-plus")
    LLM_PROVIDER_LABEL = "ECNU"
elif _usable_key(OPENAI_KEY):
    LLM_KEY = OPENAI_KEY
    LLM_BASE = _setting("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    LLM_MODEL = _setting("OPENAI_MODEL", "gpt-4o-mini")
    LLM_PROVIDER_LABEL = "OpenAI"

LLM_KEY = LLM_KEY if _usable_key(LLM_KEY) else ""

IMAGE_KEY = ""
IMAGE_BASE = ""
IMAGE_MODEL = ""
IMAGE_PROVIDER_LABEL = "未配置"
_image_api_key = _setting("IMAGE_API_KEY")
if _usable_key(_image_api_key):
    IMAGE_KEY = _image_api_key
    IMAGE_BASE = (_setting("IMAGE_API_BASE") or LLM_BASE).rstrip("/")
    IMAGE_MODEL = _setting("IMAGE_MODEL") or "gpt-image-1"
    IMAGE_PROVIDER_LABEL = "OpenAI 兼容"
elif _usable_key(ARK_KEY) and _usable_key(ARK_IMAGE_MODEL):
    IMAGE_KEY = ARK_KEY
    IMAGE_BASE = _setting("ARK_IMAGE_BASE", ARK_BASE).rstrip("/")
    IMAGE_MODEL = ARK_IMAGE_MODEL
    IMAGE_PROVIDER_LABEL = "Ark / Seedream"
elif _usable_key(ECNU_KEY):
    IMAGE_KEY = ECNU_KEY
    IMAGE_BASE = _setting("ECNU_API_BASE", "https://chat.ecnu.edu.cn/open/api/v1").rstrip("/")
    IMAGE_MODEL = _setting("ECNU_IMAGE_MODEL") or "ecnu-image"
    IMAGE_PROVIDER_LABEL = "ECNU"
elif _usable_key(OPENAI_KEY):
    IMAGE_KEY = OPENAI_KEY
    IMAGE_BASE = _setting("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    IMAGE_MODEL = _setting("IMAGE_MODEL") or "gpt-image-1"
    IMAGE_PROVIDER_LABEL = "OpenAI"
elif LLM_PROVIDER_LABEL == "OpenAI 兼容" and _usable_key(LLM_KEY):
    IMAGE_KEY = LLM_KEY
    IMAGE_BASE = LLM_BASE
    IMAGE_MODEL = _setting("IMAGE_MODEL") or "gpt-image-1"
    IMAGE_PROVIDER_LABEL = "OpenAI 兼容"

ARK_KEY_PRESENT = _usable_key(ARK_KEY)
ARK_MODEL_MISSING = ARK_KEY_PRESENT and not _usable_key(ARK_MODEL)
ARK_IMAGE_MODEL_MISSING = ARK_KEY_PRESENT and not _usable_key(ARK_IMAGE_MODEL)

_vision_key = _setting("VISION_API_KEY") or LLM_KEY
VISION_KEY = _vision_key if _usable_key(_vision_key) else ""
VISION_BASE = (_setting("VISION_API_BASE") or LLM_BASE).rstrip("/")
VISION_MODEL = _setting("VISION_MODEL")
IMAGE_COOLDOWN_SECONDS = int(_setting("IMAGE_COOLDOWN_SECONDS", "20") or 20)
DAILY_IMAGE_LIMIT = int(_setting("DAILY_IMAGE_LIMIT", "12") or 12)
LLM_RECOMMEND_TIMEOUT = int(_setting("LLM_RECOMMEND_TIMEOUT", "120") or 120)
LLM_RECOMMEND_MAX_TOKENS = int(_setting("LLM_RECOMMEND_MAX_TOKENS", "600") or 600)
LLM_RECOMMEND_ATTEMPTS = int(_setting("LLM_RECOMMEND_ATTEMPTS", "1") or 1)
LLM_SHORTLIST_PER_CATEGORY = int(_setting("LLM_SHORTLIST_PER_CATEGORY", "6") or 6)
CN_TZ = timezone(timedelta(hours=8))


def now_cn() -> datetime:
    return datetime.now(CN_TZ)


def brand_logo_data_uri() -> str:
    """芍药品牌标识：外层 8 瓣、内层 6 瓣、中心 5 瓣 + 金色花心。"""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="outerRose" x1="18" y1="8" x2="46" y2="56" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#E9BCC9"/>
      <stop offset="1" stop-color="#A95776"/>
    </linearGradient>
    <linearGradient id="outerPlum" x1="18" y1="8" x2="46" y2="56" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#C9879E"/>
      <stop offset="1" stop-color="#6E4B73"/>
    </linearGradient>
    <linearGradient id="middleRose" x1="24" y1="14" x2="40" y2="46" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#E8B6C4"/>
      <stop offset="1" stop-color="#A95776"/>
    </linearGradient>
    <linearGradient id="innerPlum" x1="27" y1="20" x2="37" y2="38" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#D394AA"/>
      <stop offset="1" stop-color="#754E79"/>
    </linearGradient>
    <linearGradient id="gold" x1="28" y1="8" x2="38" y2="36" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#E8CE98"/>
      <stop offset="1" stop-color="#B58446"/>
    </linearGradient>
  </defs>
  <circle cx="32" cy="32" r="30.5" fill="none" stroke="#B25F7C" stroke-opacity=".13" stroke-width=".6" stroke-dasharray="1.2 4.2"/>
  <g stroke="#FFF9F5" stroke-opacity=".48" stroke-width=".48" stroke-linejoin="round">
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#outerRose)"/>
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#gold)" transform="rotate(45 32 32)"/>
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#outerPlum)" transform="rotate(90 32 32)"/>
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#outerRose)" transform="rotate(135 32 32)"/>
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#outerPlum)" transform="rotate(180 32 32)"/>
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#outerRose)" transform="rotate(225 32 32)"/>
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#outerPlum)" transform="rotate(270 32 32)"/>
    <path d="M32 31C24 28 21 19 25 11C27 7 30 5 32 5C34 5 37 7 39 11C43 19 40 28 32 31Z" fill="url(#outerRose)" transform="rotate(315 32 32)"/>
    <path d="M32 31C27 28 25 22 27 16C29 13 31 12 32 12C33 12 35 13 37 16C39 22 37 28 32 31Z" fill="url(#middleRose)" opacity=".96" transform="rotate(30 32 32)"/>
    <path d="M32 31C27 28 25 22 27 16C29 13 31 12 32 12C33 12 35 13 37 16C39 22 37 28 32 31Z" fill="url(#middleRose)" opacity=".96" transform="rotate(90 32 32)"/>
    <path d="M32 31C27 28 25 22 27 16C29 13 31 12 32 12C33 12 35 13 37 16C39 22 37 28 32 31Z" fill="url(#middleRose)" opacity=".96" transform="rotate(150 32 32)"/>
    <path d="M32 31C27 28 25 22 27 16C29 13 31 12 32 12C33 12 35 13 37 16C39 22 37 28 32 31Z" fill="url(#middleRose)" opacity=".96" transform="rotate(210 32 32)"/>
    <path d="M32 31C27 28 25 22 27 16C29 13 31 12 32 12C33 12 35 13 37 16C39 22 37 28 32 31Z" fill="url(#middleRose)" opacity=".96" transform="rotate(270 32 32)"/>
    <path d="M32 31C27 28 25 22 27 16C29 13 31 12 32 12C33 12 35 13 37 16C39 22 37 28 32 31Z" fill="url(#middleRose)" opacity=".96" transform="rotate(330 32 32)"/>
    <path d="M32 31C28.5 29 27 25 28.5 21C30 18.5 31 18 32 18C33 18 34 18.5 35.5 21C37 25 35.5 29 32 31Z" fill="url(#innerPlum)" opacity=".97" transform="rotate(18 32 32)"/>
    <path d="M32 31C28.5 29 27 25 28.5 21C30 18.5 31 18 32 18C33 18 34 18.5 35.5 21C37 25 35.5 29 32 31Z" fill="url(#innerPlum)" opacity=".97" transform="rotate(90 32 32)"/>
    <path d="M32 31C28.5 29 27 25 28.5 21C30 18.5 31 18 32 18C33 18 34 18.5 35.5 21C37 25 35.5 29 32 31Z" fill="url(#innerPlum)" opacity=".97" transform="rotate(162 32 32)"/>
    <path d="M32 31C28.5 29 27 25 28.5 21C30 18.5 31 18 32 18C33 18 34 18.5 35.5 21C37 25 35.5 29 32 31Z" fill="url(#innerPlum)" opacity=".97" transform="rotate(234 32 32)"/>
    <path d="M32 31C28.5 29 27 25 28.5 21C30 18.5 31 18 32 18C33 18 34 18.5 35.5 21C37 25 35.5 29 32 31Z" fill="url(#innerPlum)" opacity=".97" transform="rotate(306 32 32)"/>
  </g>
  <circle cx="32" cy="32" r="4.4" fill="#FFF9F3"/>
  <path d="M32 28.3L35.7 32L32 35.7L28.3 32Z" fill="#B98B4E"/>
  <circle cx="32" cy="32" r="1.0" fill="#7A4D73" opacity=".78"/>
</svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


st.markdown(
    """
<style>
    :root {
        --ink: #2E2633;
        --muted: #7D6E7B;
        --plum: #6F4F77;
        --rose: #C75C7A;
        --rose-deep: #A84362;
        --blush: #F7DCE4;
        --cream: #FFFBF6;
        --sage: #7D9B7F;
        --gold: #C6A46A;
        --line: rgba(111, 79, 119, 0.14);
        --shadow: 0 18px 50px rgba(96, 64, 82, 0.10);
    }
    html, body, [class*="css"] {
        font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
        color: var(--ink);
    }
    .stApp {
        background:
            radial-gradient(circle at 6% 0%, rgba(247, 220, 228, 0.85) 0, rgba(247, 220, 228, 0) 34%),
            radial-gradient(circle at 94% 6%, rgba(232, 222, 242, 0.8) 0, rgba(232, 222, 242, 0) 30%),
            linear-gradient(180deg, #FFFCF8 0%, #FFF9F7 48%, #FBF7F4 100%);
    }
    header[data-testid="stHeader"] {
        background: transparent;
    }
    [data-testid="stToolbar"] {
        visibility: hidden;
        height: 0;
    }
    #MainMenu, footer { visibility: hidden; }
    .block-container {
        max-width: 1220px;
        padding-top: 1.1rem;
        padding-bottom: 3.5rem;
    }
    [data-testid="stSidebar"] {
        background: rgba(255, 252, 248, 0.78);
        border-right: 1px solid var(--line);
        backdrop-filter: blur(18px);
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.3rem;
    }
    [data-testid="stSidebar"] .stButton > button {
        width: 100%;
    }
    .brand-lockup {
        position: relative;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 2px 0 13px;
        margin-top: 2px;
    }
    .brand-lockup::after {
        content: "";
        position: absolute;
        left: 64px;
        right: 2px;
        bottom: 4px;
        height: 1px;
        background: linear-gradient(90deg, rgba(199, 92, 122, 0.48), rgba(199, 92, 122, 0));
    }
    .brand-logo {
        width: 52px;
        height: 52px;
        flex: 0 0 52px;
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 5px;
        background: linear-gradient(145deg, #FFFDFC 0%, #F8EBEF 100%);
        border: 1px solid rgba(199, 92, 122, 0.14);
        box-shadow:
            0 8px 18px rgba(142, 62, 76, 0.10),
            inset 0 0 0 1px rgba(255, 255, 255, 0.72);
    }
    .brand-logo img {
        width: 100%;
        height: 100%;
        display: block;
    }
    .brand-copy {
        min-width: 0;
    }
    .brand-cn {
        font-family: "Songti SC", "Noto Serif SC", "Source Han Serif SC", "STSong", "SimSun", Georgia, serif;
        font-size: 2.08rem;
        line-height: 1.08;
        font-weight: 600;
        letter-spacing: 0.09em;
        white-space: nowrap;
        color: #8E3E4C;
        background: linear-gradient(118deg, #6E2F3F 0%, #B95270 52%, #7A5A8C 100%);
        -webkit-background-clip: text;
        background-clip: text;
        filter: drop-shadow(0 3px 8px rgba(169, 80, 108, 0.16));
    }
    @supports ((-webkit-background-clip: text) or (background-clip: text)) {
        .brand-cn {
            color: transparent;
            -webkit-text-fill-color: transparent;
        }
    }
    .brand-en {
        margin-top: 5px;
        font-family: "Helvetica Neue", "Arial", sans-serif;
        font-size: 0.52rem;
        font-weight: 300;
        line-height: 1.2;
        letter-spacing: 0.23em;
        color: #9A8792;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .brand-tagline {
        margin: 1px 0 0 64px;
        font-size: 0.72rem;
        line-height: 1.5;
        letter-spacing: 0.07em;
        color: #8B7B88;
    }
    h1, h2, h3, h4 {
        color: var(--ink);
        letter-spacing: -0.02em;
    }
    p, li, label, span {
        line-height: 1.65;
    }
    .hero {
        position: relative;
        display: grid;
        grid-template-columns: minmax(0, 1.45fr) minmax(220px, 0.55fr);
        gap: 20px;
        align-items: center;
        padding: 26px 32px;
        border-radius: 26px;
        border: 1px solid rgba(199, 92, 122, 0.16);
        background:
            linear-gradient(120deg, rgba(255, 251, 248, 0.96) 0%, rgba(252, 239, 242, 0.92) 48%, rgba(240, 232, 246, 0.9) 100%);
        box-shadow: var(--shadow);
        overflow: hidden;
        margin-bottom: 14px;
    }
    .hero::after {
        content: "";
        position: absolute;
        width: 260px;
        height: 260px;
        right: -80px;
        top: -120px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.9), rgba(255,255,255,0));
    }
    .hero-kicker {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        color: var(--rose-deep);
        text-transform: uppercase;
        font-weight: 700;
    }
    .hero-title {
        font-family: "Songti SC", "Noto Serif SC", Georgia, serif;
        font-size: clamp(2rem, 4vw, 3rem);
        line-height: 1.14;
        margin: 8px 0 10px;
        font-weight: 700;
    }
    .hero-title .accent {
        color: var(--rose-deep);
    }
    .hero-sub {
        color: #6D5E6B;
        font-size: 0.98rem;
        max-width: 680px;
        margin: 0;
    }
    .hero-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 18px;
    }
    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 11px;
        border-radius: 999px;
        font-size: 0.76rem;
        color: #654F63;
        background: rgba(255, 255, 255, 0.7);
        border: 1px solid rgba(111, 79, 119, 0.12);
    }
    .hero-art {
        position: relative;
        min-height: 190px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .hero-art .halo {
        position: absolute;
        width: 190px;
        height: 190px;
        border-radius: 50%;
        background: conic-gradient(from 210deg, #F6DCE4, #EAE0F3, #F7EADB, #F6DCE4);
        opacity: 0.85;
        filter: blur(1px);
    }
    .hero-art .emoji {
        position: relative;
        font-size: 5.2rem;
        filter: drop-shadow(0 14px 18px rgba(111, 79, 119, 0.18));
    }
    .hero-art .dot {
        position: absolute;
        border-radius: 50%;
        background: #FFFFFF;
        opacity: 0.7;
    }
    .step-strip {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 2px 0 20px;
    }
    .step-pill {
        padding: 7px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        color: #7D6E7B;
        background: rgba(255, 255, 255, 0.62);
        border: 1px solid var(--line);
    }
    .step-pill.active {
        color: #FFFFFF;
        background: linear-gradient(135deg, #B95270, #75537F);
        border-color: transparent;
        box-shadow: 0 8px 18px rgba(169, 80, 108, 0.18);
    }
    .section-kicker {
        color: var(--rose-deep);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        margin-bottom: 2px;
    }
    .section-title {
        font-family: "Songti SC", "Noto Serif SC", Georgia, serif;
        font-size: 1.7rem;
        margin: 0 0 5px;
    }
    .section-sub {
        color: var(--muted);
        font-size: 0.9rem;
        margin: 0 0 18px;
    }
    .flower-card {
        position: relative;
        height: 100%;
        min-height: 166px;
        padding: 16px 16px 14px;
        border-radius: 22px;
        background: rgba(255, 255, 255, 0.88);
        border: 1px solid rgba(111, 79, 119, 0.13);
        box-shadow: 0 8px 22px rgba(96, 64, 82, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        overflow: hidden;
    }
    .flower-card:hover {
        transform: translateY(-3px);
        border-color: rgba(199, 92, 122, 0.42);
        box-shadow: 0 16px 30px rgba(96, 64, 82, 0.10);
    }
    .flower-card.selected {
        border: 1.5px solid rgba(199, 92, 122, 0.72);
        background: linear-gradient(160deg, rgba(255, 249, 249, 0.98), rgba(249, 238, 244, 0.94));
        box-shadow: 0 12px 26px rgba(199, 92, 122, 0.14);
    }
    .flower-orb {
        width: 52px;
        height: 52px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 27px;
        margin-bottom: 9px;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.55), 0 8px 18px rgba(96, 64, 82, 0.08);
    }
    .flower-photo {
        display: block;
        width: 100%;
        height: 150px;
        object-fit: contain;
        margin: 0 auto 12px;
        border-radius: 14px;
        background: transparent;
    }
    .fc-name {
        font-size: 1.08rem;
        font-weight: 750;
        margin: 5px 0 8px;
    }
    .fc-en {
        color: #9A8A96;
        font-size: 0.68rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-bottom: 7px;
    }
    .fc-lang {
        color: #6E5D6C;
        font-size: 0.82rem;
        line-height: 1.5;
        min-height: 24px;
        margin-bottom: 10px;
    }
    .fc-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        margin-bottom: 7px;
    }
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 8px;
        border-radius: 999px;
        font-size: 0.66rem;
        font-weight: 700;
        color: #FFFFFF;
        background: linear-gradient(135deg, #B95270, #8A5E92);
    }
    .badge.soft {
        color: #6D5866;
        background: rgba(199, 92, 122, 0.10);
        border: 1px solid rgba(199, 92, 122, 0.14);
    }
    .price {
        font-size: 0.78rem;
        color: var(--rose-deep);
        font-weight: 700;
    }
    .fc-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
    .fc-tag {
        padding: 3px 8px;
        border-radius: 999px;
        font-size: 0.68rem;
        color: #7B6A78;
        background: rgba(111, 79, 119, 0.06);
    }
    .reason-line {
        color: #8E6B78;
        font-size: 0.68rem;
        margin-top: 6px;
    }
    .rec-card {
        padding: 22px 24px;
        border-radius: 24px;
        color: #FFFFFF;
        background:
            radial-gradient(circle at 88% 10%, rgba(255,255,255,0.18), transparent 34%),
            linear-gradient(135deg, #7A4F73 0%, #A9516C 55%, #C9798C 100%);
        box-shadow: 0 18px 34px rgba(122, 79, 115, 0.20);
        margin: 10px 0 18px;
    }
    .rec-card .rec-title {
        font-family: "Songti SC", "Noto Serif SC", Georgia, serif;
        font-size: 1.4rem;
        margin-bottom: 8px;
    }
    .rec-card .rec-text {
        font-size: 0.93rem;
        line-height: 1.8;
        opacity: 0.94;
    }
    .rec-card .rec-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 14px;
    }
    .rec-card .rec-chip {
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        background: rgba(255,255,255,0.16);
        border: 1px solid rgba(255,255,255,0.18);
    }
    .empty-state {
        text-align: center;
        padding: 34px 24px;
        border-radius: 24px;
        border: 1px dashed rgba(111, 79, 119, 0.24);
        background: rgba(255, 255, 255, 0.55);
        color: var(--muted);
    }
    .empty-state .empty-emoji {
        font-size: 2.6rem;
        margin-bottom: 6px;
    }
    .empty-state .empty-title {
        color: var(--ink);
        font-size: 1.05rem;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .summary-card {
        padding: 16px 18px;
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid var(--line);
    }
    .summary-card .summary-label {
        color: var(--muted);
        font-size: 0.7rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .summary-card .summary-value {
        font-size: 1.35rem;
        font-weight: 800;
        color: var(--rose-deep);
    }
    .basket-row {
        padding: 12px 14px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.66);
        margin-bottom: 8px;
    }
    .basket-name {
        font-weight: 700;
        font-size: 0.95rem;
    }
    .basket-sub {
        color: var(--muted);
        font-size: 0.72rem;
    }
    .order-card {
        padding: 22px 24px;
        border-radius: 22px;
        background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(250, 240, 244, 0.9));
        border: 1px solid rgba(199, 92, 122, 0.18);
        box-shadow: 0 12px 28px rgba(96, 64, 82, 0.07);
    }
    .order-id {
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        color: var(--rose-deep);
        text-transform: uppercase;
    }
    .order-total {
        font-size: 1.8rem;
        font-weight: 800;
        color: var(--rose-deep);
    }
    .stButton > button {
        border-radius: 999px;
        border: 1px solid rgba(111, 79, 119, 0.16);
        background: rgba(255, 255, 255, 0.9);
        color: #5D4B5B;
        font-weight: 650;
        padding: 0.52rem 1rem;
        transition: all 0.18s ease;
    }
    .stButton > button:hover {
        border-color: rgba(199, 92, 122, 0.46);
        color: var(--rose-deep);
        background: #FFFFFF;
        transform: translateY(-1px);
        box-shadow: 0 8px 18px rgba(96, 64, 82, 0.08);
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        color: #FFFFFF;
        border: none;
        background: linear-gradient(135deg, #B95270 0%, #8A5E92 100%);
        box-shadow: 0 10px 22px rgba(169, 80, 108, 0.20);
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover {
        color: #FFFFFF;
        box-shadow: 0 14px 26px rgba(169, 80, 108, 0.28);
    }
    .stButton > button:disabled {
        background: #E9E2E7 !important;
        color: #A99BA7 !important;
        border-color: transparent !important;
        box-shadow: none !important;
        transform: none !important;
    }
    .stDownloadButton > button {
        border-radius: 999px;
        border: 1px solid rgba(199, 92, 122, 0.28);
        background: rgba(255, 255, 255, 0.9);
        color: var(--rose-deep);
        font-weight: 650;
    }
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        border-radius: 12px !important;
        border-color: rgba(111, 79, 119, 0.16) !important;
        background: rgba(255, 255, 255, 0.9) !important;
    }
    .stSelectbox [data-baseweb="select"] > div {
        border-radius: 12px !important;
        border-color: rgba(111, 79, 119, 0.16) !important;
        background: rgba(255, 255, 255, 0.9) !important;
    }
    div[role="radiogroup"] {
        gap: 7px;
        flex-wrap: wrap;
    }
    div[role="radiogroup"] label {
        border: 1px solid rgba(111, 79, 119, 0.14);
        background: rgba(255, 255, 255, 0.78);
        border-radius: 999px;
        padding: 7px 13px;
        margin: 0 !important;
        transition: all 0.18s ease;
    }
    div[role="radiogroup"] label > div:first-child {
        display: none;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #B95270, #8A5E92);
        border-color: transparent;
        color: #FFFFFF;
        box-shadow: 0 8px 18px rgba(169, 80, 108, 0.18);
    }
    [data-testid="stMetric"] {
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.68);
        border: 1px solid var(--line);
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-size: 0.72rem;
    }
    [data-testid="stMetricValue"] {
        color: var(--ink);
        font-size: 1.35rem;
    }
    [data-testid="stExpander"] {
        border-radius: 16px;
        border-color: var(--line);
        background: rgba(255, 255, 255, 0.55);
    }
    .stAlert {
        border-radius: 14px;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #C75C7A, #8A5E92);
    }
    .stCodeBlock {
        border-radius: 14px;
    }
    .small-note {
        color: var(--muted);
        font-size: 0.8rem;
        line-height: 1.65;
    }
    .divider-soft {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(111,79,119,0.16), transparent);
        margin: 18px 0;
    }
    @media (max-width: 820px) {
        .block-container {
            padding-left: 0.9rem;
            padding-right: 0.9rem;
            padding-top: 0.8rem;
        }
        .hero {
            grid-template-columns: 1fr;
            padding: 22px 20px;
            border-radius: 22px;
        }
        .hero-art { display: none; }
        .hero-title { font-size: 1.9rem; }
        .flower-card { min-height: 158px; padding: 13px 12px; }
        .flower-photo { height: 130px; }
        .floating-note { display: none; }
    }
    @media (max-width: 700px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
        }
        [data-testid="column"] {
            min-width: 46% !important;
            flex: 1 1 46% !important;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# 数据与会话状态
# ============================================================
PROJECT_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(PROJECT_DIR, "assets_knowledge", "knowledge_base", "flower_knowledge.json")
FLOWER_IMAGE_DIR = os.path.join(PROJECT_DIR, "assets_knowledge", "assets", "flowers")


@st.cache_data(show_spinner=False, ttl=300)
def _load_data(path: str) -> List[Dict[str, Any]]:
    return load_flowers(path)


try:
    FLOWERS = _load_data(DATA_PATH)
except Exception as exc:
    st.error(f"花材知识库读取失败：{exc}")
    FLOWERS = []

DEFAULTS: Dict[str, Any] = {
    "nav": "AI 灵感",
    "target": "恋人",
    "occasion": "日常惊喜",
    "color": "粉色",
    "style": "浪漫",
    "budget": 320,
    "size": "M",
    "season_filter": "当季",
    "selected_flowers": [],
    "flower_quantities": {},
    "custom_roles": {},
    "recommend_result": None,
    "free_text": "",
    "pending_prefs": None,
    "auto_recommend": False,
    "gallery_name": "",
    "packaging": "misty",
    "shape": "round",
    "ribbon": "champagne",
    "custom_message": "",
    "generated_image": None,
    "last_image_time": 0.0,
    "image_counts": {},
    "orders": [],
    "llm_cache": {},
    "web_cache": {},
    "ai_web_enabled": False,
    "lib_page": 1,
    "lib_filter_sig": "",
    "library_search": "",
    "library_category": "全部",
    "library_color": "任意",
    "library_season": "当季",
    "library_max_price": 40,
    "library_sort": "当季优先",
    "last_order": None,
}

for _key, _value in DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _value

if "order_message" not in st.session_state:
    st.session_state.order_message = str(st.session_state.get("custom_message", "") or "")

# 兼容旧版本留下的字符串预算/尺寸值
if (
    not isinstance(st.session_state.get("budget"), int)
    or isinstance(st.session_state.get("budget"), bool)
    or not 80 <= int(st.session_state.get("budget")) <= 800
):
    st.session_state.budget = 320
if st.session_state.get("target") not in TARGETS:
    st.session_state.target = "恋人"
if st.session_state.get("occasion") not in OCCASIONS:
    st.session_state.occasion = "日常惊喜"
if st.session_state.get("color") not in COLOR_CHOICES:
    st.session_state.color = "粉色"
if st.session_state.get("style") not in STYLE_CHOICES:
    st.session_state.style = "浪漫"
if st.session_state.get("size") not in SIZE_CONFIG:
    st.session_state.size = "M"
if st.session_state.get("season_filter") not in SEASON_CHOICES:
    st.session_state.season_filter = "当季"
if st.session_state.get("packaging") not in PACKAGING_OPTIONS:
    st.session_state.packaging = "misty"
if st.session_state.get("shape") not in SHAPE_OPTIONS:
    st.session_state.shape = "round"
if st.session_state.get("ribbon") not in RIBBON_OPTIONS:
    st.session_state.ribbon = "champagne"

COLOR_ROOT_LABELS = {
    "红": "红色", "玫红": "玫红色", "粉": "粉色", "白": "白色",
    "米白": "米白色", "黄": "黄色", "金": "金色", "香槟": "香槟色",
    "紫": "紫色", "蓝": "蓝色", "灰": "灰色", "绿": "绿色",
    "橙": "橙色", "多色": "多色", "褐": "褐色", "棕": "棕色",
}
IMAGE_CODE_LABELS = {
    1: "红色", 2: "粉色", 3: "白色", 4: "黄色", 5: "香槟色",
    6: "紫色", 7: "蓝色", 8: "绿色", 9: "橙色", 10: "多色", 11: "褐色",
}
IMAGE_COLOR_CODES = {
    "红": 1, "玫红": 1, "粉": 2, "白": 3, "米白": 3, "黄": 4,
    "金": 4, "香槟": 5, "紫": 6, "蓝": 7, "灰": 7, "绿": 8,
    "橙": 9, "多色": 10, "褐": 11, "棕": 11,
}


@st.cache_data(show_spinner=False)
def _flower_image_index(directory: str) -> Dict[int, Dict[int, str]]:
    """Index local flower photos by flower id and filename color code."""
    indexed: Dict[int, Dict[int, str]] = {}
    if not os.path.isdir(directory):
        return indexed
    pattern = re.compile(r"^(\d+)_(\d+)(?:_\d+)?\.(?:png|jpe?g|webp)$", re.IGNORECASE)
    for filename in sorted(os.listdir(directory)):
        match = pattern.match(filename)
        if not match:
            continue
        flower_id, color_code = int(match.group(1)), int(match.group(2))
        indexed.setdefault(flower_id, {}).setdefault(
            color_code, os.path.join(directory, filename)
        )
    return indexed


def flower_color_options(flower: Dict[str, Any]) -> List[str]:
    """Use available photo variants as the source of selectable colors."""
    try:
        flower_id = int(flower["id"])
    except (KeyError, TypeError, ValueError):
        return ["多色"]
    variants = _flower_image_index(FLOWER_IMAGE_DIR).get(flower_id, {})
    options = [
        IMAGE_CODE_LABELS[code]
        for code in sorted(variants)
        if code in IMAGE_CODE_LABELS
    ]
    if options:
        return list(dict.fromkeys(options))
    return list(dict.fromkeys(
        COLOR_ROOT_LABELS.get(root, root)
        for root in color_roots(str(flower.get("color", "")))
    )) or ["多色"]


def _default_flower_color(flower: Dict[str, Any], preferred_color: str = "任意") -> str:
    options = flower_color_options(flower)
    preferred_roots = color_roots(preferred_color) if preferred_color not in {"", "任意"} else []
    for root in preferred_roots:
        label = COLOR_ROOT_LABELS.get(root, root)
        if label in options:
            return label
    return options[0] if options else "多色"


# 兼容旧版本 session_state：按 id 映射到最新花材数据，避免旧字典缺字段。
if FLOWERS:
    _by_id = {int(flower["id"]): flower for flower in FLOWERS}
    _migrated: List[Dict[str, Any]] = []
    _seen: set = set()
    for _flower in st.session_state.selected_flowers or []:
        try:
            _fid = int(_flower.get("id"))
        except (AttributeError, TypeError, ValueError):
            continue
        if _fid in _by_id and _fid not in _seen:
            _seen.add(_fid)
            _current = dict(_by_id[_fid])
            _old_color = str(_flower.get("selected_color", ""))
            _allowed_colors = [
                COLOR_ROOT_LABELS.get(root, root)
                for root in color_roots(str(_current.get("color", "")))
            ]
            _current["selected_color"] = (
                _old_color if _old_color in _allowed_colors else _default_flower_color(
                    _current, st.session_state.color
                )
            )
            _migrated.append(_current)
    st.session_state.selected_flowers = _migrated
    st.session_state.flower_quantities = {
        int(key): int(value)
        for key, value in (st.session_state.flower_quantities or {}).items()
        if str(key).isdigit() and int(key) in _seen
    }
    st.session_state.custom_roles = {
        int(key): str(value)
        for key, value in (st.session_state.custom_roles or {}).items()
        if str(key).isdigit() and int(key) in _seen
    }
    for _flower in _migrated:
        _fid = int(_flower["id"])
        if qty_for(st.session_state.flower_quantities, _fid) <= 0:
            st.session_state.flower_quantities[_fid] = default_quantity(
                _flower, st.session_state.size
            )
        st.session_state.custom_roles.setdefault(
            _fid,
            "主花" if _flower.get("category") == "主花" else "配花",
        )
    if st.session_state.recommend_result is not None and (
        not isinstance(st.session_state.recommend_result, dict)
        or "main" not in st.session_state.recommend_result
    ):
        st.session_state.recommend_result = None


def safe(value: Any) -> str:
    return html_lib.escape(str(value), quote=True)


def money(value: float) -> str:
    return f"¥{value:,.0f}"


def selected_ids() -> set:
    return {int(flower["id"]) for flower in st.session_state.selected_flowers}


def _set_flower_color(flower_id: int, widget_key: str) -> None:
    color = str(st.session_state.get(widget_key, ""))
    for item in st.session_state.selected_flowers:
        if int(item.get("id", 0)) == int(flower_id):
            item["selected_color"] = color
            break
    st.session_state.generated_image = None


def add_flower(
    flower: Dict[str, Any],
    notify: bool = True,
    preferred_color: str = "任意",
) -> bool:
    if int(flower["id"]) in selected_ids():
        return False
    selected_flower = dict(flower)
    selected_flower["selected_color"] = _default_flower_color(
        selected_flower, preferred_color
    )
    st.session_state.selected_flowers.append(selected_flower)
    flower_id = int(flower["id"])
    st.session_state.flower_quantities[flower_id] = default_quantity(flower, st.session_state.size)
    st.session_state.custom_roles[flower_id] = (
        "主花" if flower.get("category") == "主花" else "配花"
    )
    if notify:
        st.toast(f"已加入花篮：{flower['name']}", icon="🌸")
    return True


def remove_flower(flower_id: int, notify: bool = True) -> None:
    st.session_state.selected_flowers = [
        flower for flower in st.session_state.selected_flowers if int(flower["id"]) != int(flower_id)
    ]
    st.session_state.flower_quantities.pop(int(flower_id), None)
    st.session_state.flower_quantities.pop(str(flower_id), None)
    st.session_state.custom_roles.pop(int(flower_id), None)
    for key in (f"qty_{flower_id}", f"role_{flower_id}", f"flower_color_{flower_id}"):
        st.session_state.pop(key, None)
    if notify:
        st.toast("已从花篮移除", icon="🍃")


def current_packaging() -> Dict[str, Any]:
    return PACKAGING_OPTIONS.get(st.session_state.packaging, PACKAGING_OPTIONS["misty"])


def current_shape() -> Dict[str, Any]:
    return SHAPE_OPTIONS.get(st.session_state.shape, SHAPE_OPTIONS["round"])


def current_price() -> Dict[str, Any]:
    return price_breakdown(
        st.session_state.selected_flowers,
        st.session_state.flower_quantities,
        st.session_state.size,
        st.session_state.packaging,
        st.session_state.shape,
    )


def prefs_for_recommendation() -> Dict[str, Any]:
    return {
        "target": st.session_state.target,
        "occasion": st.session_state.occasion,
        "color": st.session_state.color,
        "style": st.session_state.style,
        "season": st.session_state.season_filter,
    }


def apply_recommendation_to_basket(result: Dict[str, Any]) -> None:
    new_ids = {int(flower["id"]) for flower in result.get("selected", [])}
    for old_flower in list(st.session_state.selected_flowers):
        old_id = int(old_flower["id"])
        if old_id not in new_ids:
            st.session_state.pop(f"qty_{old_id}", None)
            st.session_state.pop(f"role_{old_id}", None)
        st.session_state.pop(f"flower_color_{old_id}", None)
    st.session_state.selected_flowers = []
    for flower in result.get("selected", []):
        selected_flower = dict(flower)
        selected_flower["selected_color"] = _default_flower_color(
            selected_flower, st.session_state.color
        )
        st.session_state.selected_flowers.append(selected_flower)
    quantities: Dict[int, int] = {}
    roles: Dict[int, str] = {}
    for flower in st.session_state.selected_flowers:
        flower_id = int(flower["id"])
        quantities[flower_id] = int(result.get("quantities", {}).get(flower_id, default_quantity(flower, st.session_state.size)))
        roles[flower_id] = "主花" if flower.get("category") == "主花" else "配花"
    st.session_state.flower_quantities = quantities
    st.session_state.custom_roles = roles
    for flower in st.session_state.selected_flowers:
        flower_id = int(flower["id"])
        st.session_state.pop(f"flower_color_{flower_id}", None)
    st.session_state.generated_image = None


def reset_basket() -> None:
    for flower in list(st.session_state.selected_flowers):
        flower_id = int(flower["id"])
        st.session_state.pop(f"qty_{flower_id}", None)
        st.session_state.pop(f"role_{flower_id}", None)
        st.session_state.pop(f"flower_color_{flower_id}", None)
    st.session_state.selected_flowers = []
    st.session_state.flower_quantities = {}
    st.session_state.custom_roles = {}
    st.session_state.generated_image = None


def image_quota() -> Dict[str, Any]:
    today = now_cn().date().isoformat()
    counts = st.session_state.image_counts
    used = int(counts.get(today, 0))
    remaining = max(0, DAILY_IMAGE_LIMIT - used)
    elapsed = time.time() - float(st.session_state.last_image_time or 0)
    cooldown = max(0, int(IMAGE_COOLDOWN_SECONDS - elapsed))
    return {
        "used": used,
        "limit": DAILY_IMAGE_LIMIT,
        "remaining": remaining,
        "cooldown": cooldown,
    }


def record_image_generation() -> None:
    today = now_cn().date().isoformat()
    counts = dict(st.session_state.image_counts)
    counts[today] = int(counts.get(today, 0)) + 1
    st.session_state.image_counts = counts
    st.session_state.last_image_time = time.time()


def apply_pending_preferences() -> None:
    pending = st.session_state.get("pending_prefs")
    if not pending:
        return
    allowed = {"target", "occasion", "color", "style", "budget", "size"}
    for key, value in pending.items():
        if key in allowed:
            st.session_state[key] = value
    st.session_state.pending_prefs = None
    st.session_state.auto_recommend = True


apply_pending_preferences()


# ============================================================
# 模型调用
# ============================================================
def _friendly_api_error(status: int, body: str = "") -> str:
    def safe_detail(raw: str, limit: int = 320) -> str:
        detail = raw or ""
        try:
            parsed = json.loads(detail)
            error = parsed.get("error", parsed) if isinstance(parsed, dict) else {}
            if isinstance(error, dict):
                parts = [
                    str(error.get("message") or "").strip(),
                    str(error.get("code") or "").strip(),
                ]
                request_id = (
                    error.get("request_id") or error.get("requestId")
                    or parsed.get("request_id") or parsed.get("requestId")
                )
                if request_id:
                    parts.append(f"Request ID: {request_id}")
                detail = "；".join(part for part in parts if part) or detail
        except (TypeError, ValueError):
            pass
        detail = re.sub(r"(?i)(Bearer\s+)[^\s,;\"']+", r"\1[已隐藏]", detail)
        detail = re.sub(
            r"(?i)((?:api[_-]?key|authorization)[\"']?\s*[:=]\s*[\"']?)[^\s,;\"'}]+",
            r"\1[已隐藏]",
            detail,
        )
        return re.sub(r"\s+", " ", detail).strip()[:limit]

    if status == 401:
        return "API 认证失败，请检查密钥是否正确。"
    if status == 403:
        return "当前账号没有该模型的调用权限。"
    if status == 404:
        detail = safe_detail(body)
        message = "接口不存在，请检查 API Base URL 与模型名。"
        return f"{message} 服务端返回：{detail}" if detail else message
    if status == 429:
        return "调用频率或额度已用尽，请稍后再试。"
    if status >= 500:
        detail = safe_detail(body)
        message = f"模型服务暂时繁忙（HTTP {status}），请稍后重试。"
        return f"{message} 服务端返回：{detail}" if detail else message
    detail = safe_detail(body, limit=160)
    return f"API 返回 HTTP {status}。{detail}"


def call_llm(
    messages: Sequence[Dict[str, Any]],
    temperature: float = 0.6,
    max_tokens: int = 800,
    timeout: int = 45,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    use_cache: bool = True,
    max_attempts: int = 3,
) -> Tuple[Optional[str], Optional[str]]:
    """调用 OpenAI 兼容的 Chat Completions 接口。"""
    model = model or LLM_MODEL
    base_url = (base_url or LLM_BASE).rstrip("/")
    api_key = api_key or LLM_KEY
    if not api_key:
        return None, "未配置大模型 API，已自动使用本地搭配引擎。"

    cache_key = ""
    if use_cache:
        raw = json.dumps(
            {
                "base": base_url,
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_key = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        cached = st.session_state.llm_cache.get(cache_key)
        if cached:
            return str(cached.get("content", "")), None

    payload = {
        "model": model,
        "messages": list(messages),
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_error = "模型调用失败。"
    attempts = max(1, int(max_attempts))
    for attempt in range(attempts):
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                last_error = _friendly_api_error(response.status_code, response.text)
                time.sleep(1.1 * (attempt + 1))
                continue
            if response.status_code != 200:
                return None, _friendly_api_error(response.status_code, response.text)
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return None, "模型没有返回候选结果。"
            message = choices[0].get("message") or {}
            content = message.get("content", "")
            if isinstance(content, list):
                content = "".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict)
                )
            content = str(content or "").strip()
            if not content:
                return None, "模型返回了空内容。"
            if use_cache and cache_key:
                st.session_state.llm_cache[cache_key] = {
                    "content": content,
                    "time": time.time(),
                }
                if len(st.session_state.llm_cache) > 80:
                    oldest = sorted(
                        st.session_state.llm_cache.items(),
                        key=lambda item: float(item[1].get("time", 0)),
                    )[:20]
                    for key, _ in oldest:
                        st.session_state.llm_cache.pop(key, None)
            return content, None
        except requests.exceptions.Timeout:
            last_error = f"模型响应超时（{timeout} 秒），建议稍后重试或换一个更快的模型。"
        except requests.exceptions.ConnectionError:
            last_error = "无法连接模型服务，请检查网络与 API 地址。"
        except Exception as exc:
            last_error = f"模型调用异常：{type(exc).__name__}"
        if attempt < attempts - 1:
            time.sleep(0.8 * (attempt + 1))
    return None, last_error


def _fetch_image_bytes(url: str) -> Optional[bytes]:
    try:
        response = requests.get(url, timeout=25)
        if response.status_code == 200 and len(response.content) > 1000:
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type or response.content[:4] in {
                b"\x89PNG",
                b"\xff\xd8\xff\xe0",
                b"GIF8",
                b"RIFF",
            }:
                return response.content
    except Exception:
        return None
    return None


def generate_bouquet_image(prompt: str, size: str = "1024x1024") -> Dict[str, Any]:
    if not IMAGE_KEY:
        return {
            "success": False,
            "error_type": "未配置",
            "message": "还没有配置生图 API。你仍可使用结构示意图或复制提示词到其他绘画工具。",
        }
    payload: Dict[str, Any] = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if (
        not IMAGE_MODEL.startswith("gpt-image")
        and _setting("IMAGE_SEND_RESPONSE_FORMAT", "true").lower() not in {"0", "false", "no"}
    ):
        payload["response_format"] = "url"
    if _setting("IMAGE_SUPPORTS_NEGATIVE", "false").lower() in {"1", "true", "yes"}:
        payload["negative_prompt"] = build_negative_prompt()
    headers = {
        "Authorization": f"Bearer {IMAGE_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            f"{IMAGE_BASE}/images/generations",
            headers=headers,
            json=payload,
            timeout=120,
        )
        if response.status_code != 200:
            return {
                "success": False,
                "error_type": "接口错误",
                "message": _friendly_api_error(response.status_code, response.text),
            }
        data = response.json()
        items = data.get("data") or []
        if not items:
            return {"success": False, "error_type": "响应异常", "message": "接口没有返回图片。"}
        item = items[0]
        image_url = item.get("url") or item.get("image_url")
        image_bytes: Optional[bytes] = None
        if item.get("b64_json"):
            try:
                image_bytes = base64.b64decode(item["b64_json"])
            except Exception:
                image_bytes = None
        if not image_bytes and image_url:
            image_bytes = _fetch_image_bytes(str(image_url))
        if not image_url and image_bytes:
            image_url = ""
        if not image_url and not image_bytes:
            return {"success": False, "error_type": "响应异常", "message": "未找到可用的图片数据。"}
        return {
            "success": True,
            "url": image_url,
            "bytes": image_bytes,
            "revised_prompt": item.get("revised_prompt", ""),
            "model": IMAGE_MODEL,
        }
    except requests.exceptions.Timeout:
        return {"success": False, "error_type": "超时", "message": "生图超时，模型可能正忙，请稍后重试。"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error_type": "连接失败", "message": "无法连接生图服务，请检查网络。"}
    except Exception as exc:
        return {
            "success": False,
            "error_type": "异常",
            "message": f"生图异常：{type(exc).__name__}",
        }


def vision_consistency_check(
    image_url: str,
    image_bytes: Optional[bytes],
    manifest_text: str,
) -> Optional[Dict[str, Any]]:
    if not VISION_MODEL:
        return None
    if image_url:
        image_ref = image_url
    elif image_bytes:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        image_ref = f"data:image/png;base64,{encoded}"
    else:
        image_ref = ""
    if not image_ref:
        return None
    prompt = (
        "你是花艺质检员。请检查这张花束图是否与下面的配方一致。\n"
        f"配方：{manifest_text}\n"
        "重点检查：是否出现配方之外的花材、是否明显缺少配方中的花材、颜色是否明显不符。\n"
        "只输出 JSON，不要 markdown："
        '{"match_score":0-100,"missing":["缺少的花材"],"extra":["多出的花材"],'
        '"comment":"一句中文说明"}'
    )
    content, error = call_llm(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_ref}},
                ],
            }
        ],
        temperature=0.0,
        max_tokens=350,
        timeout=50,
        model=VISION_MODEL,
        base_url=VISION_BASE,
        api_key=VISION_KEY,
        use_cache=False,
    )
    if error:
        return {"error": error}
    parsed = parse_json_object(content)
    return parsed if parsed else {"error": "视觉模型没有返回可解析的 JSON。"}


# ============================================================
# 推荐与联网
# ============================================================
def _groups_from_llm(
    parsed: Dict[str, Any],
    shortlist: Sequence[Dict[str, Any]],
    local_result: Dict[str, Any],
    size_key: str,
) -> Dict[str, List[Dict[str, Any]]]:
    config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
    quotas = {
        "main": int(config["main_types"]),
        "filler": int(config["filler_types"]),
        "foliage": int(config["foliage_types"]),
        "fruit": int(config["fruit_types"]),
    }
    category_for = {
        "main": "主花",
        "filler": "配花",
        "foliage": "叶材",
        "fruit": "果材",
    }
    by_id = {int(flower["id"]): flower for flower in shortlist}
    groups: Dict[str, List[Dict[str, Any]]] = {key: [] for key in quotas}
    used: set = set()
    for key, category in category_for.items():
        raw_ids = parsed.get(f"{key}_ids") or []
        if not isinstance(raw_ids, list):
            continue
        for raw_id in raw_ids:
            try:
                flower_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            flower = by_id.get(flower_id)
            if not flower or flower.get("category") != category:
                continue
            if flower_id in used:
                continue
            if len(groups[key]) >= quotas[key]:
                break
            groups[key].append(flower)
            used.add(flower_id)

    local_key_map = {
        "main": "main",
        "filler": "filler",
        "foliage": "foliage",
        "fruit": "fruit",
    }
    for key, local_key in local_key_map.items():
        for flower in local_result.get(local_key, []):
            flower_id = int(flower["id"])
            if len(groups[key]) >= quotas[key]:
                break
            if flower_id in used:
                continue
            groups[key].append(flower)
            used.add(flower_id)
    return groups


def run_recommendation(
    free_text: str = "",
    seed: int = 0,
    announce: bool = True,
    use_web: bool = False,
) -> Dict[str, Any]:
    prefs = prefs_for_recommendation()
    parsed_free = parse_free_text_local(free_text)
    for key in ("target", "occasion", "color", "style"):
        if parsed_free.get(key):
            prefs[key] = parsed_free[key]
    budget = int(st.session_state.budget)
    if parsed_free.get("budget"):
        try:
            budget = min(budget, int(parsed_free["budget"]))
        except (TypeError, ValueError):
            pass
    size_key = st.session_state.size
    packaging_key = st.session_state.packaging
    shape_key = st.session_state.shape
    season_pref = str(prefs.get("season", "当季"))
    season = current_season() if season_pref in {"当季", ""} else ("不限" if season_pref == "不限" else season_pref)
    web_context = ""
    if use_web and LLM_KEY:
        try:
            web_items = web_lookup(
                f"{prefs.get('occasion', '')} {prefs.get('target', '')} 花束 花语"
            )
            if web_items:
                web_context = "\n".join(
                    f"- {item.get('title', '')}：{item.get('extract', '')}"
                    for item in web_items[:3]
                )
        except Exception:
            web_context = ""

    if not FLOWERS:
        st.error("花材知识库为空。请检查 assets_knowledge/knowledge_base/flower_knowledge.json。")
        return {
            "success": False,
            "title": "暂时无法搭配",
            "rationale": "花材知识库没有加载成功。",
            "main": [],
            "filler": [],
            "foliage": [],
            "fruit": [],
            "selected": [],
            "quantities": {},
            "prefs": prefs,
            "source": "local",
        }

    spinner_text = "正在联网补充花语并挑选花材…" if use_web else "花艺师正在挑选花材、核算预算…"
    with st.spinner(spinner_text):
        local_result = recommend_local(
            FLOWERS,
            prefs,
            size_key,
            budget,
            packaging_key,
            shape_key,
            seed,
        )
        result = local_result
        llm_error = None

        if LLM_KEY and FLOWERS:
            config = SIZE_CONFIG.get(size_key, SIZE_CONFIG["M"])
            shortlist = shortlist_for_llm(
                FLOWERS, prefs, season, LLM_SHORTLIST_PER_CATEGORY
            )
            candidate_lines = []
            for flower in shortlist:
                candidate_lines.append(
                    "|".join(
                        [
                            str(flower["id"]),
                            str(flower.get("name", "")),
                            str(flower.get("english_name", "")),
                            str(flower.get("category", "")),
                            str(flower.get("color", "")),
                            str(flower.get("language", "")),
                            "、".join(str(value) for value in flower.get("season_tags", [])),
                            f"¥{float(flower.get('unit_price', 5)):.0f}",
                        ]
                    )
                )
            prompt = f"""你是资深花艺设计师，擅长做有审美、能落地的商业花束。

用户需求：
- 送给：{prefs.get('target', '')}
- 场合：{prefs.get('occasion', '')}
- 颜色：{prefs.get('color', '任意')}
- 风格：{prefs.get('style', '任意')}
- 尺寸：{config['label']}（{config['dims']}）
- 预算上限：¥{budget}
- 季节：{season}
- 用户自由描述：{free_text or '无'}
- 联网参考（仅作灵感，不得改变候选 id 白名单）：{web_context or '无'}

候选花材（id|中文名|英文名|类别|颜色|花语|季节|单支价）：
{chr(10).join(candidate_lines)}

硬性规则：
1. 只能使用候选列表里的 id，不要编造花材。
2. 主花 {config['main_types']} 种、配花 {config['filler_types']} 种、叶材 {config['foliage_types']} 种、果材 {config['fruit_types']} 种；S 码可以少一种配花。
3. 花材颜色、花语、场合要协调；喜庆场合避开容易引起误会的白色菊类；不要所有花都同一个颜色。
4. 花束要有主次：主花撑焦点，配花做层次，叶材收轮廓，果材点睛。
5. rationale 必须提到你实际选中的花材名称，40–70 个中文字，语气自然，不要夸张。
6. 不要输出思考过程，只输出紧凑 JSON。

只输出 JSON，不要 markdown：
{{"title":"一句花束名","rationale":"推荐语","main_ids":[1,2],"filler_ids":[3,4],"foliage_ids":[5],"fruit_ids":[6]}}"""
            content, llm_error = call_llm(
                [
                    {"role": "system", "content": "你只输出合法 JSON，不添加任何解释。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.45,
                max_tokens=LLM_RECOMMEND_MAX_TOKENS,
                timeout=LLM_RECOMMEND_TIMEOUT,
                max_attempts=LLM_RECOMMEND_ATTEMPTS,
            )
            parsed = parse_json_object(content)
            if parsed:
                groups = _groups_from_llm(parsed, shortlist, local_result, size_key)
                if groups["main"]:
                    result = compose_recommendation(
                        groups["main"],
                        groups["filler"],
                        groups["foliage"],
                        groups["fruit"],
                        prefs,
                        size_key,
                        budget,
                        packaging_key,
                        shape_key,
                        title=str(parsed.get("title") or "").strip() or None,
                        rationale=str(parsed.get("rationale") or "").strip() or None,
                        source="llm",
                        seed=seed,
                    )
                else:
                    result = local_result
                    llm_error = "模型没有给出可用的主花组合，已回退到本地搭配。"
            elif llm_error is None:
                llm_error = "模型返回内容无法解析，已回退到本地搭配。"

        result["llm_error"] = llm_error
        result["free_text"] = free_text
        result["web_used"] = bool(web_context)
        st.session_state.recommend_result = result
        if result.get("selected"):
            apply_recommendation_to_basket(result)
        if announce:
            st.toast("搭配已生成，并已放入花篮", icon="💐")
    return result


def web_lookup(query: str) -> List[Dict[str, str]]:
    query = query.strip()
    if not query:
        return []
    cached = st.session_state.web_cache.get(query)
    if cached is not None:
        return list(cached)
    results: List[Dict[str, str]] = []
    headers = {"User-Agent": "AI-Bouquet-Studio/1.0 (educational demo)"}
    try:
        search_response = requests.get(
            "https://zh.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "utf8": 1,
                "srlimit": 2,
            },
            headers=headers,
            timeout=5,
        )
        if search_response.status_code == 200:
            search_data = search_response.json()
            for item in (search_data.get("query", {}).get("search") or [])[:2]:
                title = str(item.get("title", ""))
                if not title:
                    continue
                summary_response = requests.get(
                    "https://zh.wikipedia.org/api/rest_v1/page/summary/"
                    + urllib.parse.quote(title, safe=""),
                    headers=headers,
                    timeout=5,
                )
                if summary_response.status_code == 200:
                    summary = summary_response.json()
                    extract = str(summary.get("extract", "")).strip()
                    if extract:
                        results.append(
                            {
                                "source": "维基百科",
                                "title": title,
                                "extract": extract[:260],
                                "url": str(summary.get("content_urls", {}).get("desktop", {}).get("page", "")),
                            }
                        )
    except Exception:
        results = []
    if not results:
        try:
            ddg = requests.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": f"{query} 花 花语",
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
                headers=headers,
                timeout=5,
            )
            if ddg.status_code == 200:
                data = ddg.json()
                abstract = str(data.get("AbstractText", "")).strip()
                if abstract:
                    results.append(
                        {
                            "source": "DuckDuckGo",
                            "title": str(data.get("Heading", query)),
                            "extract": abstract[:260],
                            "url": str(data.get("AbstractURL", "")),
                        }
                    )
                for topic in (data.get("RelatedTopics") or [])[:2]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append(
                            {
                                "source": "DuckDuckGo",
                                "title": str(topic.get("Text", ""))[:40],
                                "extract": str(topic.get("Text", ""))[:260],
                                "url": str(topic.get("FirstURL", "")),
                            }
                        )
        except Exception:
            results = []
    st.session_state.web_cache[query] = results
    return results


# ============================================================
# 展示组件
# ============================================================
def section_header(kicker: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="section-title">{safe(title)}</div>'
        + (f'<div class="section-sub">{safe(subtitle)}</div>' if subtitle else ""),
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False, max_entries=256)
def _flower_thumbnail_data_uri(path: str) -> str:
    """Resize source photos before embedding so the catalog stays lightweight."""
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            resampling = getattr(Image, "Resampling", Image).LANCZOS
            image.thumbnail((720, 720), resampling)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=78, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return ""


def flower_image_data_uri(
    flower: Dict[str, Any], preferred_color: str = "任意"
) -> str:
    """Choose a matching id/color photo, then fall back to another available variant."""
    try:
        flower_id = int(flower["id"])
    except (KeyError, TypeError, ValueError):
        return ""

    variants = _flower_image_index(FLOWER_IMAGE_DIR).get(flower_id, {})
    if not variants:
        return ""

    preferred_color = str(flower.get("selected_color") or preferred_color or "任意")
    desired_roots = color_roots(preferred_color) if preferred_color not in {"", "任意"} else []
    desired_codes = [IMAGE_COLOR_CODES[root] for root in desired_roots if root in IMAGE_COLOR_CODES]
    flower_roots = color_roots(str(flower.get("color", "")))
    flower_codes = [IMAGE_COLOR_CODES[root] for root in flower_roots if root in IMAGE_COLOR_CODES]

    ordered_codes = desired_codes + flower_codes + sorted(variants)
    for code in ordered_codes:
        if code in variants:
            return _flower_thumbnail_data_uri(variants[code])
    return ""


def flower_card_html(
    flower: Dict[str, Any],
    selected: bool = False,
    image_uri: str = "",
) -> str:
    palette = flower.get("palette") or ["#F2A7BC", "#E9C7D1"]
    first = palette[0]
    second = palette[1] if len(palette) > 1 else "#E9C7D1"
    category = str(flower.get("category", "配花"))
    meta = CATEGORY_META.get(category, CATEGORY_META["配花"])
    language = str(flower.get("language", ""))
    if len(language) > 24:
        language = language[:24] + "…"
    season_tags = [str(value) for value in flower.get("season_tags", []) if value != "全年"]
    season_label = season_tags[0] if season_tags else "全年供应"
    image_html = (
        f'<img class="flower-photo" src="{image_uri}" alt="{safe(flower.get("name", "花材"))}花材照片" />'
        if image_uri
        else f'<div class="flower-orb" style="background: linear-gradient(135deg, {first}, {second});">{flower_emoji(flower)}</div>'
    )
    return f"""
    <div class="flower-card {'selected' if selected else ''}">
        {image_html}
        <div class="fc-name">{safe(flower.get('name', ''))}</div>
        <div class="fc-lang">「{safe(language)}」</div>
        <div class="fc-meta">
            <span class="badge">{safe(meta['emoji'])} {safe(category)}</span>
            <span class="price">¥{float(flower.get('unit_price', 0)):.0f}/支</span>
        </div>
        <div class="fc-tags"><span class="fc-tag">{safe(season_label)}</span></div>
    </div>
    """


def render_flower_grid(
    flowers: Sequence[Dict[str, Any]],
    key_prefix: str,
    columns: int = 3,
    preferred_color: str = "任意",
) -> None:
    if not flowers:
        return
    columns = max(1, min(columns, 4))
    for start in range(0, len(flowers), columns):
        row = list(flowers[start : start + columns])
        cols = st.columns(columns, gap="medium")
        for col, flower in zip(cols, row):
            flower_id = int(flower["id"])
            is_selected = flower_id in selected_ids()
            with col:
                image_uri = flower_image_data_uri(flower, preferred_color)
                st.markdown(
                    flower_card_html(
                        flower,
                        selected=is_selected,
                        image_uri=image_uri,
                    ),
                    unsafe_allow_html=True,
                )
                label = "✓ 已加入 · 移除" if is_selected else "＋ 加入花篮"
                if st.button(
                    label,
                    key=f"{key_prefix}_{flower_id}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                ):
                    if is_selected:
                        remove_flower(flower_id)
                    else:
                        add_flower(flower, preferred_color=preferred_color)
                    st.rerun()


def render_empty_state(emoji: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""<div class="empty-state">
            <div class="empty-emoji">{safe(emoji)}</div>
            <div class="empty-title">{safe(title)}</div>
            <div>{safe(subtitle)}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def go_to(page: str) -> None:
    st.session_state.pending_nav = page
    st.rerun()


def process_pending_actions() -> None:
    """在控件实例化之前处理跨页面的状态修改，避免 Streamlit 的 widget key 限制。"""
    pending_nav = st.session_state.pop("pending_nav", None)
    if pending_nav in {"AI 灵感", "当季花材库", "花束工作台"}:
        st.session_state.nav = pending_nav
    widgets = st.session_state.pop("pending_widgets", None)
    if isinstance(widgets, dict):
        for key, value in widgets.items():
            st.session_state[key] = value
    remove_id = st.session_state.pop("pending_remove_id", None)
    if remove_id is not None:
        remove_flower(int(remove_id), notify=False)
    if st.session_state.pop("pending_reset", False):
        reset_basket()
    pending_quantities = st.session_state.pop("pending_quantities", None)
    if isinstance(pending_quantities, dict):
        active_ids = {int(flower["id"]) for flower in st.session_state.selected_flowers}
        for flower_id, quantity in pending_quantities.items():
            try:
                numeric_id = int(flower_id)
                numeric_quantity = int(quantity)
            except (TypeError, ValueError):
                continue
            if numeric_id not in active_ids:
                continue
            st.session_state.flower_quantities[numeric_id] = numeric_quantity


def render_hero() -> None:
    active = st.session_state.nav
    step_one = "active" if active != "花束工作台" else ""
    step_two = "active" if active == "花束工作台" and not st.session_state.generated_image else ""
    step_three = "active" if st.session_state.generated_image else ""
    st.markdown(
        f"""
        <div class="hero">
            <div>
                <div class="hero-kicker">✦ 信心花舍 · AI 花艺工作室</div>
                <div class="hero-title">把心意，<span class="accent">扎成一束花</span>。</div>
                <p class="hero-sub">用一份花束，把心意好好送达。</p>
                <div class="hero-badges">
                    <span class="hero-badge">🌷 {len(FLOWERS)} 种当季花材</span>
                    <span class="hero-badge">✦ AI 灵感 · 自由搭配</span>
                </div>
            </div>
            <div class="hero-art">
                <div class="halo"></div>
                <span class="dot" style="width:10px;height:10px;left:20%;top:22%;"></span>
                <span class="dot" style="width:6px;height:6px;right:18%;top:18%;"></span>
                <span class="dot" style="width:7px;height:7px;right:26%;bottom:18%;"></span>
                <span class="emoji">💐</span>
            </div>
        </div>
        <div class="step-strip">
            <span class="step-pill {step_one}">01 · 选花材</span>
            <span class="step-pill {step_two}">02 · 定包装</span>
            <span class="step-pill {step_three}">03 · 出效果图</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="brand-lockup">
                <div class="brand-logo">
                    <img src="{brand_logo_data_uri()}" alt="信心花舍几何花瓣 Logo" />
                </div>
                <div class="brand-copy">
                    <div class="brand-cn">信心花舍</div>
                    <div class="brand-en">XINXIN FLOWER ATELIER</div>
                </div>
            </div>
            <div class="brand-tagline">让每一份心意，都有信心的表达。</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)

        st.markdown("**这份花送给谁？**")
        st.selectbox("送给谁", TARGETS, key="target", label_visibility="collapsed")
        st.selectbox("什么场合", OCCASIONS, key="occasion", label_visibility="collapsed")

        st.markdown("**想要什么感觉？**")
        st.selectbox("偏好颜色", COLOR_CHOICES, key="color", label_visibility="collapsed")
        st.selectbox("偏好风格", STYLE_CHOICES, key="style", label_visibility="collapsed")
        st.slider(
            "预算上限",
            min_value=80,
            max_value=800,
            step=20,
            key="budget",
            format="¥%d",
            help="推荐引擎会在预算内调整花材种类与支数。",
        )
        st.selectbox(
            "花束尺寸",
            list(SIZE_CONFIG.keys()),
            format_func=lambda key: f"{SIZE_CONFIG[key]['label']} · {SIZE_CONFIG[key]['dims']}",
            key="size",
        )
        st.selectbox("季节偏好", SEASON_CHOICES, key="season_filter")
        with st.expander("⚙️ 模型与额度", expanded=False):
            text_status = (
                f"{LLM_PROVIDER_LABEL} · {LLM_MODEL}"
                if LLM_KEY
                else "本地搭配（未检测到文字 Key）"
            )
            image_status = (
                f"{IMAGE_PROVIDER_LABEL} · {IMAGE_MODEL}"
                if IMAGE_KEY
                else "未配置（AI 效果图按钮会禁用）"
            )
            st.caption(f"文字：{text_status}")
            st.caption(f"生图：{image_status}")
            if ARK_KEY_PRESENT and ARK_MODEL_MISSING and ARK_IMAGE_MODEL_MISSING:
                st.caption("提示：检测到 ARK_API_KEY，但 ARK_MODEL / ARK_IMAGE_MODEL 都未填写，Ark 不会生效。")
            elif ARK_KEY_PRESENT and ARK_MODEL_MISSING and LLM_PROVIDER == "ark":
                st.caption("提示：Ark 文字模型缺少 ARK_MODEL；如需豆包文字，请补上模型/接入点 ID。")
            if not LLM_KEY:
                st.caption("提示：未检测到可用文字 Key 时，AI 推荐会使用本地搭配引擎。")
            if st.button(
                "测试文字模型连接",
                key="test_llm_connection",
                use_container_width=True,
                disabled=not LLM_KEY,
                help="只发送一句很短的话，验证 Key、Base URL 和模型名是否可用。",
            ):
                with st.spinner("正在测试文字模型连接…"):
                    _test_content, test_error = call_llm(
                        [{"role": "user", "content": "只回复 OK"}],
                        temperature=0.0,
                        max_tokens=8,
                    )
                if test_error:
                    st.error(f"连接失败：{test_error}")
                else:
                    st.success(f"连接正常：{LLM_PROVIDER_LABEL} · {LLM_MODEL}")
            st.caption("生图测试会消耗额度，建议在工作台生成一张图验证。")
            quota = image_quota()
            st.caption(f"今日生图：{quota['used']}/{quota['limit']} 次")
            if quota["cooldown"]:
                st.caption(f"生图冷却：{quota['cooldown']} 秒")
            if VISION_MODEL and VISION_KEY:
                st.caption(f"视觉质检：{VISION_MODEL}")

        st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
        if st.button("✨ AI 一键搭配", type="primary", use_container_width=True):
            result = run_recommendation(
                "",
                int(time.time()),
                use_web=bool(st.session_state.get("ai_web_enabled", False)),
            )
            st.session_state.pending_nav = "AI 灵感"
            st.rerun()

        if st.session_state.selected_flowers:
            price = current_price()
            stems = sum(
                qty_for(st.session_state.flower_quantities, int(flower["id"]))
                for flower in st.session_state.selected_flowers
            )
            st.markdown(
                f"""<div class="summary-card">
                    <div class="summary-label">CURRENT BASKET</div>
                    <div class="summary-value">{money(price['total_price'])}</div>
                    <div class="small-note">{len(st.session_state.selected_flowers)} 种花材 · {stems} 支 · {SIZE_CONFIG[st.session_state.size]['label']}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            if c1.button("去工作台", use_container_width=True):
                go_to("花束工作台")
            if c2.button("清空", use_container_width=True):
                reset_basket()
                st.rerun()
        else:
            st.caption("花篮还是空的。先用 AI 搭配，或去当季花材库挑几枝。")
            if st.button("🌿 逛当季花材库", use_container_width=True):
                go_to("当季花材库")

        if st.session_state.orders:
            st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
            st.markdown("**最近订单**")
            for index, order in enumerate(st.session_state.orders[:2]):
                order_price = order.get("price") if isinstance(order.get("price"), dict) else {}
                order_id = str(order.get("order_id", ""))
                if st.button(
                    f"🧾 {order_id[-6:]} · {money(order_price.get('total_price', 0))}",
                    key=f"load_order_{index}",
                    use_container_width=True,
                ):
                    load_order_into_workbench(order)
                    st.rerun()

        st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)


def load_order_into_workbench(order: Dict[str, Any]) -> None:
    items = order.get("items") or []
    by_id = {int(flower["id"]): flower for flower in FLOWERS}
    for old_flower in list(st.session_state.selected_flowers):
        old_id = int(old_flower["id"])
        st.session_state.pop(f"qty_{old_id}", None)
        st.session_state.pop(f"role_{old_id}", None)
        st.session_state.pop(f"flower_color_{old_id}", None)
    selected: List[Dict[str, Any]] = []
    quantities: Dict[int, int] = {}
    roles: Dict[int, str] = {}
    for item in items:
        flower = by_id.get(int(item.get("id", 0)))
        if not flower:
            continue
        flower_id = int(flower["id"])
        selected_flower = dict(flower)
        saved_color = str(item.get("selected_color", ""))
        allowed_colors = flower_color_options(selected_flower)
        selected_flower["selected_color"] = (
            saved_color if saved_color in allowed_colors else _default_flower_color(selected_flower)
        )
        selected.append(selected_flower)
        quantities[flower_id] = int(item.get("quantity", 1))
        roles[flower_id] = "主花" if item.get("category") == "主花" else "配花"
    st.session_state.selected_flowers = selected
    st.session_state.flower_quantities = quantities
    st.session_state.custom_roles = roles
    order_size = order.get("size") if order.get("size") in SIZE_CONFIG else st.session_state.size
    order_shape = order.get("shape") if order.get("shape") in SHAPE_OPTIONS else "round"
    order_packaging = order.get("packaging") if order.get("packaging") in PACKAGING_OPTIONS else "misty"
    order_ribbon = order.get("ribbon") if order.get("ribbon") in RIBBON_OPTIONS else "champagne"
    st.session_state.pending_widgets = {
        "size": order_size,
        "shape": order_shape,
        "packaging": order_packaging,
        "ribbon": order_ribbon,
        "custom_message": order.get("message", ""),
        "order_message": order.get("message", ""),
    }
    st.session_state.pending_quantities = quantities
    st.session_state.generated_image = None
    st.session_state.pending_nav = "花束工作台"


# ============================================================
# 页面：AI 灵感
# ============================================================
GALLERY = [
    {
        "emoji": "🌹",
        "name": "玫瑰情书",
        "sub": "给恋人的纪念日，红与香槟的经典浪漫",
        "tags": ["恋人", "纪念日", "红色", "浪漫"],
        "prefs": {"target": "恋人", "occasion": "纪念日", "color": "红色", "style": "浪漫", "budget": 360},
        "gradient": "linear-gradient(145deg, #FBE9ED, #F3D6DF)",
    },
    {
        "emoji": "🌻",
        "name": "向日葵毕业礼",
        "sub": "把阳光包进花里，送给即将出发的人",
        "tags": ["朋友", "毕业", "黄色", "阳光活力"],
        "prefs": {"target": "朋友", "occasion": "毕业", "color": "黄色", "style": "阳光活力", "budget": 280},
        "gradient": "linear-gradient(145deg, #FFF4D8, #F8E3B8)",
    },
    {
        "emoji": "🤍",
        "name": "奶油花园",
        "sub": "白绿与奶油色，温柔、干净、不挑场合",
        "tags": ["家人", "生日", "白色", "温柔治愈"],
        "prefs": {"target": "家人", "occasion": "生日", "color": "白色", "style": "温柔治愈", "budget": 320},
        "gradient": "linear-gradient(145deg, #FBF7EF, #EEE9DD)",
    },
    {
        "emoji": "💜",
        "name": "紫雾晚宴",
        "sub": "紫调与果材点缀，适合隆重的表白时刻",
        "tags": ["恋人", "表白", "紫色", "华丽大气"],
        "prefs": {"target": "恋人", "occasion": "表白", "color": "紫色", "style": "华丽大气", "budget": 420},
        "gradient": "linear-gradient(145deg, #F0E8F8, #DED2EE)",
    },
]


def render_gallery() -> None:
    cols = st.columns(4, gap="medium")
    for index, item in enumerate(GALLERY):
        with cols[index]:
            st.markdown(
                f"""<div style="
                    min-height: 190px;
                    padding: 18px 16px;
                    border-radius: 22px;
                    background: {item['gradient']};
                    border: 1px solid rgba(111,79,119,0.10);
                    box-shadow: 0 10px 24px rgba(96,64,82,0.06);
                    margin-bottom: 8px;
                ">
                    <div style="font-size: 2.1rem; margin-bottom: 8px;">{item['emoji']}</div>
                    <div style="font-weight: 800; font-size: 1.02rem; color: #3B303D; margin-bottom: 5px;">{safe(item['name'])}</div>
                    <div style="font-size: 0.78rem; color: #6F5F6D; line-height: 1.6; min-height: 52px;">{safe(item['sub'])}</div>
                    <div style="display:flex; flex-wrap:wrap; gap:4px; margin-top: 8px;">
                        {''.join(f'<span class="fc-tag">{safe(tag)}</span>' for tag in item['tags'])}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(f"用「{item['name']}」", key=f"gallery_{index}", use_container_width=True):
                st.session_state.pending_prefs = dict(item["prefs"])
                st.session_state.gallery_name = item["name"]
                st.session_state.free_text = ""
                st.rerun()


def render_recommendation_result(result: Dict[str, Any]) -> None:
    if not result.get("selected"):
        render_empty_state(
            "🥀",
            "这次没有生成出可用搭配",
            str(result.get("rationale") or "请稍后重试，或直接去当季花材库挑花。"),
        )
        return
    price = current_price()
    source_label = "AI 花艺师" if result.get("source") == "llm" else "本地搭配引擎"
    budget_value = float(result.get("budget") or st.session_state.budget)
    st.markdown(
        f"""<div class="rec-card">
            <div class="rec-title">{safe(result.get('title', '为你搭配的花束'))}</div>
            <div class="rec-text">{safe(result.get('rationale', ''))}</div>
            <div class="rec-meta">
                <span class="rec-chip">✦ {safe(source_label)}</span>
                <span class="rec-chip">{safe(SIZE_CONFIG.get(st.session_state.size, SIZE_CONFIG['M'])['label'])}</span>
                <span class="rec-chip">预估 {money(price['total_price'])}</span>
                <span class="rec-chip">预算 {money(budget_value)}</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )
    if price["total_price"] > budget_value:
        st.warning(
            f"这套搭配预估 {money(price['total_price'])}，超出预算 {money(price['total_price'] - budget_value)}。"
            f"可以把尺寸调到 {size_for_budget(budget_value)} 码，或在工作台减少支数。"
        )
    if result.get("llm_error"):
        st.caption(f"提示：{result['llm_error']}")
    if result.get("free_text"):
        st.caption(f"已参考你的描述：{result['free_text']}")
    if result.get("web_used"):
        st.caption("本次搭配参考了联网花语资料；花材仍严格来自候选白名单。")

    groups = [
        ("main", "主花", 3),
        ("filler", "配花", 3),
        ("foliage", "叶材", 2),
        ("fruit", "果材", 2),
    ]
    for key, label, columns in groups:
        flowers = result.get(key) or []
        if not flowers:
            continue
        meta = CATEGORY_META[label]
        st.markdown(f"#### {meta['emoji']} {label}")
        render_flower_grid(
            flowers,
            f"rec_{key}",
            columns,
            preferred_color=str(result.get("prefs", {}).get("color", "任意")),
        )

    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.2, 1, 1])
    if c1.button("去工作台定包装 →", type="primary", use_container_width=True):
        go_to("花束工作台")
    if c2.button("🎲 再换一组", use_container_width=True):
        run_recommendation(
            st.session_state.free_text,
            int(time.time() * 1000) % 100000,
            use_web=bool(st.session_state.get("ai_web_enabled", False)),
        )
        st.rerun()
    if c3.button("查看季节花材库", use_container_width=True):
        go_to("当季花材库")


def render_ai_page() -> None:
    if st.session_state.auto_recommend:
        st.session_state.auto_recommend = False
        run_recommendation(
            st.session_state.free_text,
            int(time.time()),
            use_web=bool(st.session_state.get("ai_web_enabled", False)),
        )
        st.rerun()

    section_header("AI 花艺师", "设计一束有心意的花", "先选左侧偏好，也可以用一句话告诉我们你的想法。")
    st.text_area(
        "描述你的想法",
        key="free_text",
        height=86,
        placeholder="例如：给妈妈的生日花，温柔一点，预算 300，不要太白。",
        label_visibility="collapsed",
    )
    action_col, note_col = st.columns([1, 1.35])
    with action_col:
        if st.button("✨ 生成搭配", type="primary", use_container_width=True):
            run_recommendation(
                st.session_state.free_text,
                int(time.time()),
                use_web=bool(st.session_state.ai_web_enabled),
            )
            st.rerun()
    with note_col:
        st.markdown("<div class='small-note'>也可以留空，直接按偏好为你推荐。</div>", unsafe_allow_html=True)
    with st.expander("更多灵感与设置", expanded=False):
        st.checkbox("联网补充花语灵感", key="ai_web_enabled")
        st.caption("联网结果只作灵感参考。")
        render_gallery()

    result = st.session_state.recommend_result
    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    if result:
        section_header("为你搭配", "这束花适合你的心意", "")
        render_recommendation_result(result)
    else:
        render_empty_state(
            "💐",
            "你的花束会出现在这里",
            "调整左侧偏好后，点击「生成搭配」。",
        )


# ============================================================
# 页面：当季花材库
# ============================================================
def render_library_page() -> None:
    season = current_season()
    section_header("花材图鉴", f"{season} · 当季花材", "挑喜欢的花，加入花篮。")
    st.markdown(
        f"""<div class="summary-card" style="display:flex; flex-wrap:wrap; gap:14px; align-items:center; justify-content:space-between; margin-bottom:12px;">
            <div>
                <div class="summary-label">花材精选</div>
                <div style="font-size:1.05rem; font-weight:750; margin-top:3px;">{len(FLOWERS)} 种花材 · {now_cn().month} 月</div>
            </div>
            <div style="font-size:1.8rem;">🌾</div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.text_input(
        "搜索花材",
        key="library_search",
        placeholder="搜索花名或花语",
        label_visibility="collapsed",
    )
    f1, f2 = st.columns(2, gap="medium")
    with f1:
        st.selectbox("类别", ["全部"] + CATEGORY_ORDER, key="library_category")
    with f2:
        st.selectbox("颜色", COLOR_CHOICES, key="library_color")
    with st.expander("更多筛选", expanded=False):
        f3, f4 = st.columns(2, gap="medium")
        with f3:
            st.selectbox("季节", ["当季", "不限", "春季", "夏季", "秋季", "冬季"], key="library_season")
        with f4:
            st.selectbox(
                "排序",
                ["当季优先", "价格从低到高", "价格从高到低", "名称"],
                key="library_sort",
            )
        # Keep the slider widget's frontend state separate from the canonical
        # filter value to prevent a stale value from being applied on a later rerun.
        if "library_max_price_widget" not in st.session_state:
            st.session_state.library_max_price_widget = max(
                2, min(50, int(st.session_state.library_max_price))
            )
        st.slider(
            "单支价上限",
            2,
            50,
            step=1,
            key="library_max_price_widget",
            format="¥%d",
            on_change=lambda: setattr(
                st.session_state,
                "library_max_price",
                int(st.session_state.library_max_price_widget),
            ),
        )
        if "library_only_season" not in st.session_state:
            st.session_state.library_only_season = False
        st.checkbox("只看当季限定", key="library_only_season")

    signature = json.dumps(
        {
            "search": st.session_state.library_search,
            "category": st.session_state.library_category,
            "color": st.session_state.library_color,
            "season": st.session_state.library_season,
            "max_price": st.session_state.library_max_price,
            "sort": st.session_state.library_sort,
            "only": st.session_state.library_only_season,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    if signature != st.session_state.lib_filter_sig:
        st.session_state.lib_filter_sig = signature
        st.session_state.lib_page = 1

    filtered = filter_flowers(
        FLOWERS,
        search=st.session_state.library_search,
        category=st.session_state.library_category,
        color=st.session_state.library_color,
        season=st.session_state.library_season,
        max_price=float(st.session_state.library_max_price),
        sort_key=st.session_state.library_sort,
    )
    if st.session_state.library_only_season:
        filtered = [
            flower
            for flower in filtered
            if season in flower.get("season_tags", []) and "全年" not in flower.get("season_tags", [])
        ]

    page_size = 12
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    st.session_state.lib_page = max(1, min(int(st.session_state.lib_page), total_pages))
    page = int(st.session_state.lib_page)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    c1, c2 = st.columns([1.4, 0.6])
    with c1:
        st.markdown(
            f"<div class='small-note'>找到 <b>{len(filtered)}</b> 种花材 · 当前第 {page}/{total_pages} 页</div>",
            unsafe_allow_html=True,
        )
    with c2:
        if st.session_state.selected_flowers:
            if st.button("查看已选花篮 →", type="primary", use_container_width=True):
                go_to("花束工作台")

    if page_items:
        render_flower_grid(
            page_items,
            "library",
            3,
            preferred_color=str(st.session_state.library_color),
        )
    else:
        render_empty_state("🔍", "没有找到匹配的花材", "试试放宽颜色、价格或季节条件。")

    if total_pages > 1:
        p1, p2, p3 = st.columns([1, 1.4, 1])
        if p1.button("← 上一页", key="lib_prev", disabled=page <= 1, use_container_width=True):
            st.session_state.lib_page = page - 1
            st.rerun()
        p2.markdown(
            f"<div style='text-align:center; color:#8B7B88; font-size:0.78rem; padding-top:8px;'>第 {page} / {total_pages} 页</div>",
            unsafe_allow_html=True,
        )
        if p3.button("下一页 →", key="lib_next", disabled=page >= total_pages, use_container_width=True):
            st.session_state.lib_page = page + 1
            st.rerun()

    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    with st.expander("🌐 联网补充花语 / 养护灵感（可选）", expanded=False):
        st.caption("联网查询是可选项。网络不可用时会静默回退到本地知识库，不影响选花和下单。")
        web_query = st.text_input(
            "查一种花",
            key="web_query",
            placeholder="例如：洋桔梗 花语",
        )
        if st.button("联网查一查", key="web_lookup_button"):
            with st.spinner("正在联网查询…"):
                results = web_lookup(web_query)
            st.session_state.web_results = results
            st.session_state.web_results_query = web_query
        results = st.session_state.get("web_results") or []
        if results:
            st.markdown(f"**关于「{safe(st.session_state.get('web_results_query', ''))}」的联网结果**", unsafe_allow_html=True)
            for item in results[:3]:
                title = safe(item.get("title", ""))
                source = safe(item.get("source", ""))
                extract = safe(item.get("extract", ""))
                url = str(item.get("url", ""))
                link = f' · <a href="{safe(url)}" target="_blank">查看来源</a>' if url.startswith("http") else ""
                st.markdown(
                    f"<div class='summary-card' style='margin-bottom:8px;'>"
                    f"<div style='font-weight:700;'>🌐 {title} <span class='fc-tag'>{source}</span></div>"
                    f"<div class='small-note' style='margin-top:4px;'>{extract}{link}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        elif st.session_state.get("web_results_query"):
            st.caption("联网没有返回结果，可能当前网络受限；本地知识库仍然可用。")


# ============================================================
# 页面：花束工作台
# ============================================================
def render_size_selector() -> None:
    cols = st.columns(4, gap="small")
    for index, (key, config) in enumerate(SIZE_CONFIG.items()):
        active = st.session_state.size == key
        with cols[index]:
            st.markdown(
                f"""<div style="
                    padding: 12px 8px;
                    border-radius: 16px;
                    text-align: center;
                    border: 1.5px solid {'rgba(199,92,122,0.65)' if active else 'rgba(111,79,119,0.13)'};
                    background: {'linear-gradient(135deg, rgba(255,249,249,0.98), rgba(249,238,244,0.95))' if active else 'rgba(255,255,255,0.62)'};
                    margin-bottom: 6px;
                ">
                    <div style="font-weight:800; font-size:0.95rem;">{safe(config['label'])}</div>
                    <div class="small-note">{safe(config['dims'])}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button(
                "已选" if active else "选择",
                key=f"size_btn_{key}",
                use_container_width=True,
                disabled=active,
            ):
                st.session_state.pending_widgets = {"size": key}
                st.rerun()


def _current_spec_signature() -> str:
    return json.dumps(
        {
            "size": st.session_state.size,
            "shape": st.session_state.shape,
            "packaging": st.session_state.packaging,
            "ribbon": st.session_state.ribbon,
            "color": st.session_state.color,
            "flowers": [
                [
                    int(flower["id"]),
                    str(flower.get("selected_color", "")),
                    qty_for(st.session_state.flower_quantities, int(flower["id"])),
                ]
                for flower in st.session_state.selected_flowers
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def render_workbench_page() -> None:
    section_header(
        "03 / ATELIER",
        "花束工作台",
        "调整花材与包装，确认效果和预算。",
    )
    if not st.session_state.selected_flowers:
        render_empty_state("🧺", "花篮还是空的", "先去 AI 灵感生成一套搭配，或去当季花材库挑几枝喜欢的花。")
        c1, c2 = st.columns(2)
        if c1.button("✨ 去 AI 灵感", type="primary", use_container_width=True):
            go_to("AI 灵感")
        if c2.button("🌿 去当季花材库", use_container_width=True):
            go_to("当季花材库")
        return

    for flower in st.session_state.selected_flowers:
        flower_id = int(flower["id"])
        if qty_for(st.session_state.flower_quantities, flower_id) <= 0:
            st.session_state.flower_quantities[flower_id] = default_quantity(
                flower, st.session_state.size
            )
        st.session_state.custom_roles.setdefault(
            flower_id,
            "主花" if flower.get("category") == "主花" else "配花",
        )

    price = current_price()
    stems = sum(
        qty_for(st.session_state.flower_quantities, int(flower["id"]))
        for flower in st.session_state.selected_flowers
    )
    budget = float(st.session_state.budget)
    remaining = budget - price["total_price"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("花材种类", f"{len(st.session_state.selected_flowers)} 种")
    m2.metric("总支数", f"{stems} 支")
    m3.metric("预估总价", money(price["total_price"]))
    m4.metric("预算余量", money(remaining) if remaining >= 0 else f"-{money(abs(remaining))}")

    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    section_header("STEP 01", "花束样式", "")
    render_size_selector()

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.selectbox(
            "花束形态",
            list(SHAPE_OPTIONS.keys()),
            format_func=lambda key: f"{SHAPE_OPTIONS[key]['icon']} {SHAPE_OPTIONS[key]['label']}",
            key="shape",
        )
    with c2:
        st.selectbox(
            "包装材质",
            list(PACKAGING_OPTIONS.keys()),
            format_func=lambda key: f"{PACKAGING_OPTIONS[key]['icon']} {PACKAGING_OPTIONS[key]['label']}",
            key="packaging",
        )
    with c3:
        st.selectbox(
            "丝带颜色",
            list(RIBBON_OPTIONS.keys()),
            format_func=lambda key: f"{RIBBON_OPTIONS[key]['label']}",
            key="ribbon",
        )
    shape = current_shape()
    packaging = current_packaging()
    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    section_header("STEP 02", "调整花材", "")

    for flower in list(st.session_state.selected_flowers):
        flower_id = int(flower["id"])
        maximum = max_quantity(flower, st.session_state.size)
        current_quantity = int(
            st.session_state.flower_quantities.get(
                flower_id,
                default_quantity(flower, st.session_state.size),
            )
        )
        current_quantity = max(1, min(maximum, current_quantity))
        st.session_state.flower_quantities[flower_id] = current_quantity

        with st.container(border=True):
            col_a, col_b, col_c, col_d = st.columns([3.1, 1.7, 1.0, 0.65], gap="small")
            with col_a:
                category = str(flower.get("category", "配花"))
                color_options = flower_color_options(flower)
                color_key = f"flower_color_{flower_id}"
                stored_color = str(flower.get("selected_color", ""))
                if stored_color not in color_options:
                    stored_color = _default_flower_color(flower, st.session_state.color)
                    flower["selected_color"] = stored_color
                if st.session_state.get(color_key) not in color_options:
                    st.session_state[color_key] = stored_color

                thumbnail = flower_image_data_uri(flower)
                if thumbnail:
                    identity_html = (
                        f'<img src="{thumbnail}" alt="{safe(flower.get("name", "花材"))}" '
                        'style="width:52px;height:52px;object-fit:cover;border-radius:12px;flex:0 0 52px;" />'
                    )
                else:
                    identity_html = f'<span style="font-size:1.5rem;">{flower_emoji(flower)}</span>'
                st.markdown(
                    f"""<div style="display:flex;align-items:center;gap:12px;">
                    {identity_html}<div><div class="basket-name">{safe(flower.get('name', ''))}
                    <span class="badge soft" style="font-size:0.6rem;">{safe(category)}</span></div>
                    <div class="basket-sub">{safe(flower.get('english_name', ''))} · ¥{float(flower.get('unit_price', 0)):.0f}/支</div></div></div>""",
                    unsafe_allow_html=True,
                )
                st.caption("花色")
                st.selectbox(
                    f"{safe(flower.get('name', '花材'))}颜色",
                    color_options,
                    key=color_key,
                    label_visibility="collapsed",
                    on_change=_set_flower_color,
                    args=(flower_id, color_key),
                    help="为这项花材选择颜色",
                )
            with col_b:
                st.caption("支数")
                minus_col, value_col, plus_col = st.columns([0.7, 0.8, 0.7], gap="small")
                if minus_col.button("−", key=f"minus_{flower_id}", use_container_width=True):
                    st.session_state.flower_quantities[flower_id] = max(1, current_quantity - 1)
                    st.rerun()
                value_col.markdown(
                    f"<div style='text-align:center; font-weight:800; padding-top:0.25rem;'>{current_quantity}</div>",
                    unsafe_allow_html=True,
                )
                if plus_col.button("＋", key=f"plus_{flower_id}", use_container_width=True):
                    st.session_state.flower_quantities[flower_id] = min(maximum, current_quantity + 1)
                    st.rerun()
            with col_c:
                st.caption("角色")
                current_role = st.session_state.custom_roles.get(
                    flower_id,
                    "主花" if flower.get("category") == "主花" else "配花",
                )
                if current_role not in {"主花", "配花"}:
                    current_role = "配花"
                if st.button(
                    f"{'🌹' if current_role == '主花' else '✨'} {current_role}",
                    key=f"toggle_{flower_id}",
                    use_container_width=True,
                    help="点击切换主花/配花",
                ):
                    st.session_state.custom_roles[flower_id] = (
                        "配花" if current_role == "主花" else "主花"
                    )
                    st.rerun()
            with col_d:
                st.caption("操作")
                if st.button("移除", key=f"remove_{flower_id}", use_container_width=True):
                    st.session_state.pending_remove_id = flower_id
                    st.rerun()

    main_stems = sum(
        qty_for(st.session_state.flower_quantities, int(flower["id"]))
        for flower in st.session_state.selected_flowers
        if st.session_state.custom_roles.get(int(flower["id"]), "配花") == "主花"
    )
    filler_stems = max(0, stems - main_stems)
    if stems > 0:
        st.progress(
            main_stems / stems,
            text=f"主花 {main_stems} 支 · {main_stems / stems * 100:.0f}% ｜ 配花/叶材 {filler_stems} 支",
        )
        ratio = main_stems / stems
        if ratio == 0:
            st.warning("至少设置一种主花，花束才有视觉焦点。")
        elif ratio < 0.18:
            st.warning("主花占比偏低，可以增加主花支数或减少配花。")
        elif ratio > 0.82:
            st.info("主花占比很高，适当加一点配花和叶材会更有层次。")
        else:
            st.success("主配花比例协调，花束有焦点也有呼吸感。")

    b1, b2, b3 = st.columns(3)
    if b1.button("按推荐支数重置", use_container_width=True):
        reset_quantities = {
            int(flower["id"]): default_quantity(flower, st.session_state.size)
            for flower in st.session_state.selected_flowers
        }
        st.session_state.pending_quantities = reset_quantities
        st.rerun()
    if b2.button("压缩到预算内", use_container_width=True):
        tuned = tune_quantities_to_budget(
            st.session_state.selected_flowers,
            st.session_state.flower_quantities,
            st.session_state.size,
            st.session_state.packaging,
            st.session_state.shape,
            budget,
        )
        st.session_state.pending_quantities = tuned
        st.rerun()
    if b3.button("清空花篮", use_container_width=True):
        st.session_state.pending_reset = True
        st.rerun()

    price = current_price()
    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    section_header("STEP 03", "预览与价格", "")
    preview_col, price_col = st.columns([1.05, 1], gap="large")
    svg = build_svg_preview(
        st.session_state.selected_flowers,
        st.session_state.flower_quantities,
        st.session_state.size,
        st.session_state.shape,
        st.session_state.packaging,
        st.session_state.ribbon,
        color_preference=st.session_state.color,
    )
    with preview_col:
        st.markdown(
            f'<img src="{svg_data_uri(svg)}" alt="花束结构示意图" '
            'style="width:100%; border-radius:24px; box-shadow:0 16px 34px rgba(96,64,82,0.10);" />',
            unsafe_allow_html=True,
        )
        st.download_button(
            "下载结构示意图（SVG）",
            data=svg.encode("utf-8"),
            file_name=f"花束结构图_{st.session_state.size}_{now_cn():%m%d}.svg",
            mime="image/svg+xml",
            use_container_width=True,
        )
    with price_col:
        st.markdown("**花材明细**")
        for item in price["flower_detail"]:
            if item["quantity"] <= 0:
                continue
            item_thumbnail = flower_image_data_uri(item, st.session_state.color)
            item_image = (
                f'<img src="{item_thumbnail}" alt="{safe(item.get("name", "花材"))}" '
                'style="width:28px;height:28px;object-fit:cover;border-radius:8px;vertical-align:middle;margin-right:6px;" />'
                if item_thumbnail
                else f"{flower_emoji(item['name'], item['category'])} "
            )
            st.markdown(
                f"<div style='display:flex; justify-content:space-between; gap:8px; padding:4px 0; border-bottom:1px dashed rgba(111,79,119,0.10);'>"
                f"<span>{item_image}{safe(item['name'])} · {safe(item.get('selected_color', ''))} × {item['quantity']}</span>"
                f"<b>{money(item['subtotal'])}</b></div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div style='margin-top:12px; line-height:1.9;'>"
            f"<div style='display:flex; justify-content:space-between;'><span>包装材料 + 形态</span><b>{money(price['packaging_cost'])}</b></div>"
            f"<div style='display:flex; justify-content:space-between;'><span>花艺师手工费</span><b>{money(price['labor_cost'])}</b></div>"
            f"<div style='display:flex; justify-content:space-between;'><span>配送费</span><b>{'免费' if price['delivery_fee'] == 0 else money(price['delivery_fee'])}</b></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.metric("订单总价", money(price["total_price"]))
        usage = price["total_price"] / budget if budget else 0
        st.progress(
            min(1.0, max(0.0, usage)),
            text=f"预算使用 {usage * 100:.0f}% · 上限 {money(budget)}",
        )
        if usage > 1:
            st.error(f"已超出预算 {money(price['total_price'] - budget)}。可以减少支数、换小一码，或点“压缩到预算内”。")
        elif usage > 0.92:
            st.warning("已经接近预算上限，留一点余量给配送或临时调整会更稳妥。")
        else:
            st.caption("当前搭配在预算内。价格为预估，最终以花艺师确认为准。")

    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    section_header("STEP 04", "效果预览", "")
    prompt = build_image_prompt(
        st.session_state.selected_flowers,
        st.session_state.flower_quantities,
        st.session_state.size,
        st.session_state.shape,
        st.session_state.packaging,
        st.session_state.ribbon,
        st.session_state.color,
    )
    manifest_text = "；".join(
        f"{item['quantity']} 支 {item.get('selected_color', '')} {item['name']}（{item['english_name']}）"
        for item in price["flower_detail"]
        if item["quantity"] > 0
    )
    with st.expander("查看生图提示词（英文）", expanded=False):
        st.code(prompt, language="text")
        st.download_button(
            "下载提示词",
            data=prompt.encode("utf-8"),
            file_name="花束生图提示词.txt",
            mime="text/plain",
        )

    quota = image_quota()
    disabled_reasons = []
    if not IMAGE_KEY:
        disabled_reasons.append("未配置生图 API")
    if quota["remaining"] <= 0:
        disabled_reasons.append("今日额度已用完")
    if quota["cooldown"] > 0:
        disabled_reasons.append(f"冷却中，{quota['cooldown']} 秒后可再生成")
    generate_disabled = bool(disabled_reasons)
    gen_col1, gen_col2 = st.columns([1.2, 1])
    with gen_col1:
        if st.button(
            "🎨 生成 AI 效果图",
            type="primary",
            use_container_width=True,
            disabled=generate_disabled,
            help="；".join(disabled_reasons) if disabled_reasons else "生成一张风格参考图",
        ):
            with st.status("正在准备花束效果图…", expanded=True) as status:
                try:
                    status.update(label="步骤 1/3 · 调用生图模型", state="running")
                    image_result = generate_bouquet_image(prompt)
                    if not image_result.get("success"):
                        status.update(label="生成失败", state="error")
                        st.error(image_result.get("message", "生图失败"))
                    else:
                        record_image_generation()
                        vision = None
                        if VISION_MODEL and VISION_KEY:
                            status.update(label="步骤 2/3 · 视觉一致性检查", state="running")
                            try:
                                vision = vision_consistency_check(
                                    str(image_result.get("url", "")),
                                    image_result.get("bytes"),
                                    manifest_text,
                                )
                            except Exception as vision_exc:
                                vision = {"error": f"{type(vision_exc).__name__}"}
                        else:
                            status.update(label="步骤 2/3 · 跳过视觉检查（未配置 VISION_MODEL）", state="running")
                        st.session_state.generated_image = {
                            **image_result,
                            "prompt": prompt,
                            "manifest": manifest_text,
                            "vision": vision,
                            "spec_sig": _current_spec_signature(),
                            "size_label": SIZE_CONFIG[st.session_state.size]["label"],
                            "shape_label": current_shape()["label"],
                            "packaging_label": current_packaging()["label"],
                            "ribbon_label": RIBBON_OPTIONS[st.session_state.ribbon]["label"],
                            "created_at": now_cn().strftime("%m-%d %H:%M"),
                        }
                        status.update(label="步骤 3/3 · 完成", state="complete")
                        st.success("效果图已生成。")
                except Exception as exc:
                    status.update(label="生成过程异常", state="error")
                    st.error(f"生成过程异常：{type(exc).__name__}")
    quota = image_quota()
    with gen_col2:
        st.caption(
            f"今日剩余 {quota['remaining']}/{quota['limit']} 次 · 冷却 {quota['cooldown']} 秒"
        )
        if not IMAGE_KEY:
            st.caption("未配置生图服务，可下载结构图或提示词。")

    generated = st.session_state.generated_image
    if generated:
        if generated.get("spec_sig") != _current_spec_signature():
            st.warning("花材或包装已经调整过，下面这张图对应的是上一次配方。请重新生成以匹配当前方案。")
        image_col, info_col = st.columns([1.1, 1], gap="large")
        with image_col:
            if generated.get("bytes"):
                st.image(generated["bytes"], use_column_width=True)
            elif generated.get("url"):
                st.image(generated["url"], use_column_width=True)
            if generated.get("bytes"):
                st.download_button(
                    "下载效果图",
                    data=generated["bytes"],
                    file_name=f"花束效果图_{now_cn():%m%d_%H%M}.png",
                    mime="image/png",
                    use_container_width=True,
                )
            elif generated.get("url"):
                st.markdown(f"[在新标签打开原图]({generated['url']})")
        with info_col:
            st.markdown(
                f"""<div class="summary-card">
                    <div class="summary-label">IMAGE SPEC</div>
                    <div style="font-size:1.05rem; font-weight:800; margin:4px 0;">{safe(generated.get('size_label', SIZE_CONFIG[st.session_state.size]['label']))}</div>
                    <div class="small-note">{safe(generated.get('shape_label', current_shape()['label']))} · {safe(generated.get('packaging_label', current_packaging()['label']))} · {safe(generated.get('ribbon_label', RIBBON_OPTIONS[st.session_state.ribbon]['label']))}</div>
                    <div class="small-note" style="margin-top:8px;">生成于 {safe(generated.get('created_at', ''))}</div>
                    <div class="small-note" style="margin-top:8px;">花材清单：{safe(generated.get('manifest', ''))}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            vision = generated.get("vision")
            if isinstance(vision, dict):
                if "match_score" in vision:
                    try:
                        score = int(float(vision.get("match_score", 0)))
                    except (TypeError, ValueError):
                        score = 0
                    missing = vision.get("missing") or []
                    extra = vision.get("extra") or []
                    if isinstance(missing, str):
                        missing = [missing]
                    if isinstance(extra, str):
                        extra = [extra]
                    comment = str(vision.get("comment") or "")
                    if score >= 80 and not missing and not extra:
                        st.success(f"视觉质检 {score}/100：花材与配方基本一致。{comment}")
                    else:
                        st.warning(
                            f"视觉质检 {score}/100：{comment or '建议对照结构图检查。'}"
                            + (f" 缺少：{'、'.join(map(str, missing))}" if missing else "")
                            + (f" 多出：{'、'.join(map(str, extra))}" if extra else "")
                        )
                elif vision.get("error"):
                    st.caption(f"视觉质检未完成：{vision['error']}")
            else:
                st.caption(
                    "未配置视觉质检模型。建议以左侧结构图作为花材与支数的准确依据。"
                    if not (VISION_MODEL and VISION_KEY)
                    else "视觉质检没有返回结果。建议以左侧结构图作为花材与支数的准确依据。"
                )
            st.caption("效果图仅作风格参考，花材与支数以配方为准。")

    st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
    section_header("STEP 05", "收花信息", "")

    with st.form("order_form", clear_on_submit=False):
        f1, f2 = st.columns(2)
        with f1:
            recipient = st.text_input("收花人", placeholder="怎么称呼收花人？")
        with f2:
            phone = st.text_input("手机号", placeholder="用于配送联系")
        f3, f4 = st.columns(2)
        with f3:
            delivery_date = st.date_input(
                "配送日期",
                value=now_cn().date() + timedelta(days=1),
                min_value=now_cn().date(),
                max_value=now_cn().date() + timedelta(days=30),
            )
        with f4:
            delivery_slot = st.selectbox(
                "配送时段",
                ["09:00–12:00", "12:00–15:00", "15:00–18:00", "18:00–21:00"],
            )
        address = st.text_input("配送地址", placeholder="城市 / 区 / 街道 / 门牌号")
        message = st.text_area(
            "祝福语",
            key="order_message",
            height=82,
            placeholder="写一句想对 Ta 说的话…",
        )
        submitted = st.form_submit_button("提交订单", type="primary", use_container_width=True)

    submitted_order: Optional[Dict[str, Any]] = None
    if submitted:
        errors = []
        if not recipient.strip():
            errors.append("请填写收花人")
        if not re.fullmatch(r"1[3-9]\d{9}", phone.strip()):
            errors.append("手机号格式不正确")
        if len(address.strip()) < 6:
            errors.append("请填写完整配送地址")
        if errors:
            st.error("；".join(errors))
        else:
            order_id = f"FL{now_cn():%Y%m%d%H%M%S}"
            submitted_order = {
                "order_id": order_id,
                "created_at": now_cn().strftime("%Y-%m-%d %H:%M"),
                "recipient": recipient.strip(),
                "phone": phone.strip(),
                "address": address.strip(),
                "delivery_date": delivery_date.strftime("%Y-%m-%d"),
                "delivery_slot": delivery_slot,
                "items": price["flower_detail"],
                "size": st.session_state.size,
                "size_label": SIZE_CONFIG[st.session_state.size]["label"],
                "shape": st.session_state.shape,
                "shape_label": current_shape()["label"],
                "packaging": st.session_state.packaging,
                "packaging_label": current_packaging()["label"],
                "ribbon": st.session_state.ribbon,
                "ribbon_label": RIBBON_OPTIONS[st.session_state.ribbon]["label"],
                "price": price,
                "message": message.strip(),
                "spec_sig": _current_spec_signature(),
            }
            st.session_state.orders.insert(0, submitted_order)
            st.session_state.orders = st.session_state.orders[:10]
            st.session_state.last_order = submitted_order
            st.session_state.custom_message = message.strip()
            st.balloons()
            st.success("订单已提交。合作花店会在 30 分钟内电话确认。")

    order_to_show = submitted_order or st.session_state.last_order
    if order_to_show:
        order_price_value = order_to_show.get("price")
        order_show_price: Dict[str, Any] = order_price_value if isinstance(order_price_value, dict) else {}
        st.markdown(
            f"""<div class="order-card" style="margin-top:12px;">
                <div class="order-id">ORDER · {safe(order_to_show.get('order_id', ''))}</div>
                <div style="display:flex; flex-wrap:wrap; justify-content:space-between; gap:12px; align-items:end; margin-top:6px;">
                    <div>
                        <div style="font-size:1.08rem; font-weight:800;">{safe(order_to_show.get('recipient', ''))} · {safe(order_to_show.get('delivery_date', ''))} {safe(order_to_show.get('delivery_slot', ''))}</div>
                        <div class="small-note">{safe(order_to_show.get('address', ''))}</div>
                    </div>
                    <div class="order-total">{money(order_show_price.get('total_price', 0))}</div>
                </div>
                <div class="small-note" style="margin-top:8px;">{safe(order_to_show.get('message', '') or '无祝福语')}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        summary_text = build_order_summary(order_to_show)
        d1, d2 = st.columns(2)
        d1.download_button(
            "下载订单 JSON",
            data=json.dumps(order_to_show, ensure_ascii=False, indent=2),
            file_name=f"{order_to_show.get('order_id', 'order')}.json",
            mime="application/json",
            use_container_width=True,
        )
        d2.download_button(
            "下载订单文本",
            data=summary_text,
            file_name=f"{order_to_show.get('order_id', 'order')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
        with st.expander("查看订单摘要", expanded=False):
            st.code(summary_text, language="text")
        st.caption("演示版订单保存在当前浏览器会话；接入支付或商家后台时，替换提交逻辑即可。")


# ============================================================
# 入口
# ============================================================
def main() -> None:
    process_pending_actions()
    render_hero()
    render_sidebar()

    st.radio(
        "页面导航",
        ["AI 灵感", "当季花材库", "花束工作台"],
        horizontal=True,
        key="nav",
        label_visibility="collapsed",
    )
    if st.session_state.nav == "AI 灵感":
        render_ai_page()
    elif st.session_state.nav == "当季花材库":
        render_library_page()
    else:
        render_workbench_page()

    st.markdown(
        """
        <div class="footer" style="text-align:center; padding:36px 12px 18px; color:#A28F9C; font-size:12px;">
            <div style="height:1px; background:linear-gradient(90deg, transparent, rgba(111,79,119,0.16), transparent); margin-bottom:18px;"></div>
            <div>信心花舍 · AI 花束定制平台</div>
            <div style="margin-top:4px;">花材知识库 + OpenAI 兼容大模型 · 结构示意与 AI 效果图并行</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
