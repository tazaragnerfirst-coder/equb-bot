import os
import json
import asyncio
import logging
from datetime import date, datetime, timedelta
from urllib.parse import quote

import requests as req_lib
from threading import Thread
from flask import Flask, Response, request
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import BadRequest
import database as db
from database import db as fdb
from config import BOT_TOKEN, ADMIN_IDS, GROUP_ID, CBE_ACCOUNT, CBE_NAME, TELEBIRR_ACCOUNT, TELEBIRR_NAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_TICKETS_PER_USER = 10
PUBLIC_URL = "https://equb-bot-vt5m.onrender.com"

# ══════════════════════════════════════════
# PAYMENT MINI APP (separate from ticket-selection index.html)
# ══════════════════════════════════════════
PAYMENT_APP_URL = "https://tazaragnerfirst-coder.github.io/equb-bot/payment.html"

PAYMENT_CONTINUE_TEXT = {
    "am": "💳 ክፍያ ቀጥል",
    "en": "💳 Continue to Payment",
    "or": "💳 Kaffaltiitti Itti Fufi",
}

# ══════════════════════════════════════════
# CONFIG — ግሩፕ membership
# ══════════════════════════════════════════
try:
    from config import REQUIRED_GROUP_LINK
except ImportError:
    REQUIRED_GROUP_LINK = f"https://t.me/c/{str(GROUP_ID).replace('-100', '')}"

# ── ቻናል (optional) — config.py ላይ CHANNEL_ID/REQUIRED_CHANNEL_LINK ከሌለ
# ይህ ፍቸር በራሱ disabled ሆኖ ይቀራል (ምንም ስህተት አይፈጥርም) ──
try:
    from config import CHANNEL_ID, REQUIRED_CHANNEL_LINK
except ImportError:
    CHANNEL_ID = None
    REQUIRED_CHANNEL_LINK = None

# ── ሰፖርት ኮንታክት (optional) ──
try:
    from config import SUPPORT_CONTACT_USERNAME
except ImportError:
    SUPPORT_CONTACT_USERNAME = "TazaBiz"

flask_app = Flask('', static_folder='.', static_url_path='')

@flask_app.route('/')
def home():
    return "Bot is alive! 🤖"

# ══════════════════════════════════════════
# CORS HELPERS (payment.html is hosted on GitHub Pages — different origin)
# ══════════════════════════════════════════
def _cors_json(data, status=200):
    resp = flask_app.response_class(
        response=json.dumps(data),
        status=status,
        mimetype='application/json'
    )
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

def _cors_preflight():
    resp = flask_app.response_class(status=204)
    resp.headers['Access-Control-Allow-Origin']  = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp

_bot_username_cache = {"value": None}

def _get_bot_username_cached():
    if _bot_username_cache["value"]:
        return _bot_username_cache["value"]
    try:
        r = req_lib.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
        r.raise_for_status()
        username = r.json().get("result", {}).get("username")
        if username:
            _bot_username_cache["value"] = username
        return username
    except Exception as e:
        logger.error(f"getMe error: {e}")
        return None

# ══════════════════════════════════════════
# RECEIPT IMAGE PROXY
# ══════════════════════════════════════════
@flask_app.route('/get-receipt/<int:pid>')
def get_receipt_image(pid):
    try:
        doc = fdb.collection('payments').document(str(pid)).get()
        if not doc.exists:
            return "Not found", 404
        file_id = doc.to_dict().get('receipt_file_id')
        if not file_id:
            return "No receipt", 404
        r = req_lib.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=10
        )
        r.raise_for_status()
        result = r.json().get("result", {})
        file_path = result.get("file_path")
        if not file_path:
            return "File path not found", 404
        img = req_lib.get(
            f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}",
            timeout=15
        )
        img.raise_for_status()
        return Response(
            img.content,
            content_type=img.headers.get('content-type', 'image/jpeg')
        )
    except req_lib.exceptions.Timeout:
        logger.error(f"get_receipt_image timeout: pid={pid}")
        return "Timeout", 504
    except Exception as e:
        logger.error(f"get_receipt_image error pid={pid}: {e}")
        return "Error", 500


# ══════════════════════════════════════════
# PAYMENT CONFIG (bank accounts + price) — for payment.html
# ══════════════════════════════════════════
@flask_app.route('/payment-config', methods=['GET', 'OPTIONS'])
def payment_config():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    try:
        price = asyncio.run(db.get_setting("ticket_price"))
        return _cors_json({
            "cbe_account": CBE_ACCOUNT,
            "cbe_name": CBE_NAME,
            "telebirr_account": TELEBIRR_ACCOUNT,
            "telebirr_name": TELEBIRR_NAME,
            "ticket_price": int(price) if price else 0,
        })
    except Exception as e:
        logger.error(f"payment_config error: {e}")
        return _cors_json({"status": "error", "message": "Server error"}, 500)


# ══════════════════════════════════════════
# SUBMIT PAYMENT — receives phone/name/method/receipt from payment.html
# ══════════════════════════════════════════
@flask_app.route('/submit-payment', methods=['POST', 'OPTIONS'])
def submit_payment():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    try:
        numbers_str = request.form.get('numbers', '').strip()
        user_id     = request.form.get('user_id', '').strip()
        username    = request.form.get('username', '—').strip() or '—'
        full_name   = request.form.get('full_name', '').strip()
        phone       = request.form.get('phone', '').strip()
        method      = request.form.get('method', '').strip()
        lang        = request.form.get('lang', 'am').strip() or 'am'
        receipt     = request.files.get('receipt')

        if lang not in T:
            lang = 'am'

        if not (numbers_str and user_id and full_name and phone and method and receipt):
            return _cors_json({"status": "error", "message": "Missing fields"}, 400)

        try:
            numbers = [int(n) for n in numbers_str.split(',') if n.strip().isdigit()]
        except ValueError:
            numbers = []
        if not numbers:
            return _cors_json({"status": "error", "message": "No valid numbers"}, 400)

        # Re-validate availability (guards against race conditions since selection)
        for num in numbers:
            ticket = asyncio.run(db.get_ticket(num))
            if ticket and ticket[4] == "taken":
                return _cors_json({"status": "error", "message": f"Number {num} already taken"}, 409)

        price       = int(asyncio.run(db.get_setting("ticket_price")) or 0)
        total_price = len(numbers) * price

        # Upload receipt bytes to Telegram once, to obtain a reusable file_id
        log_chat_id = ADMIN_IDS[0]
        upload = req_lib.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": log_chat_id, "caption": "📥 Receipt (Mini App upload)"},
            files={"photo": (receipt.filename or "receipt.jpg", receipt.stream, receipt.mimetype or "image/jpeg")},
            timeout=20
        )
        upload.raise_for_status()
        upload_result = upload.json().get("result", {})
        photos = upload_result.get("photo", [])
        if not photos:
            return _cors_json({"status": "error", "message": "Receipt upload failed"}, 502)
        file_id = photos[-1]["file_id"]

        payment_id = asyncio.run(db.add_payment(
            user_id, username, phone, numbers, file_id, method, full_name=full_name
        ))
        asyncio.run(db.reserve_tickets(numbers, user_id, username, phone))

        bot_username  = _get_bot_username_cached()
        receipt_link  = f"https://t.me/{bot_username}?start=receipt_{payment_id}" if bot_username else None
        tg_username   = username if str(username).startswith("@") or username == "—" else f"@{username}"

        admin_caption = (
            f"💳 <b>New Payment!</b>\n"
            f"{'─'*20}\n"
            f"👤 <b>{full_name}</b>\n"
            f"🔗 {tg_username}\n"
            f"📞 {phone}\n"
            f"🆔 <code>{user_id}</code>\n"
            f"{'─'*20}\n"
            f"🎟 <b>Numbers:</b> {', '.join(map(str, sorted(numbers)))}\n"
            f"📦 <b>Count:</b> {len(numbers)}\n"
            f"💰 <b>Total:</b> {total_price} ETB\n"
            f"💳 <b>Method:</b> {method}\n"
            f"🔖 <b>#{payment_id}</b>"
        )

        inline_kb = [[
            {"text": "✅ Approve", "callback_data": f"approve_{payment_id}"},
            {"text": "❌ Reject",  "callback_data": f"reject_{payment_id}"}
        ]]
        if receipt_link:
            inline_kb.append([{"text": "🧾 ደረሰኝ ይመልከቱ", "url": receipt_link}])
        keyboard = {"inline_keyboard": inline_kb}

        for admin_id in ADMIN_IDS:
            try:
                req_lib.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    data={
                        "chat_id": admin_id,
                        "photo": file_id,
                        "caption": admin_caption,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(keyboard),
                    },
                    timeout=15
                )
            except Exception as e:
                logger.error(f"Admin notify (mini app) error: {e}")

        # ── ተጠቃሚው ደረሰኙ በትክክል መላኩን የሚያረጋግጥ መልክት ──
        try:
            confirm_text = T[lang]["sent_ok"].format(
                name=full_name,
                phone=phone,
                nums=", ".join(map(str, sorted(numbers))),
                total=total_price,
                method=method
            )
            req_lib.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": user_id, "text": confirm_text, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            logger.error(f"User confirm notify error: {e}")

        return _cors_json({"status": "ok", "payment_id": payment_id})

    except Exception as e:
        logger.error(f"submit_payment error: {e}")
        return _cors_json({"status": "error", "message": "Server error"}, 500)


def keep_alive():
    t = Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080))
    t.daemon = True
    t.start()

from admin_auth import register_admin_verify_route
register_admin_verify_route(flask_app)

