# ══════════════════════════════════════════
# helpers.py
# ትንንሽ ጠቅላላ (generic) utility functions።
# ══════════════════════════════════════════
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import ADMIN_IDS
from config_extra import BRAND_SIGNATURE
from translations import T


def t(ctx, key, **kwargs):
    """የተጠቃሚውን ቋንቋ መሰረት አድርጎ ትርጉም ይመልሳል፣ {brand} ካለ በራሱ ይሞላል"""
    lang = ctx.user_data.get("lang", "am")
    template = T[lang].get(key, T["am"].get(key, key))
    kwargs.setdefault("brand", BRAND_SIGNATURE)
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def is_admin(user_id):
    return user_id in ADMIN_IDS


def mask_phone(phone):
    phone = str(phone).strip()
    if len(phone) < 9:
        return phone
    stars_count = len(phone) - 9
    return phone[:7] + ("*" * stars_count) + phone[-2:]


def get_cancel_keyboard(ctx):
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(ctx, "home_btn")), KeyboardButton(t(ctx, "cancel_btn"))]],
        resize_keyboard=True
    )


def remove_menu():
    return ReplyKeyboardRemove()
