# ══════════════════════════════════════════
# config_extra.py
# እነዚህ ዋና config.py ውስጥ ይጨመራሉ (ወይም እንደራሱ ፋይል ሆነው import ይደረጋሉ)።
# SaaS: ለሌላ ደንበኛ ስታሰማራ የሚቀየሩት እዚህ ብቻ ናቸው።
# ══════════════════════════════════════════

# ── GitHub Pages (Mini Apps hosting) ──
GITHUB_PAGES_BASE = "https://tazaragnerfirst-coder.github.io/equb-bot"
INDEX_APP_URL      = f"{GITHUB_PAGES_BASE}/"
PAYMENT_APP_URL    = f"{GITHUB_PAGES_BASE}/payment.html"

# ── Render (Flask keep-alive host) ──
RENDER_PUBLIC_URL = "https://equb-bot-vt5m.onrender.com"

# ── Brand signature (bottom of user-facing confirmation messages) ──
BRAND_SIGNATURE = "Developed by @TazaBiz"

# ── Optional overrides (already handled as try/except in main.py,
#    kept here for a single place to look at) ──
# REQUIRED_GROUP_LINK        -> falls back to f"https://t.me/c/{str(GROUP_ID).replace('-100','')}"
# CHANNEL_ID                 -> None disables channel-join requirement
# REQUIRED_CHANNEL_LINK      -> None disables channel-join requirement
# SUPPORT_CONTACT_USERNAME   -> default "TazaBiz"
SUPPORT_CONTACT_USERNAME_DEFAULT = "TazaBiz"