# ══════════════════════════════════════════
# TRANSLATIONS  
# ══════════════════════════════════════════
T = {
    "am": {
        "pick_btn":       "❇️ ቁጥር ምረጥ ❇️",
        "my_tickets_btn": "✴️ የኔ ትኬቶች ✴️",
        "info_btn":       "ℹ️ አጠቃቀም ℹ️",
        "admin_btn":      "🔰 ADMIN 🔰",
        "admin_cards_btn":"📋 CARDS",
        "home_btn":       "🏠 ዋና ገጽ",
        "cancel_btn":     "❌ ሰርዝ",
        "back_btn":       "◀️ ተመለስ",

        "join_required": (
            "⚠️ *ቦቱን ለመጠቀም መጀመሪያ*\n"
            "*ቡድናችንን መቀላቀል ይኖርብዎታል!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 ቀላቅለው ✅ ተቀላቅያለሁ ይጫኑ።"
        ),
        "join_btn":       "📢 ቡድኑን ቀላቀሉ",
        "joined_btn":     "✅ ተቀላቅያለሁ",
        "not_joined":     "⚠️ ገና ቡድኑን አልተቀላቀሉም። ቀላቅለው እንደገና ይሞክሩ።",

        "contact_required": (
            "📱 *ቦቱን ለመጠቀም ስልክ ቁጥርዎን ማጋራት ያስፈልጋል*\n"
            "━━━━━━━━━━━━━━━\n"
            "ይህ የሚያስፈልገው ክፍያ ሲፈጽሙ በራስ-ሰር\n"
            "መረጃዎን ለመሙላት ነው።\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 ከስር ያለውን ቁልፍ ተጭነው ኮንታክትዎን ያጋሩ።"
        ),
        "contact_btn":    "📱 ኮንታክት አጋራ",
        "contact_own_only": "⚠️ እባክዎ የራስዎን ኮንታክት ብቻ ያጋሩ።",

        "home_text": (
            "🎉 *{title}*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ አንደኛ እጣ 👉 {prize1}\n"
            "2️⃣ ሁለተኛ እጣ 👉 {prize2}\n"
            "3️⃣ ሦስተኛ እጣ 👉 {prize3}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {total}\n"
            "የአንዱ ትኬት ዋጋ = {price}\n"
            "━━━━━━━━━━━━━━━\n"
            "የሚፈልጉትን ትኬት ቁጥር ለመምረጥ\n"
            "ከስር ያለውን 👇 \" ❇️ ቁጥር ምረጥ ❇️ \"\n"
            "የሚለውን ቁልፍ ይጫኑ!"
        ),

        "payment_intro": (
            "💳 *ክፍያ*\n"
            "━━━━━━━━━━━━━━━\n"
            "አሁን የመረጧቸው ቁጥሮች 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {count}\n"
            "ዋጋ = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "ክፍያ ለመፈጸም ከስር ያለውን 👇\n"
            "\"💳 ክፍያ ቀጥል\" የሚለውን ይጫኑ!"
        ),
        "pay_cbe_btn":     "🏦 CBE",
        "pay_telebirr_btn":"📱 TELE BIRR",
        "pay_back_btn":    "◀️ ተመለስ",

        "cbe_msg": (
            "🏦 *CBE*\n"
            "━━━━━━━━━━━━━━━\n"
            "አካዉንት ቁጥር 👉 `{account}`\n"
            "ስም 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "ድምር ዋጋ = {total} ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "ክፍያ ከፈፀሙ በኋላ\n"
            "የከፈሉበትን ደረሰኝ (screenshot)\n"
            "ይላኩልን 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "telebirr_msg": (
            "📱 *TELE BIRR*\n"
            "━━━━━━━━━━━━━━━\n"
            "አካዉንት ቁጥር 👉 `{account}`\n"
            "ስም 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "ድምር ዋጋ = {total} ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "ክፍያ ከፈፀሙ በኋላ\n"
            "የከፈሉበትን ደረሰኝ (screenshot)\n"
            "ይላኩልን 👇🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "ask_name":      "👤 *ሙሉ ስምዎን ይፃፉ:*\nምሳሌ: አበበ ባልቻ",
        "ask_phone":     "📞 *ስልክ ቁጥርዎን ይፃፉ:*\nምሳሌ: 09########",
        "invalid_phone": "⚠️ ትክክለኛ ስልክ ቁጥር ይፃፉ። ምሳሌ: 0911223344",
        "receipt_only":  "⚠️ እባክዎ *screenshot (ፎቶ)* ይላኩ።",

        "preview_msg": (
            "📋 *ማረጋገጫ*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 ቁጥሮች: {nums}\n"
            "👤 ስም: {name}\n"
            "📞 ስልክ: {phone}\n"
            "💰 ዋጋ: {total} ብር\n"
            "💳 ዘዴ: {method}\n"
            "━━━━━━━━━━━━━━━"
        ),
        "confirm_send": "✅ ልክ ነው፣ ላክ",

        "sent_ok": (
            "✅ *ደረሰኝዎ ተልኳል!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👤 ስም: {name}\n"
            "📞 ስልክ: {phone}\n"
            "🎟 የመረጡት ቁጥር: {nums}\n"
            "💰 ድምር: {total} ብር\n"
            "💳 ዘዴ: {method}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ አድሚን ሲያረጋግጥ notification\n"
            "ይደርስዎታል። እናመሰግናለን!\n"
            "Developed by @TazaBiz"
        ),

        "approved": (
            "🎉 *ክፍያዎ ተረጋግጧል!*\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ ክፍያዎ ተረጋግጧል!\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 ቁጥሮቾ: {nums}\n"
            "💰 {total} ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ ቁጥሮቹ የእርስዎ ሆነዋል።\n"
            "እጣ እስኪቆረጥ ድረስ ይጠብቁ!\n"
            "✳️ እናመሰግናለን! ✳️\n"
            "Developed by @TazaBiz"
        ),
        "rejected": (
            "❌ *ክፍያዎ አልተረጋገጠም።*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 ቁጥሮች: {nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "እባክዎ ትክክለኛ ማስረጃ ይላኩ\n"
            "ወይም ድጋሚ ይሞክሩ።"
        ),

        "my_tickets_hdr": "✴️ *የኔ ትኬቶች* ✴️",
        "my_tickets_body": (
            "ዉድ {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "አስካሁን የእርስዎ የሆኑት ቁጥሮች 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {count}\n"
            "ዋጋ = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "የእጣ መቁረጫ ቀን እስከሚደርስ\n"
            "ተጨማሪ ትኬቶችን መቁረጥ ይችላሉ።\n"
            "━━━━━━━━━━━━━━━\n"
            "✳️ እናመሰግናለን! ✳️"
        ),
        "my_tickets_pending": (
            "ዉድ {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ በሂደት ላይ ያሉ ቁጥሮች 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "የትኬት ብዛት = {count}\n"
            "ዋጋ = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ አድሚን እስኪያረጋግጥ ይጠብቁ።"
        ),
        "no_tickets": (
            "✴️ *የኔ ትኬቶች* ✴️\n"
            "━━━━━━━━━━━━━━━\n"
            "ምንም ትኬት የለዎትም።"
        ),
        "referral_btn": "👥 Referral",
        "back_home_btn": "🔙 Back",

        "referral_info": (
            "👥 *Referral ስርዓት*\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 የእርስዎ Referral ሊንክ:\n"
            "`{link}`\n"
            "━━━━━━━━━━━━━━━\n"
            "👥 የጋበዟቸው: *{count}* ሰዎች\n"
            "💰 ሊያገኙ የሚችሉ: *{reward}* ብር\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 ለእያንዳንዱ የሚጋብዟቸው ሰው\n"
            "በአንድ ሰው *2 ብር* ይከፈልዎታል!"
        ),

        "info_text": (
            "ℹ️ *ሙሉ አጠቃቀም መመሪያ*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ ቋንቋ ይምረጡ\n"
            "2️⃣ ቡድናችንን (እና ካለ ቻናላችንን) ይቀላቀሉ፣ ከዛ ✅ ተቀላቅያለሁ ይጫኑ\n"
            "3️⃣ ስልክ ቁጥርዎን ያጋሩ — ይህ በክፍያ ወቅት መረጃዎን በራስ-ሰር ለመሙላት ያገለግላል\n"
            "4️⃣ \"❇️ ቁጥር ምረጥ ❇️\" ተጭነው የሚፈልጉትን የትኬት ቁጥር(ሮች) ይምረጡ\n"
            "5️⃣ \"💳 ክፍያ ቀጥል\" ተጭነው CBE ወይም Telebirr ይምረጡ፣ ስምና ስልክ ያረጋግጡ፣ ከዛ የከፈሉበትን ደረሰኝ (screenshot) ይላኩ\n"
            "6️⃣ አድሚን ደረሰኙን ካረጋገጠ በኋላ ቁጥሮቹ የእርስዎ ይሆናሉ — የማረጋገጫ መልክት ይደርስዎታል\n"
            "7️⃣ በ\"✴️ የኔ ትኬቶች ✴️\" ማንኛውም ጊዜ የገዙትን/በሂደት ላይ ያሉትን ቁጥሮች ማየት ይችላሉ\n"
            "8️⃣ ጓደኞችዎን በ Referral ሊንክ ጋብዘው ለእያንዳንዱ የተጋበዘ ሰው 2 ብር ያግኙ\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *ማሳሰቢያ:* ትክክለኛ ደረሰኝ ብቻ ተቀባይነት ይኖረዋል፤ የተቀየረ ወይም ትርጉም የሌለው ደረሰኝ ውድቅ ይሆናል።\n"
            "📌 እርዳታ ካስፈለገዎት \"💬 Support\" ይጫኑ"
        ),

        "num_taken": "⚠️ ቁጥር {num} ቀድሞ ተይዟል! እንደገና ይምረጡ።",

        "sold_announce": "🎟 ቁጥር *{num}* ተሽጧል!",

        "skip_btn":       "⏭ Skip",
        "support_btn":    "💬 Support",
        "support_menu_text": (
            "🆘 *ሰፖርት*\n"
            "━━━━━━━━━━━━━━━\n"
            "እርዳታ ከፈለጉ ከስር ያሉትን ይምረጡ 👇"
        ),
        "feedback_btn":   "💬 አስተያየት መስጫ",
        "support_contact_btn": "📞 ሰፓርት መገናኛ",
        "feedback_prompt": "💬 *አስተያየትዎን ይፃፉ:*\nመልክትዎ በቀጥታ ለአድሚን ይላካል።",
        "feedback_sent":   "✅ አስተያየትዎ ተልኳል! እናመሰግናለን።",
        "visit_group_btn":   "👥 Visit Group",
        "visit_channel_btn": "📢 Visit Channel",
        "mainmenu_btn":      "🏠 Main Menu",
    },

    "en": {
        "pick_btn":       "❇️ Pick Numbers ❇️",
        "my_tickets_btn": "✴️ My Tickets ✴️",
        "info_btn":       "ℹ️ How to Use ℹ️",
        "admin_btn":      "🔰 ADMIN 🔰",
        "admin_cards_btn":"📋 CARDS",
        "home_btn":       "🏠 Home",
        "cancel_btn":     "❌ Cancel",
        "back_btn":       "◀️ Back",

        "join_required": (
            "⚠️ *You must join our group*\n"
            "*to use this bot!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Join then tap ✅ I Joined."
        ),
        "join_btn":       "📢 Join Group",
        "joined_btn":     "✅ I Joined",
        "not_joined":     "⚠️ You haven't joined yet. Please join and try again.",

        "contact_required": (
            "📱 *You must share your contact to use this bot*\n"
            "━━━━━━━━━━━━━━━\n"
            "This is needed to auto-fill your details\n"
            "during payment.\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Tap the button below to share your contact."
        ),
        "contact_btn":    "📱 Share Contact",
        "contact_own_only": "⚠️ Please share your own contact only.",

        "home_text": (
            "🎉 *{title}*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ First Prize 👉 {prize1}\n"
            "2️⃣ Second Prize 👉 {prize2}\n"
            "3️⃣ Third Prize 👉 {prize3}\n"
            "━━━━━━━━━━━━━━━\n"
            "Total Tickets = {total}\n"
            "Ticket Price = {price}\n"
            "━━━━━━━━━━━━━━━\n"
            "To pick your ticket number\n"
            "press the button below 👇\n"
            "\" ❇️ Pick Numbers ❇️ \""
        ),

        "payment_intro": (
            "💳 *Payment*\n"
            "━━━━━━━━━━━━━━━\n"
            "Your selected numbers 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Ticket Count = {count}\n"
            "Total = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "Tap \"💳 Continue to Payment\" below 👇"
        ),
        "pay_cbe_btn":      "🏦 CBE",
        "pay_telebirr_btn": "📱 TELE BIRR",
        "pay_back_btn":     "◀️ Back",

        "cbe_msg": (
            "🏦 *CBE*\n"
            "━━━━━━━━━━━━━━━\n"
            "Account Number 👉 `{account}`\n"
            "Name 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Total Amount = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Please pay using this account\n"
            "and send us your receipt\n"
            "(screenshot) 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "telebirr_msg": (
            "📱 *TELE BIRR*\n"
            "━━━━━━━━━━━━━━━\n"
            "Account Number 👉 `{account}`\n"
            "Name 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Total Amount = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Please pay using this account\n"
            "and send us your receipt\n"
            "(screenshot) 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "ask_name":      "👤 *Enter your full name:*\nExample: Abebe Kebede",
        "ask_phone":     "📞 *Enter your phone number:*\nExample: 09########",
        "invalid_phone": "⚠️ Please enter a valid phone number. Example: 0911223344",
        "receipt_only":  "⚠️ Please send a *screenshot (photo)*.",

        "preview_msg": (
            "📋 *Confirmation*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Numbers: {nums}\n"
            "👤 Name: {name}\n"
            "📞 Phone: {phone}\n"
            "💰 Total: {total} ETB\n"
            "💳 Method: {method}\n"
            "━━━━━━━━━━━━━━━"
        ),
        "confirm_send": "✅ Correct, Send",

        "sent_ok": (
            "✅ *Receipt sent!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👤 Name: {name}\n"
            "📞 Phone: {phone}\n"
            "🎟 Numbers: {nums}\n"
            "💰 Total: {total} ETB\n"
            "💳 Method: {method}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ You will be notified once\n"
            "admin confirms. Thank you!\n"
            "Developed by @TazaBiz"
        ),

        "approved": (
            "🎉 *Payment Confirmed!*\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ Your payment is confirmed!\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Numbers: {nums}\n"
            "💰 {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Your numbers are reserved.\n"
            "Wait for the draw!\n"
            "✳️ Thank you! ✳️\n"
            "Developed by @TazaBiz"
        ),
        "rejected": (
            "❌ *Payment Not Confirmed.*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Numbers: {nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Please send a valid receipt\n"
            "or try again."
        ),

        "my_tickets_hdr": "✴️ *My Tickets* ✴️",
        "my_tickets_body": (
            "Dear {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "Your reserved numbers 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Ticket Count = {count}\n"
            "Total = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "You can buy more tickets\n"
            "until the draw date.\n"
            "━━━━━━━━━━━━━━━\n"
            "✳️ Thank you! ✳️"
        ),
        "my_tickets_pending": (
            "Dear {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Pending numbers 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Ticket Count = {count}\n"
            "Total = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Waiting for admin approval."
        ),
        "no_tickets": (
            "✴️ *My Tickets* ✴️\n"
            "━━━━━━━━━━━━━━━\n"
            "You have no tickets yet."
        ),
        "referral_btn":  "👥 Referral",
        "back_home_btn": "🔙 Back",

        "referral_info": (
            "👥 *Referral System*\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 Your Referral Link:\n"
            "`{link}`\n"
            "━━━━━━━━━━━━━━━\n"
            "👥 Referred: *{count}* people\n"
            "💰 Reward: *{reward}* ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 Earn *2 ETB* for every\n"
            "person you invite, paid at draw!"
        ),

        "info_text": (
            "ℹ️ *Complete Guide*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ Choose your language\n"
            "2️⃣ Join our group (and channel, if shown), then tap ✅ I Joined\n"
            "3️⃣ Share your phone number — this auto-fills your info during payment\n"
            "4️⃣ Tap \"❇️ Pick Numbers ❇️\" and select the ticket number(s) you want\n"
            "5️⃣ Tap \"💳 Continue to Payment\", choose CBE or Telebirr, confirm your name & phone, then upload your payment receipt (screenshot)\n"
            "6️⃣ Once admin verifies your receipt, the numbers become yours — you'll get a confirmation message\n"
            "7️⃣ Check \"✴️ My Tickets ✴️\" anytime to see your purchased/pending numbers\n"
            "8️⃣ Invite friends with your Referral link and earn 2 ETB for each person you invite\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *Note:* Only valid receipts are accepted; edited or unclear receipts will be rejected.\n"
            "📌 Need help? Tap \"💬 Support\""
        ),

        "num_taken": "⚠️ Number {num} is already taken! Please pick again.",

        "sold_announce": "🎟 Number *{num}* sold!",

        "skip_btn":       "⏭ Skip",
        "support_btn":    "💬 Support",
        "support_menu_text": (
            "🆘 *Support*\n"
            "━━━━━━━━━━━━━━━\n"
            "Choose an option below 👇"
        ),
        "feedback_btn":   "💬 Send Feedback",
        "support_contact_btn": "📞 Contact Support",
        "feedback_prompt": "💬 *Type your feedback:*\nYour message will be sent directly to the admin.",
        "feedback_sent":   "✅ Your feedback has been sent! Thank you.",
        "visit_group_btn":   "👥 Visit Group",
        "visit_channel_btn": "📢 Visit Channel",
        "mainmenu_btn":      "🏠 Main Menu",
    },

    "or": {
        "pick_btn":       "❇️ Lakkoofsa Filadhu ❇️",
        "my_tickets_btn": "✴️ Tikeetii Koo ✴️",
        "info_btn":       "ℹ️ Akkamitti fayyadamuu ℹ️",
        "admin_btn":      "🔰 ADMIN 🔰",
        "admin_cards_btn":"📋 CARDS",
        "home_btn":       "🏠 Fuula Jalqabaa",
        "cancel_btn":     "❌ Haquu",
        "back_btn":       "◀️ Deebi'i",

        "join_required": (
            "⚠️ *Garee keenya makamuun*\n"
            "*bot kana fayyadamuuf barbaachisaadha!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Makamtee booda ✅ Makamuun koo cuqaasi."
        ),
        "join_btn":       "📢 Garee Makamu",
        "joined_btn":     "✅ Makamuun koo",
        "not_joined":     "⚠️ Ammallee garee hin makaamin. Makamtee ammas yaali.",

        "contact_required": (
            "📱 *Bot kana fayyadamuuf lakkoofsa bilbilaa kee qooduu qabda*\n"
            "━━━━━━━━━━━━━━━\n"
            "Kun kaffaltii yeroo raawwattu odeeffannoo\n"
            "kee ofumaan guutuuf barbaachisa.\n"
            "━━━━━━━━━━━━━━━\n"
            "👇 Mallattoo gadii tuqi kontaakticha qoodi."
        ),
        "contact_btn":    "📱 Kontaakti Qoodi",
        "contact_own_only": "⚠️ Maaloo kontaaktii kee qofa qoodi.",

        "home_text": (
            "🎉 *{title}*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ Badhaasa 1ffaa 👉 {prize1}\n"
            "2️⃣ Badhaasa 2ffaa 👉 {prize2}\n"
            "3️⃣ Badhaasa 3ffaa 👉 {prize3}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {total}\n"
            "Gatii tikeetii tokkoo = {price}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii filachuuf\n"
            "cuqaasi 👇 \" ❇️ Lakkoofsa Filadhu ❇️ \""
        ),

        "payment_intro": (
            "💳 *Kaffaltii*\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa filatame 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {count}\n"
            "Gatii = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "\"💳 Kaffaltiitti Itti Fufi\" jedhu cuqaasi 👇"
        ),
        "pay_cbe_btn":      "🏦 CBE",
        "pay_telebirr_btn": "📱 TELE BIRR",
        "pay_back_btn":     "◀️ Deebi'i",

        "cbe_msg": (
            "🏦 *CBE*\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa akkaawuntii 👉 `{account}`\n"
            "Maqaa 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Gatii waliigalaa = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Akkaawuntii kana fayyadamuun\n"
            "kaffalii, booda beeksisa\n"
            "(screenshot) ergi 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "telebirr_msg": (
            "📱 *TELE BIRR*\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa akkaawuntii 👉 `{account}`\n"
            "Maqaa 👉 {name}\n"
            "━━━━━━━━━━━━━━━\n"
            "Gatii waliigalaa = {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Akkaawuntii kana fayyadamuun\n"
            "kaffalii, booda beeksisa\n"
            "(screenshot) ergi 👇 🧾\n"
            "━━━━━━━━━━━━━━━\n"
        ),

        "ask_name":      "👤 *Maqaa guutuu kee barreessi:*\nFkn: Abebe Kebede",
        "ask_phone":     "📞 *Lakkoofsa bilbilaa kee barreessi:*\nFkn: 09########",
        "invalid_phone": "⚠️ Lakkoofsa bilbilaa sirrii barreessi. Fkn: 0911223344",
        "receipt_only":  "⚠️ *Screenshot (suuraa)* ergi.",

        "preview_msg": (
            "📋 *Mirkaneessaa*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Lakkoofsa: {nums}\n"
            "👤 Maqaa: {name}\n"
            "📞 Bilbila: {phone}\n"
            "💰 Gatii: {total} ETB\n"
            "💳 Mala: {method}\n"
            "━━━━━━━━━━━━━━━"
        ),
        "confirm_send": "✅ Sirriidha, Ergi",

        "sent_ok": (
            "✅ *Beeksisni ergame!*\n"
            "━━━━━━━━━━━━━━━\n"
            "👤 Maqaa: {name}\n"
            "📞 Bilbila: {phone}\n"
            "🎟 Lakkoofsa: {nums}\n"
            "💰 Waliigala: {total} ETB\n"
            "💳 Mala: {method}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Admin mirkaneesu booda\n"
            "beeksifama. Galatoomi!\n"
            "Developed by @TazaBiz"
        ),

        "approved": (
            "🎉 *Kaffaltiins mirkanaa'e!*\n"
            "━━━━━━━━━━━━━━━\n"
            "✅ Kaffaltiin kee mirkanaa'e!\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Lakkoofsa: {nums}\n"
            "💰 {total} ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsi kee qabame.\n"
            "Fiigichaa eegi!\n"
            "✳️ Galatoomi! ✳️\n"
            "Developed by @TazaBiz"
        ),
        "rejected": (
            "❌ *Kaffaltiins hin mirkanaa'in.*\n"
            "━━━━━━━━━━━━━━━\n"
            "🎟 Lakkoofsa: {nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Beeksisa sirrii ergi\n"
            "ykn ammas yaali."
        ),

        "my_tickets_hdr": "✴️ *Tikeetii Koo* ✴️",
        "my_tickets_body": (
            "Kabajamaa {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa kee 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {count}\n"
            "Gatii = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "Guyyaa fiigichaa dura\n"
            "tikeetii dabalataa bitachuu dandeessa.\n"
            "━━━━━━━━━━━━━━━\n"
            "✳️ Galatoomi! ✳️"
        ),
        "my_tickets_pending": (
            "Kabajamaa {username}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Lakkoofsa eegaa jiru 👇\n"
            "━━━━━━━━━━━━━━━\n"
            "{nums}\n"
            "━━━━━━━━━━━━━━━\n"
            "Lakkoofsa tikeetii = {count}\n"
            "Gatii = {total}\n"
            "━━━━━━━━━━━━━━━\n"
            "⏳ Admin mirkaneessuu eegaa jira."
        ),
        "no_tickets": (
            "✴️ *Tikeetii Koo* ✴️\n"
            "━━━━━━━━━━━━━━━\n"
            "Tikeetii hin qabdu."
        ),
        "referral_btn":  "👥 Referral",
        "back_home_btn": "🔙 Back",

        "referral_info": (
            "👥 *Referral*\n"
            "━━━━━━━━━━━━━━━\n"
            "🔗 Link kee:\n"
            "`{link}`\n"
            "━━━━━━━━━━━━━━━\n"
            "👥 Affeerre: *{count}* namoota\n"
            "💰 Badhaasa: *{reward}* ETB\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 Nama hunda affeerteef\n"
            "Nama tokkoof *2 ETB* argatta!"
        ),

        "info_text": (
            "ℹ️ *Qajeelfama Guutuu*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ Afaan filadhu\n"
            "2️⃣ Garee keenya (fi channel, yoo jiraate) makami, ergasii ✅ Makamuun koo tuqi\n"
            "3️⃣ Lakkoofsa bilbilaa kee qoodi — kun odeeffannoo kee kaffaltii keessatti ofumaan guutuuf gargaara\n"
            "4️⃣ \"❇️ Lakkoofsa Filadhu ❇️\" tuqiitii lakkoofsa tikeetii barbaaddu filadhu\n"
            "5️⃣ \"💳 Kaffaltiitti Itti Fufi\" tuqi, CBE ykn Telebirr filadhu, maqaa fi bilbila mirkaneessi, ergasii ragaa kaffaltii (screenshot) ergi\n"
            "6️⃣ Admin ragaa kee erga mirkaneessee booda lakkoofsi kee siif ta'a — ergaa mirkaneessaa siif erga\n"
            "7️⃣ Yeroo barbaaddetti \"✴️ Tikeetii Koo ✴️\" ilaaluun lakkoofsa bitatte/eegaa jiru argachuu dandeessa\n"
            "8️⃣ Hiriyoota kee link Referral kaatiin afeeruun nama afeerte hunda irraa 2 ETB argadha\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *Yaadadhu:* Ragaan sirrii qofa fudhatama; ragaan jijjiirame ykn ifa hin taane ni kufa.\n"
            "📌 Gargaarsa yoo barbaadde \"💬 Support\" tuqi"
        ),

        "num_taken": "⚠️ Lakkoofsi {num} fudhataame! Ammas filadhu.",

        "sold_announce": "🎟 Lakkoofsi *{num}* gurgurame!",

        "skip_btn":       "⏭ Skip",
        "support_btn":    "💬 Support",
        "support_menu_text": (
            "🆘 *Support*\n"
            "━━━━━━━━━━━━━━━\n"
            "Filannoo gadii filadhu 👇"
        ),
        "feedback_btn":   "💬 Yaada Ergi",
        "support_contact_btn": "📞 Kontaakti Sapoortii",
        "feedback_prompt": "💬 *Yaada kee barreessi:*\nErgaan kee kallattiin admin bira gaha.",
        "feedback_sent":   "✅ Yaadni kee ergameera! Galatoomi.",
        "visit_group_btn":   "👥 Visit Group",
        "visit_channel_btn": "📢 Visit Channel",
        "mainmenu_btn":      "🏠 Main Menu",
    }
}

# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════
def t(ctx, key, **kwargs):
    lang = ctx.user_data.get("lang", "am")
    template = T[lang].get(key, T["am"].get(key, key))
    try:
        return template.format(**kwargs)
    except:
        return template

def is_admin(user_id):
    return user_id in ADMIN_IDS

def mask_phone(phone):
    phone = str(phone).strip()
    if len(phone) < 6:
        return phone
    stars_count = len(phone) - 6
    return phone[:4] + ("*" * stars_count) + phone[-2:]

def get_cancel_keyboard(ctx):
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(ctx, "home_btn")), KeyboardButton(t(ctx, "cancel_btn"))]],
        resize_keyboard=True
    )

def remove_menu():
    return ReplyKeyboardRemove()

# ══════════════════════════════════════════
# MEMBERSHIP CHECK
# ══════════════════════════════════════════
async def is_member_of_group(bot, user_id: int) -> bool:
    """ተጠቃሚ ግሩፕ ውስጥ አለ ወይ አረጋግጥ"""
    try:
        from telegram.constants import ChatMemberStatus
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception as e:
        logger.warning(f"Membership check error for {user_id}: {e}")
        return True

async def is_member_of_channel(bot, user_id: int) -> bool:
    """ተጠቃሚ ቻናል ውስጥ አለ ወይ አረጋግጥ (ቻናል ካልተዋቀረ True ይመልሳል)"""
    if not CHANNEL_ID:
        return True
    try:
        from telegram.constants import ChatMemberStatus
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception as e:
        logger.warning(f"Channel membership check error for {user_id}: {e}")
        return True

async def is_fully_joined(bot, user_id: int) -> bool:
    """ግሩፕ እና (ካለ) ቻናል ሁለቱንም አረጋግጥ"""
    group_ok   = await is_member_of_group(bot, user_id)
    channel_ok = await is_member_of_channel(bot, user_id)
    return group_ok and channel_ok

async def send_join_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ (እና ካለ ቻናል) ቀላቅሉ ማሳወቂያ ይላካል"""
    lang = ctx.user_data.get("lang", "am")

    await update.effective_message.reply_text(
        "⏳",
        reply_markup=ReplyKeyboardRemove()
    )

    keyboard_rows = [[InlineKeyboardButton(T[lang]["join_btn"], url=REQUIRED_GROUP_LINK)]]
    if REQUIRED_CHANNEL_LINK:
        keyboard_rows.append([InlineKeyboardButton(T[lang]["visit_channel_btn"], url=REQUIRED_CHANNEL_LINK)])
    keyboard_rows.append([InlineKeyboardButton(T[lang]["joined_btn"], callback_data="check_membership")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)

    await update.effective_message.reply_text(
        T[lang]["join_required"],
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def send_contact_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ ከተቀላቀሉ በኋላ ኮንታክት እንዲያጋሩ ይጠየቃል"""
    lang = ctx.user_data.get("lang", "am")
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(T[lang]["contact_btn"], request_contact=True)],
         [KeyboardButton(T[lang]["skip_btn"])]],
        resize_keyboard=True
    )
    await update.effective_message.reply_text(
        T[lang]["contact_required"],
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def proceed_after_membership(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ አባልነት ከተረጋገጠ በኋላ፦ አድሚን ከሆነ ወይም ቀድሞ ኮንታክት ካጋራ ወደ home፣
    ካልሆነ ግን ኮንታክት እንዲያጋራ ይጠየቃል።"""
    user = update.effective_user
    if is_admin(user.id):
        await show_home(update, ctx)
        return
    profile = await db.get_profile(user.id)
    if not profile:
        await send_contact_prompt(update, ctx)
        return
    ctx.user_data["_profile_checked"] = True
    await show_home(update, ctx)

# ══════════════════════════════════════════
# CONTACT HANDLER
# ══════════════════════════════════════════
async def contact_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user    = update.effective_user
    lang    = ctx.user_data.get("lang", "am")

    if not contact or contact.user_id != user.id:
        await update.message.reply_text(T[lang]["contact_own_only"])
        return

    first = contact.first_name or user.first_name or ""
    last  = contact.last_name or user.last_name or ""
    phone = contact.phone_number or ""
    if phone and not phone.startswith("+"):
        phone = "+" + phone

    await db.save_profile(user.id, first, last, phone)
    ctx.user_data["_profile_checked"] = True

    await show_home(update, ctx)

# ══════════════════════════════════════════
# GROUP LIST
# ══════════════════════════════════════════
_group_update_lock = asyncio.Lock()
_group_update_pending = False

def _build_chunks(ticket_map, total, chunk_size=150):
    chunks = []
    for chunk_start in range(1, total + 1, chunk_size):
        chunk_end = min(chunk_start + chunk_size - 1, total)
        lines = []
        for n in range(chunk_start, chunk_end + 1):
            info = ticket_map.get(n)
            if info and info[1] == "taken":
                lines.append(f"{n} 👉 {mask_phone(info[0])} ✅")
            else:
                lines.append(f"{n} 👉")
        chunks.append("\n".join(lines))
    return chunks


async def send_full_list_to_group(bot, total):
    old_msgs = await db.get_group_message_ids()
    ticket_map = await db.get_all_tickets_full(total)
    new_chunks = _build_chunks(ticket_map, total)

    if old_msgs and len(old_msgs) == len(new_chunks):
        edited_ids = []
        for (msg_id, chat_id), text in zip(old_msgs, new_chunks):
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
            except BadRequest as e:
                if "not modified" not in str(e).lower():
                    logger.warning(f"Edit chunk error (msg_id={msg_id}): {e}")
            except Exception as e:
                logger.warning(f"Edit chunk error (msg_id={msg_id}): {e}")
            edited_ids.append(msg_id)
            await asyncio.sleep(0.4)
        return len(edited_ids)

    for msg_id, chat_id in old_msgs:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Delete old group msg error: {e}")
    await db.clear_group_messages()

    new_msg_ids = []
    for text in new_chunks:
        try:
            msg = await bot.send_message(chat_id=GROUP_ID, text=text)
            new_msg_ids.append(msg.message_id)
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Chunk send error: {e}")

    await db.save_group_message_ids(GROUP_ID, new_msg_ids)
    return len(new_msg_ids)


async def schedule_group_list_update(bot, total, min_interval=12):
    global _group_update_pending
    async with _group_update_lock:
        if _group_update_pending:
            return
        _group_update_pending = True

    async def _runner():
        global _group_update_pending
        try:
            await asyncio.sleep(min_interval)
            await send_full_list_to_group(bot, total)
        except Exception as e:
            logger.error(f"schedule_group_list_update error: {e}")
        finally:
            async with _group_update_lock:
                _group_update_pending = False

    asyncio.create_task(_runner())


# ══════════════════════════════════════════
# GROUP "SOLD" ANNOUNCEMENTS — sliding window of max 10
# ለእያንዳንዱ አዲስ የተሸጠ ቁጥር 1 መልክት ብቻ ግሩፕ ላይ ይላካል (duplicate guard)።
# ከ10 ካለፈ፣ ሁሉንም ከማጥፋት ይልቅ በጣም አሮጌውን 1 ብቻ አጥፍቶ አዲሱን ይተካል (ቋሚ sliding window)።
# ══════════════════════════════════════════
async def announce_sold_numbers(bot, numbers):
    for num in numbers:
        try:
            if await db.has_sold_announcement(num):
                continue
            msg = await bot.send_message(
                chat_id=GROUP_ID,
                text=T["am"]["sold_announce"].format(num=num),
                parse_mode="Markdown"
            )
            await db.add_sold_announcement(num, msg.message_id, GROUP_ID)

            all_announcements = await db.get_sold_announcements()
            if len(all_announcements) > 10:
                oldest_num, oldest_mid, oldest_cid, _ = all_announcements[0]
                try:
                    await bot.delete_message(chat_id=oldest_cid, message_id=oldest_mid)
                except Exception as e:
                    logger.warning(f"Delete oldest sold announce error: {e}")
                await db.remove_sold_announcement(oldest_num)
        except Exception as e:
            logger.error(f"Sold announce error num={num}: {e}")
        await asyncio.sleep(0.3)

# ══════════════════════════════════════════
# START / LANGUAGE
# ══════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args

    if args and args[0].startswith("receipt_"):
        if is_admin(user.id):
            try:
                payment_id = int(args[0].replace("receipt_", ""))
                payment = await db.get_payment(payment_id)
                if payment:
                    p_id       = payment[0]
                    p_user_id  = payment[1]
                    p_username = payment[2]
                    p_phone    = payment[3]
                    p_numbers  = payment[4]
                    p_receipt  = payment[5]
                    p_method   = payment[6]
                    p_status   = payment[7]
                    full_name  = payment[8] if payment[8] else p_username

                    price_val   = int(await db.get_setting("ticket_price"))
                    nums_list   = list(map(int, p_numbers.split(",")))
                    total_price = len(nums_list) * price_val
                    status_label = {
                        "pending":  "⏳ Pending",
                        "approved": "✅ Approved",
                        "rejected": "❌ Rejected"
                    }.get(p_status, p_status)

                    caption = (
                        f"🧾 <b>Receipt — Payment #{p_id}</b>\n"
                        f"{'─'*20}\n"
                        f"👤 <b>{full_name}</b>\n"
                        f"🔗 {p_username}\n"
                        f"📞 {p_phone}\n"
                        f"🎟 {p_numbers}\n"
                        f"💰 {total_price} ETB | {p_method}\n"
                        f"📊 {status_label}"
                    )
                    kb = []
                    if p_status == "pending":
                        kb.append([
                            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{p_id}"),
                            InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{p_id}")
                        ])
                    await ctx.bot.send_photo(
                        chat_id=user.id,
                        photo=p_receipt,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(kb) if kb else None
                    )
                else:
                    await update.message.reply_text("⚠️ Payment not found.")
            except Exception as e:
                logger.error(f"Receipt deep link error: {e}")
                await update.message.reply_text("⚠️ ደረሰኝ ማምጣት አልተቻለም።")
        return

    if args and args[0].startswith("ref_"):
        referrer_id = args[0].replace("ref_", "")
        if referrer_id != str(user.id):
            await db.add_referral(referrer_id, str(user.id))

    if not ctx.user_data.get("lang"):
        keyboard = [
            [InlineKeyboardButton("🇪🇹 አማርኛ",      callback_data="lang_am")],
            [InlineKeyboardButton("🇬🇧 English",      callback_data="lang_en")],
            [InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_or")],
        ]
        await update.message.reply_text(
            "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if not is_admin(user.id):
        if not await is_fully_joined(ctx.bot, user.id):
            await send_join_prompt(update, ctx)
            return

    await proceed_after_membership(update, ctx)


async def language_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇪🇹 አማርኛ",      callback_data="lang_am")],
        [InlineKeyboardButton("🇬🇧 English",      callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_or")],
    ]
    await update.message.reply_text(
        "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def lang_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    ctx.user_data["lang"] = lang
    await query.delete_message()

    user = update.effective_user
    if not is_admin(user.id):
        if not await is_fully_joined(ctx.bot, user.id):
            await send_join_prompt(update, ctx)
            return

    await proceed_after_membership(update, ctx)


# ══════════════════════════════════════════
# CHECK MEMBERSHIP CALLBACK
# ══════════════════════════════════════════
async def check_membership_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = update.effective_user

    if await is_fully_joined(ctx.bot, user.id):
        await query.answer()
        try:
            await query.delete_message()
        except:
            pass
        await proceed_after_membership(update, ctx)
    else:
        lang = ctx.user_data.get("lang", "am")
        await query.answer(T[lang]["not_joined"], show_alert=True)

# ══════════════════════════════════════════
# HOME
# ══════════════════════════════════════════
async def show_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    title  = await db.get_setting("lottery_title")
    price  = await db.get_setting("ticket_price")
    total  = await db.get_setting("total_tickets")
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")

    text = t(ctx, "home_text", title=title, total=total, price=price,
             prize1=prize1, prize2=prize2, prize3=prize3)

    lang    = ctx.user_data.get("lang", "am")
    lang_url = f"https://tazaragnerfirst-coder.github.io/equb-bot/?lang={lang}"
    rows = [
        [KeyboardButton(t(ctx, "pick_btn"), web_app=WebAppInfo(url=lang_url))],
        [KeyboardButton(t(ctx, "my_tickets_btn"))],
        [KeyboardButton(t(ctx, "info_btn")), KeyboardButton(t(ctx, "support_btn"))],
    ]
    if is_admin(user.id):
        rows.append([KeyboardButton(t(ctx, "admin_btn"))])
    reply_markup = ReplyKeyboardMarkup(rows, resize_keyboard=True)

    if update.callback_query:
        try:
            await update.callback_query.delete_message()
        except:
            pass

    home_image = await db.get_setting("home_image")
    if home_image:
        try:
            await update.effective_message.reply_photo(
                photo=home_image, caption=text, parse_mode="Markdown", reply_markup=reply_markup
            )
            return
        except Exception as e:
            logger.warning(f"Home image send failed, falling back to text: {e}")

    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def home_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["admin_action"] = None
    ctx.user_data["admin_menu"]   = False
    await show_home(update, ctx)

# ══════════════════════════════════════════
# SUPPORT
# ══════════════════════════════════════════
async def show_support_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lang = ctx.user_data.get("lang", "am")
    text = T[lang]["support_menu_text"]
    if SUPPORT_CONTACT_USERNAME:
        text += f"\n\n📞 {T[lang]['support_contact_btn']}: @{SUPPORT_CONTACT_USERNAME.lstrip('@')}"
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton(T[lang]["feedback_btn"])],
            [KeyboardButton(T[lang]["back_home_btn"]), KeyboardButton(T[lang]["mainmenu_btn"])],
        ],
        resize_keyboard=True
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def handle_feedback_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = ctx.user_data.get("lang", "am")
    text = update.message.text.strip()
    ctx.user_data["awaiting_feedback"] = False

    uname = f"@{user.username}" if user.username else (user.full_name or "—")
    fb_caption = (
        f"💬 <b>Feedback</b>\n"
        f"{'─'*20}\n"
        f"👤 {uname}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"{'─'*20}\n"
        f"{text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(chat_id=admin_id, text=fb_caption, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Feedback forward error: {e}")

    await update.message.reply_text(T[lang]["feedback_sent"])

# ══════════════════════════════════════════
# MESSAGE ROUTER
# ══════════════════════════════════════════
async def any_message_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    user = update.effective_user

    # ተጠቃሚ አስተያየት (feedback) እየፃፈ ከሆነ ወደ አድሚን ብቻ ላክ
    if ctx.user_data.get("awaiting_feedback"):
        await handle_feedback_text(update, ctx)
        return

    skip_words = ["⏭ Skip"]
    if any(w in text for w in skip_words):
        ctx.user_data["_profile_checked"] = True
        await show_home(update, ctx)
        return

    # ኮንታክት ገና ካላጋሩ (እና አድሚን ካልሆኑ) ማንኛውንም ግብዓት ወደ contact prompt መልስ
    if ctx.user_data.get("lang") and not is_admin(user.id) and not ctx.user_data.get("_profile_checked"):
        profile = await db.get_profile(user.id)
        if not profile:
            await send_contact_prompt(update, ctx)
            return
        ctx.user_data["_profile_checked"] = True

    home_words    = ["ዋና ገጽ", "Home", "Fuula Jalqabaa", "🏠 Main Menu", "🔙 Back"]
    cancel_words  = ["❌ ሰርዝ", "❌ Cancel", "❌ Haquu"]
    tickets_words = ["✴️ የኔ ትኬቶች ✴️", "✴️ My Tickets ✴️", "✴️ Tikeetii Koo ✴️"]
    admin_words   = ["🔰 ADMIN 🔰"]
    info_words    = ["ℹ️ አጠቃቀም ℹ️", "ℹ️ How to Use ℹ️", "ℹ️ Akkamitti fayyadamuu ℹ️"]
    pick_words    = ["❇️ ቁጥር ምረጥ ❇️", "❇️ Pick Numbers ❇️", "❇️ Lakkoofsa Filadhu ❇️"]
    back_words    = ["◀️ ተመለስ", "◀️ Back", "◀️ Deebi'i"]
    support_words = ["💬 Support"]
    feedback_words = ["💬 አስተያየት መስጫ", "💬 Send Feedback", "💬 Yaada Ergi"]

    if any(w in text for w in home_words):
        ctx.user_data["admin_action"] = None
        ctx.user_data["admin_menu"]   = False
        await show_home(update, ctx)
        return

    if any(w in text for w in cancel_words):
        selected = ctx.user_data.get("selected", [])
        if selected:
            await db.free_tickets(selected)
        ctx.user_data["admin_action"] = None
        ctx.user_data["admin_menu"]   = False
        ctx.user_data["selected"]     = []
        await update.message.reply_text("❌", reply_markup=remove_menu())
        await show_home(update, ctx)
        return

    if any(w in text for w in tickets_words):
        await show_my_tickets(update, ctx)
        return

    if any(w in text for w in feedback_words):
        lang = ctx.user_data.get("lang", "am")
        ctx.user_data["awaiting_feedback"] = True
        await update.message.reply_text(T[lang]["feedback_prompt"], parse_mode="Markdown")
        return

    if any(w in text for w in support_words):
        await show_support_menu(update, ctx)
        return

    if any(w in text for w in info_words):
        lang = ctx.user_data.get("lang", "am")
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(T[lang]["back_home_btn"]), KeyboardButton(T[lang]["mainmenu_btn"])]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            T[lang]["info_text"], parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    if any(w in text for w in admin_words):
        if is_admin(update.effective_user.id):
            await show_admin_panel(update, ctx)
        return

    if any(w in text for w in pick_words):
        return

    # ── አድሚን ◀️ ተመለስ (ወደ admin panel፣ Home አይደለም) ──
    if any(w in text for w in back_words) and is_admin(update.effective_user.id):
        await show_admin_panel(update, ctx)
        return

    if is_admin(update.effective_user.id):
        if "📤 SEND TO GROUP 📤" in text:
            await admin_send_list_msg(update, ctx)
            return
        if "📢 BROADCAST 📢" in text:
            await admin_broadcast_msg(update, ctx)
            return
        if "⚙️ SETTING ⚙️" in text:
            await show_settings_menu(update, ctx)
            return
        if "CHANGE NUMBER 🔢" in text:
            ctx.user_data["admin_action"] = "set_tickets"
            await update.message.reply_text("🔢 አዲስ የቁጥሮች ብዛት ፃፍ (10-2000):")
            return
        if "CHANGE PRICE 💰" in text:
            ctx.user_data["admin_action"] = "set_price"
            await update.message.reply_text("💰 አዲስ ዋጋ ፃፍ (ETB):")
            return
        if "PRIZE 1️⃣" in text:
            ctx.user_data["admin_action"] = "set_prize_1"
            await update.message.reply_text("🥇 1ኛ ሽልማት ፃፍ:")
            return
        if "PRIZE 2️⃣" in text:
            ctx.user_data["admin_action"] = "set_prize_2"
            await update.message.reply_text("🥈 2ኛ ሽልማት ፃፍ:")
            return
        if "PRIZE 3️⃣" in text:
            ctx.user_data["admin_action"] = "set_prize_3"
            await update.message.reply_text("🥉 3ኛ ሽልማት ፃፍ:")
            return
        if "CHANGE IMAGE 🖼" in text:
            ctx.user_data["admin_action"] = "set_home_image"
            await update.message.reply_text("🖼 አዲስ ምስል (ፎቶ) ላክ፦ Home ገጽ ላይ ይታያል።")
            return
        if "REMOVE IMAGE 🗑" in text:
            await db.set_setting("home_image", "")
            await update.message.reply_text("✅ ምስል ተሰርዟል።")
            return
        if "⚠️ RESET ⚠️" in text:
            await update.message.reply_text(
                "⚠️ *እርግጠኛ ነህ? ሁሉም ቁጥሮች እና ክፍያዎች ይጠፋሉ!*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ አዎ Reset", callback_data="admin_reset_yes")],
                    [InlineKeyboardButton("✖️ አይ",      callback_data="admin_panel")]
                ])
            )
            return

    if ctx.user_data.get("admin_action"):
        await handle_text_input(update, ctx)
    elif not ctx.user_data.get("lang"):
        await show_home(update, ctx)

# ══════════════════════════════════════════
# MY TICKETS
# ══════════════════════════════════════════
async def show_my_tickets(update, ctx):
    user      = update.effective_user
    lang      = ctx.user_data.get("lang", "am")
    confirmed = await db.get_user_tickets(user.id, "taken")
    pending_t = await db.get_user_tickets(user.id, "reserved")
    price     = int(await db.get_setting("ticket_price"))
    username  = user.full_name or user.username or "—"

    if not confirmed and not pending_t:
        reply_text = T[lang]["no_tickets"]
    else:
        reply_text = T[lang]["my_tickets_hdr"] + "\n"
        if confirmed:
            nums  = sorted([r[0] for r in confirmed])
            total = len(nums) * price
            reply_text += "\n" + T[lang]["my_tickets_body"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums),
                total=total
            )
        if pending_t:
            nums  = sorted([r[0] for r in pending_t])
            total = len(nums) * price
            reply_text += "\n" + T[lang]["my_tickets_pending"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums),
                total=total
            )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(T[lang]["referral_btn"],  callback_data="show_referral")],
        [InlineKeyboardButton(T[lang]["back_home_btn"], callback_data="main_menu")],
    ])
    await update.message.reply_text(reply_text, parse_mode="Markdown", reply_markup=keyboard)

# ══════════════════════════════════════════
# PAYMENT FLOW — numbers arrive from index.html, payment itself is
# handled entirely in payment.html (separate Mini App) + Flask endpoints
# above (/payment-config, /submit-payment). This handler only locks the
# numbers and hands off to the payment Mini App via a WebApp button.
# ══════════════════════════════════════════
async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
    except Exception as e:
        logger.error(f"WebApp data parse error: {e}")
        return

    if data.get("action") != "buy_tickets":
        return

    numbers = data.get("numbers", [])
    if not numbers:
        return

    price       = int(await db.get_setting("ticket_price"))
    total_price = len(numbers) * price

    for num in numbers:
        ticket = await db.get_ticket(num)
        if ticket and ticket[4] in ("taken", "reserved", "pending_payment"):
            await update.message.reply_text(t(ctx, "num_taken", num=num))
            return

    user     = update.effective_user
    username = f"@{user.username}" if user.username else (user.full_name or "—")
    await db.lock_tickets_pending_payment(numbers, user.id, username)

    ctx.user_data["selected"] = numbers

    lang     = ctx.user_data.get("lang", "am")
    nums_str = ",".join(map(str, sorted(numbers)))

    # ቀድሞ የተጋራው ኮንታክት (ስም/ስልክ) ካለ payment mini app ላይ ቅድመ-ሙላ ይደረጋል
    profile    = await db.get_profile(user.id)
    first_name = profile.get("first_name", "") if profile else ""
    last_name  = profile.get("last_name", "") if profile else ""
    phone      = profile.get("phone", "") if profile else ""

    payment_url = (
        f"{PAYMENT_APP_URL}"
        f"?numbers={nums_str}&total={total_price}&user_id={user.id}"
        f"&username={quote(username)}&lang={lang}"
        f"&first_name={quote(first_name)}&last_name={quote(last_name)}&phone={quote(phone)}"
    )

    text = t(ctx, "payment_intro",
             nums=", ".join(map(str, sorted(numbers))),
             count=len(numbers),
             total=total_price)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            PAYMENT_CONTINUE_TEXT.get(lang, PAYMENT_CONTINUE_TEXT["am"]),
            web_app=WebAppInfo(url=payment_url)
        )],
        [InlineKeyboardButton(t(ctx, "pay_back_btn"), callback_data="main_menu")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

# ══════════════════════════════════════════
# APPROVE / REJECT
# ══════════════════════════════════════════
async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    action, payment_id = query.data.split("_", 1)
    payment_id = int(payment_id)
    payment    = await db.get_payment(payment_id)
    if not payment:
        return

    p_id      = payment[0]
    p_user_id = payment[1]
    p_username= payment[2]
    p_phone   = payment[3]
    p_numbers = payment[4]
    p_receipt = payment[5]
    p_method  = payment[6]
    p_status  = payment[7]
    full_name = payment[8] if payment[8] else p_username

    if p_status != "pending":
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except:
            pass
        await query.answer("Already reviewed!", show_alert=True)
        return

    numbers     = list(map(int, p_numbers.split(",")))
    price       = int(await db.get_setting("ticket_price"))
    total_price = len(numbers) * price
    total       = int(await db.get_setting("total_tickets"))
    user_lang   = "am"

    if action == "approve":
        await db.update_payment_status(payment_id, "approved", update.effective_user.id)
        await db.confirm_tickets(numbers, p_user_id, p_username, p_phone)

        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=T[user_lang]["approved"].format(
                    nums=", ".join(map(str, sorted(numbers))),
                    total=total_price
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User approved notify: {e}")

        try:
            await query.edit_message_caption(
                caption=(f"✅ <b>Approved</b>\n"
                         f"👤 {full_name}\n"
                         f"🔗 {p_username}\n📞 {p_phone}\n"
                         f"🎟 {p_numbers}\n💰 {total_price} ETB"),
                parse_mode="HTML", reply_markup=None
            )
        except Exception as e:
            logger.error(f"Edit caption: {e}")

        try:
            asyncio.create_task(schedule_group_list_update(ctx.bot, total))
        except Exception as e:
            logger.error(f"Group update schedule error: {e}")

        try:
            asyncio.create_task(announce_sold_numbers(ctx.bot, numbers))
        except Exception as e:
            logger.error(f"Sold announce schedule error: {e}")

        taken = await db.count_taken_tickets()
        if taken >= total:
            for admin_id in ADMIN_IDS:
                try:
                    await ctx.bot.send_message(
                        chat_id=admin_id,
                        text=f"🎊 *All tickets sold!* {taken}/{total}",
                        parse_mode="Markdown"
                    )
                except:
                    pass
    else:
        await db.update_payment_status(payment_id, "rejected", update.effective_user.id)
        await db.free_tickets(numbers)

        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=T[user_lang]["rejected"].format(
                    nums=", ".join(map(str, sorted(numbers)))
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User rejected notify: {e}")

        try:
            await query.edit_message_caption(
                caption=(f"❌ <b>Rejected</b>\n"
                         f"👤 {full_name}\n"
                         f"🔗 {p_username}\n📞 {p_phone}\n🎟 {p_numbers}"),
                parse_mode="HTML", reply_markup=None
            )
        except Exception as e:
            logger.error(f"Edit caption: {e}")

# ══════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════
async def show_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    total         = int(await db.get_setting("total_tickets"))
    taken         = await db.count_taken_tickets()
    pending_list  = await db.get_pending_payments()
    pending_count = len(pending_list)
    price         = int(await db.get_setting("ticket_price"))
    total_revenue = taken * price

    text = (
        f"🔰 *ADMIN PANEL* 🔰\n"
        f"━━━━━━━━━━━━━━━\n"
        f"የትኬት ብዛት = {total}\n"
        f"የተሸጠ = {taken}\n"
        f"ቀሪ = {total - taken}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"ገቢ = {total_revenue:,} ብር\n"
        f"በሂደት ላይ ያለ = {pending_count}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"for admin only!"
    )

    inline_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⏳ Pending ({pending_count})", callback_data="admin_pending"),
            InlineKeyboardButton("📊 STATISTICS",                 callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("🔍 SEARCH",  callback_data="admin_find"),
            InlineKeyboardButton("📋 CARDS",   web_app=WebAppInfo(url=f"{PUBLIC_URL}/admin.html"))
        ],
    ])

    menu_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📤 SEND TO GROUP 📤")],
        [KeyboardButton("📢 BROADCAST 📢"), KeyboardButton("⚙️ SETTING ⚙️")],
        [KeyboardButton("🏠 Main Menu")],
    ], resize_keyboard=True)

    ctx.user_data["admin_menu"] = True

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=inline_kb)
        except:
            await update.effective_message.reply_text(
                text, parse_mode="Markdown", reply_markup=inline_kb)
        await update.effective_message.reply_text(
            "━━━━━━━━━━━",
            reply_markup=menu_kb
        )
    else:
        await update.effective_message.reply_text(
            text, parse_mode="Markdown", reply_markup=inline_kb)
        await update.effective_message.reply_text(
            "━━━━━━━━━━━",
            reply_markup=menu_kb
        )


async def admin_panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await show_admin_panel(update, ctx)

# ── Settings menu ──
async def show_settings_menu(update, ctx):
    price  = await db.get_setting("ticket_price")
    total  = await db.get_setting("total_tickets")
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")
    home_image = await db.get_setting("home_image")
    image_status = "✅ ተቀናብሯል" if home_image else "❌ የለም"

    text = (
        f"⚙️ *SETTING* ⚙️\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔢 ቁጥሮች: {total}\n"
        f"💰 ዋጋ: {price} ETB\n"
        f"🥇 {prize1}\n🥈 {prize2}\n🥉 {prize3}\n"
        f"🖼 Home ምስል: {image_status}"
    )
    # ◀️ ተመለስ / 🏠 Main Menu ከስር ተቀምጠዋል (አድሚን ከዚህ ስክሪን ለመውጣት /start መተየብ እንዳይኖርበት)
    settings_kb = ReplyKeyboardMarkup([
        [KeyboardButton("CHANGE NUMBER 🔢"), KeyboardButton("CHANGE PRICE 💰")],
        [KeyboardButton("PRIZE 1️⃣"), KeyboardButton("PRIZE 2️⃣"), KeyboardButton("PRIZE 3️⃣")],
        [KeyboardButton("CHANGE IMAGE 🖼"), KeyboardButton("REMOVE IMAGE 🗑")],
        [KeyboardButton("⚠️ RESET ⚠️")],
        [KeyboardButton("◀️ ተመለስ"), KeyboardButton("🏠 Main Menu")],
    ], resize_keyboard=True)

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=settings_kb)

# ── Admin panel inline callbacks ──
async def admin_pending_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    pending = await db.get_pending_payments()
    if not pending:
        await query.edit_message_text(
            "✅ No pending payments.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back", callback_data="admin_panel")
            ]])
        )
        return
    price = int(await db.get_setting("ticket_price"))
    await query.edit_message_text(
        f"⏳ Sending *{len(pending)}* pending payments to DM...",
        parse_mode="Markdown"
    )
    for p in pending:
        p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status = p[:8]
        numbers     = list(map(int, p_numbers.split(",")))
        total_price = len(numbers) * price
        caption = (
            f"💳 <b>#{p_id}</b>\n{'─'*20}\n"
            f"👤 {p_username}\n📞 {p_phone}\n"
            f"🎫 {p_numbers}\n"
            f"💰 {total_price} ETB | {p_method}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{p_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{p_id}")
        ]])
        try:
            await ctx.bot.send_photo(chat_id=update.effective_user.id,
                                     photo=p_receipt, caption=caption,
                                     parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Pending send error: {e}")
        await asyncio.sleep(0.3)

async def admin_stats_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total         = int(await db.get_setting("total_tickets"))
    taken         = await db.count_taken_tickets()
    price         = int(await db.get_setting("ticket_price"))
    today_count   = await db.count_tickets_today()
    pending_count = len(await db.get_pending_payments())
    reserved      = await db.count_pending_tickets()
    percent       = round((taken / total) * 100, 1) if total > 0 else 0
    filled        = int(percent / 10)
    bar           = "█" * filled + "░" * (10 - filled)

    text = (
        f"📊 *STATISTICS*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎟 Total Tickets: *{total}*\n"
        f"✅ Approved (Sold): *{taken}*\n"
        f"⏳ Reserved (Pending): *{reserved}*\n"
        f"🆓 Free: *{total - taken - reserved}*\n"
        f"⌛ Pending Payments: *{pending_count}*\n"
        f"📅 Today Approved: *{today_count}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 Sales Progress:\n"
        f"[{bar}] {percent}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Approved Revenue: *{taken * price:,} ETB*\n"
        f"⏳ Pending Revenue: *{pending_count * price:,} ETB*\n"
        f"💎 Total Possible: *{total * price:,} ETB*"
    )
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back", callback_data="admin_panel")
        ]])
    )

async def admin_find_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["admin_action"] = "find_ticket"
    await query.edit_message_text(
        "🔍 *SEARCH*\n━━━━━━━━━━━━━━━\nየቲኬት ቁጥር ፃፍ:\nምሳሌ: 5",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Cancel", callback_data="admin_panel")
        ]])
    )

async def watch_pending_payments(bot, interval_seconds=30, max_age_seconds=300):
    """በየ30 ሰከንድ ይፈትሻል፣ 5 ደቂቃ ካለፈ ቁጥሩን free ያደርጋል + ለተጠቃሚው ያሳውቃል"""
    while True:
        try:
            released = await db.release_expired_pending(max_age_seconds)
            for num, user_id in released:
                if not user_id:
                    continue
                try:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=(
                            f"⏳ የቁጥር {num} ማስያዣ ጊዜ አልቋል።\n"
                            f"ደረሰኝ ስላልደረሰን ቁጥሩ ነፃ ወጥቷል። እንደገና ይምረጡ።"
                        )
                    )
                except Exception as e:
                    logger.warning(f"Notify release failed for {user_id}: {e}")
        except Exception as e:
            logger.error(f"watch_pending_payments error: {e}")
        await asyncio.sleep(interval_seconds)

# ── Send to Group ──
async def admin_send_list_msg(update, ctx):
    if not is_admin(update.effective_user.id):
        return
    total = int(await db.get_setting("total_tickets"))
    await update.message.reply_text("⏳ Sending to group...")

    async def _runner():
        try:
            count = await send_full_list_to_group(ctx.bot, total)
            await ctx.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ {count} messages updated in group!"
            )
        except Exception as e:
            logger.error(f"admin_send_list_msg error: {e}")
            await ctx.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Group update failed."
            )

    asyncio.create_task(_runner())

# ── Broadcast ──
async def admin_broadcast_msg(update, ctx):
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "broadcast"
    await update.message.reply_text(
        "📢 *BROADCAST*\n━━━━━━━━━━━━━━━\nWrite the message to send to all users + group:",
        parse_mode="Markdown"
    )

async def admin_broadcast_edit_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "broadcast"
    await query.edit_message_text(
        "📢 *BROADCAST*\n━━━━━━━━━━━━━━━\nWrite the message to send to all users + group:",
        parse_mode="Markdown"
    )

async def broadcast_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    msg   = ctx.user_data.get("broadcast_msg", "")
    users = await db.get_all_users()
    sent, failed = 0, 0
    for (uid,) in users:
        try:
            await ctx.bot.send_message(chat_id=uid, text=f"📢 {msg}")
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast failed for user {uid}: {e}")
        await asyncio.sleep(0.05)

    try:
        await ctx.bot.send_message(chat_id=GROUP_ID, text=f"📢 {msg}")
    except Exception as e:
        logger.error(f"Group broadcast: {e}")

    await query.edit_message_text(
        f"✅ Sent to {sent} users + group!\n⚠️ Failed: {failed}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
        ]])
    )

# ── Reset ──
async def admin_reset_yes_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await db.reset_lottery()
    await query.edit_message_text(
        "✅ *New lottery started!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")
        ]])
    )

# ══════════════════════════════════════════
# REFERRAL
# ══════════════════════════════════════════
async def referral_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user         = update.effective_user
    lang         = ctx.user_data.get("lang", "am")
    bot_username = (await ctx.bot.get_me()).username
    ref_link     = f"https://t.me/{bot_username}?start=ref_{user.id}"
    count        = await db.get_referral_count(str(user.id))
    reward       = count * 2

    text = T[lang]["referral_info"].format(link=ref_link, count=count, reward=reward)
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(T[lang]["back_home_btn"], callback_data="main_menu")
        ]])
    )

# ══════════════════════════════════════════
# TEXT INPUT HANDLER (admin actions only — payment info now
# collected entirely inside payment.html, not via chat text)
# ══════════════════════════════════════════
async def handle_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()

    action = ctx.user_data.get("admin_action")
    if not action or not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = None

    if action == "find_ticket":
        try:
            num = int(text_input)
        except:
            await update.message.reply_text("⚠️ ቁጥር ብቻ ፃፍ።")
            return
        payment = await db.find_payment_by_number(num)
        if not payment:
            await update.message.reply_text(f"❌ ቁጥር {num} ምንም መረጃ የለም።")
            return

        p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status, p_reviewed_at = payment
        full_payment = await db.get_payment(p_id)
        full_name    = full_payment[8] if full_payment and full_payment[8] else p_username

        price_val    = int(await db.get_setting("ticket_price"))
        nums_list    = list(map(int, p_numbers.split(",")))
        total_price  = len(nums_list) * price_val
        status_label = {
            "pending":  "⏳ Pending",
            "approved": "✅ Approved",
            "rejected": "❌ Rejected"
        }.get(p_status, p_status)

        caption = (
            f"🔍 <b>Ticket {num} Search</b>\n"
            f"{'─'*20}\n"
            f"💳 Payment #{p_id}\n"
            f"👤 <b>{full_name}</b>\n"
            f"🔗 {p_username}\n"
            f"📞 {p_phone}\n"
            f"🎟 {p_numbers}\n"
            f"💰 {total_price} ETB | {p_method}\n"
            f"📊 {status_label}"
        )
        kb = []
        if p_status == "pending":
            kb.append([
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{p_id}"),
                InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{p_id}")
            ])
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        try:
            await ctx.bot.send_photo(chat_id=update.effective_user.id,
                                     photo=p_receipt, caption=caption,
                                     parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text(caption, parse_mode="HTML",
                                            reply_markup=InlineKeyboardMarkup(kb))
        return

    if action == "set_tickets":
        try:
            val = int(text_input)
            if 10 <= val <= 2000:
                await db.set_setting("total_tickets", val)
                await update.message.reply_text(f"✅ Tickets → {val}")
            else:
                await update.message.reply_text("⚠️ 10-2000 ፃፍ።")
        except:
            await update.message.reply_text("⚠️ ቁጥር ብቻ።")

    elif action == "set_price":
        try:
            val = int(text_input)
            await db.set_setting("ticket_price", val)
            await update.message.reply_text(f"✅ Price → {val} ETB")
        except:
            await update.message.reply_text("⚠️ ቁጥር ብቻ።")

    elif action in ["set_prize_1", "set_prize_2", "set_prize_3"]:
        key = action.replace("set_", "")
        await db.set_setting(key, text_input)
        await update.message.reply_text(f"✅ {text_input}")

    elif action == "broadcast":
        ctx.user_data["broadcast_msg"] = text_input
        await update.message.reply_text(
            f"📋 *Preview:*\n━━━━━━━━━━━━━━━\n📢 {text_input}\n━━━━━━━━━━━━━━━\nSend to all + group?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Send", callback_data="broadcast_confirm")],
                [InlineKeyboardButton("✏️ Edit",      callback_data="admin_broadcast")],
                [InlineKeyboardButton("✖️ Cancel",    callback_data="admin_panel")]
            ])
        )

# ══════════════════════════════════════════
# ADMIN PHOTO HANDLER (home banner image upload)
# ══════════════════════════════════════════
async def admin_photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if ctx.user_data.get("admin_action") != "set_home_image":
        return
    photo = update.message.photo[-1]
    await db.set_setting("home_image", photo.file_id)
    ctx.user_data["admin_action"] = None
    await update.message.reply_text("✅ Home ምስል ተቀናብሯል!")

# ══════════════════════════════════════════
# MY TICKETS (inline callback)
# ══════════════════════════════════════════
async def my_tickets_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user     = update.effective_user
    lang     = ctx.user_data.get("lang", "am")
    confirmed= await db.get_user_tickets(user.id, "taken")
    pending_t= await db.get_user_tickets(user.id, "reserved")
    price    = int(await db.get_setting("ticket_price"))
    username = user.full_name or user.username or "—"

    if not confirmed and not pending_t:
        text = T[lang]["no_tickets"]
    else:
        text = T[lang]["my_tickets_hdr"] + "\n"
        if confirmed:
            nums  = sorted([r[0] for r in confirmed])
            total = len(nums) * price
            text += "\n" + T[lang]["my_tickets_body"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums), total=total
            )
        if pending_t:
            nums  = sorted([r[0] for r in pending_t])
            total = len(nums) * price
            text += "\n" + T[lang]["my_tickets_pending"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums), total=total
            )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(T[lang]["referral_btn"],  callback_data="show_referral")],
        [InlineKeyboardButton(T[lang]["back_home_btn"], callback_data="main_menu")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)

# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════
async def post_init(application):
    await db.init_db()
    asyncio.create_task(watch_pending_payments(application.bot))

def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("language", language_cmd))

    async def admin_cmd(update, ctx):
        if is_admin(update.effective_user.id):
            await show_admin_panel(update, ctx)
    app.add_handler(CommandHandler("admin", admin_cmd))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(lang_cb,              pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(home_cb,              pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(my_tickets_cb,        pattern="^my_tickets$"))
    app.add_handler(CallbackQueryHandler(referral_cb,          pattern="^show_referral$"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb,    pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(check_membership_cb,  pattern="^check_membership$"))

    app.add_handler(CallbackQueryHandler(admin_panel_cb,       pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_pending_cb,     pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_stats_cb,       pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_find_cb,        pattern="^admin_find$"))
    app.add_handler(CallbackQueryHandler(admin_reset_yes_cb,   pattern="^admin_reset_yes$"))
    app.add_handler(CallbackQueryHandler(broadcast_confirm_cb, pattern="^broadcast_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_edit_cb, pattern="^admin_broadcast$"))

    # Message handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.PHOTO, admin_photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message_home))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
