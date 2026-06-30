import logging
import asyncio
import requests as req_lib
from threading import Thread
from flask import Flask, Response
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
# CONFIG — ግሩፕ membership
# ══════════════════════════════════════════
try:
    from config import REQUIRED_GROUP_LINK
except ImportError:
    REQUIRED_GROUP_LINK = f"https://t.me/c/{str(GROUP_ID).replace('-100', '')}"

flask_app = Flask('', static_folder='.', static_url_path='')

@flask_app.route('/')
def home():
    return "Bot is alive! 🤖"

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
            "ክፍያ ለመፈጸም ከስር ካሉት 👇\n"
            "💳 የክፍያ አማራጮች አንዱን\n"
            "በመምረጥ ክፍያ ይፈፅሙ!"
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

        "my_tickets_hdr": "🌟 *የኔ ትኬቶች* 🌟",
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
            "🌟 *የኔ ትኬቶች* 🌟\n"
            "━━━━━━━━━━━━━━━\n"
            "ምንም ትኬት የለዎትም።"
        ),
        "referral_btn": "👥 Referral",
        "back_home_btn": "🔙 ተመለስ",

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
            "ℹ️ *አጠቃቀም መመሪያ*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ *➕ ቁጥር ምረጥ* — ቁጥሮቾን ከ WebApp ይምረጡ\n"
            "2️⃣ *ክፍያ* — CBE ወይም Telebirr ይምረጡ\n"
            "3️⃣ *ደረሰኝ ላክ* — Screenshot ይላኩ\n"
            "4️⃣ *ስም እና ስልክ* — መረጃዎን ይሙሉ\n"
            "5️⃣ *አረጋግጥ* — አድሚን ያረጋግጥልዎታል\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *ማሳሰቢያ:*\n"
            "— ትክክለኛ ደረሰኝ ብቻ ተቀባይነት ይኖረዋል\n"
            "— ደረሰኝ ከቀየሩ ወይም ትርጉም የሌለው\n"
            "  ፎቶ ከላኩ ያለ notification ውድቅ ይሆናል"
        ),

        "num_taken": "⚠️ ቁጥር {num} ቀድሞ ተይዟል! እንደገና ይምረጡ።",
    },

    "en": {
        "pick_btn":       "➕ Pick Numbers ➕",
        "my_tickets_btn": "🌟 My Tickets 🌟",
        "info_btn":       "ℹ️ How to Use ℹ️",
        "admin_btn":      "🎴 ADMIN 🎴",
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
            "\" ➕ Pick Numbers ➕ \""
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
            "Choose your payment method 👇"
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

        "my_tickets_hdr": "🌟 *My Tickets* 🌟",
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
            "🌟 *My Tickets* 🌟\n"
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
            "ℹ️ *How to Use*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ *➕ Pick Numbers* — Select from WebApp\n"
            "2️⃣ *Payment* — Choose CBE or Telebirr\n"
            "3️⃣ *Send Receipt* — Send screenshot\n"
            "4️⃣ *Name & Phone* — Fill your info\n"
            "5️⃣ *Confirm* — Admin will verify\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *Note:* Only valid receipts are accepted."
        ),

        "num_taken": "⚠️ Number {num} is already taken! Please pick again.",
    },

    "or": {
        "pick_btn":       "➕ Lakkoofsa Filadhu ➕",
        "my_tickets_btn": "🌟 Tikeetii Koo 🌟",
        "info_btn":       "ℹ️ Akkamitti fayyadamuu ℹ️",
        "admin_btn":      "🎴 ADMIN 🎴",
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
            "cuqaasi 👇 \" ➕ Lakkoofsa Filadhu ➕ \""
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
            "Mala kaffaltii filadhu 👇"
        ),
        "pay_cbe_btn":      "🏦 CBE",
        "pay_telebirr_btn": "📱 TELE BIRR",
        "pay_back_btn":     "🔙 Deebi'i",

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
        "back_home_btn": "🔙 Deebi'i",

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
            "ℹ️ *Akkamitti itti fayyadamuu*\n"
            "━━━━━━━━━━━━━━━\n"
            "1️⃣ *➕ Lakkoofsa Filadhu* — WebApp irraa filadhu\n"
            "2️⃣ *Kaffaltii* — CBE ykn Telebirr filadhu\n"
            "3️⃣ *Beeksisa Ergi* — Screenshot ergi\n"
            "4️⃣ *Maqaa fi Bilbila* — Odeeffannoo guuti\n"
            "5️⃣ *Mirkaneessi* — Admin si beeksisa\n"
            "━━━━━━━━━━━━━━━\n"
            "📌 *Yaadadhu:* Beeksisa sirrii qofa fudhatama."
        ),

        "num_taken": "⚠️ Lakkoofsi {num} fudhataame! Ammas filadhu.",
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
    if len(phone) < 2:
        return phone
    return phone[:-1] + "#"

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

async def send_join_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ ቀላቅሉ ማሳወቂያ ይላካል"""
    lang = ctx.user_data.get("lang", "am")

    # ── FIX: ቀደም ሲል የነበረውን ReplyKeyboard (የግርጌ ቁልፎች) አስቀድሞ አስወግድ ──
    # ግሩፑን እስኪቀላቀል ድረስ "ቁጥር ምረጥ", "የኔ ትኬቶች", "ዋና ገጽ" ወዘተ የሚሉ
    # የግርጌ ቁልፎች በስክሪኑ ስር እንዳይታዩ
    await update.effective_message.reply_text(
        "⏳",
        reply_markup=ReplyKeyboardRemove()
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(T[lang]["join_btn"], url=REQUIRED_GROUP_LINK)],
        [InlineKeyboardButton(T[lang]["joined_btn"], callback_data="check_membership")],
    ])
    await update.effective_message.reply_text(
        T[lang]["join_required"],
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ══════════════════════════════════════════
# GROUP LIST
# ══════════════════════════════════════════
async def send_full_list_to_group(bot, total):
    old_msgs = await db.get_group_message_ids()
    for msg_id, chat_id in old_msgs:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Delete old group msg error: {e}")
    await db.clear_group_messages()

    ticket_map = await db.get_all_tickets_full(total)
    CHUNK = 40
    new_msg_ids = []
    for chunk_start in range(1, total + 1, CHUNK):
        chunk_end = min(chunk_start + CHUNK - 1, total)
        lines = []
        for n in range(chunk_start, chunk_end + 1):
            info = ticket_map.get(n)
            if info and info[1] == "taken":
                lines.append(f"{n} 👉 {mask_phone(info[0])} ✅")
            else:
                lines.append(f"{n} 👉")
        text = "\n".join(lines)
        try:
            msg = await bot.send_message(chat_id=GROUP_ID, text=text)
            new_msg_ids.append(msg.message_id)
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Chunk send error: {e}")

    await db.save_group_message_ids(GROUP_ID, new_msg_ids)
    return len(new_msg_ids)

# ══════════════════════════════════════════
# START / LANGUAGE
# ══════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args

    # ── Receipt deep link (admin only) ──
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

    # ── Referral ──
    if args and args[0].startswith("ref_"):
        referrer_id = args[0].replace("ref_", "")
        if referrer_id != str(user.id):
            await db.add_referral(referrer_id, str(user.id))

    # ── Language: first time → language picker ──
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

    # ── Membership check (admin ሳይሆን) ──
    if not is_admin(user.id):
        if not await is_member_of_group(ctx.bot, user.id):
            await send_join_prompt(update, ctx)
            return

    await show_home(update, ctx)


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

    # ── ቋንቋ ከተመረጠ በኋላም membership check ──
    user = update.effective_user
    if not is_admin(user.id):
        if not await is_member_of_group(ctx.bot, user.id):
            await send_join_prompt(update, ctx)
            return

    await show_home(update, ctx)


# ══════════════════════════════════════════
# CHECK MEMBERSHIP CALLBACK
# ══════════════════════════════════════════
async def check_membership_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = update.effective_user

    if await is_member_of_group(ctx.bot, user.id):
        await query.answer()
        try:
            await query.delete_message()
        except:
            pass
        await show_home(update, ctx)
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
        [KeyboardButton(t(ctx, "info_btn"))],
    ]
    if is_admin(user.id):
        rows.append([KeyboardButton(t(ctx, "admin_btn"))])
    reply_markup = ReplyKeyboardMarkup(rows, resize_keyboard=True)

    if update.callback_query:
        try:
            await update.callback_query.delete_message()
        except:
            pass

    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def home_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["waiting_receipt"] = False
    ctx.user_data["waiting_name"]    = False
    ctx.user_data["waiting_phone"]   = False
    ctx.user_data["admin_action"]    = None
    ctx.user_data["admin_menu"]      = False
    await show_home(update, ctx)

# ══════════════════════════════════════════
# MESSAGE ROUTER
# ══════════════════════════════════════════
async def any_message_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    home_words    = ["ዋና ገጽ", "Home", "Fuula Jalqabaa"]
    cancel_words  = ["❌ ሰርዝ", "❌ Cancel", "❌ Haquu"]
    tickets_words = ["🌟 የኔ ትኬቶች 🌟", "🌟 My Tickets 🌟", "🌟 Tikeetii Koo 🌟",
                     "✴️ የኔ ትኬቶች ✴️"]
    admin_words   = ["🔰 ADMIN 🔰", "🎴 ADMIN 🎴"]
    info_words    = ["ℹ️ አጠቃቀም ℹ️", "ℹ️ How to Use ℹ️", "ℹ️ Akkamitti fayyadamuu ℹ️"]
    pick_words    = ["❇️ ቁጥር ምረጥ ❇️", "➕ Pick Numbers ➕", "➕ Lakkoofsa Filadhu ➕"]

    if any(w in text for w in home_words):
        ctx.user_data["waiting_name"]    = False
        ctx.user_data["waiting_phone"]   = False
        ctx.user_data["waiting_receipt"] = False
        ctx.user_data["admin_action"]    = None
        ctx.user_data["admin_menu"]      = False
        await show_home(update, ctx)
        return

    if any(w in text for w in cancel_words):
        ctx.user_data["waiting_name"]    = False
        ctx.user_data["waiting_phone"]   = False
        ctx.user_data["waiting_receipt"] = False
        ctx.user_data["admin_action"]    = None
        ctx.user_data["admin_menu"]      = False
        await update.message.reply_text("❌", reply_markup=remove_menu())
        await show_home(update, ctx)
        return

    if any(w in text for w in tickets_words):
        await show_my_tickets(update, ctx)
        return

    if any(w in text for w in info_words):
        lang = ctx.user_data.get("lang", "am")
        await update.message.reply_text(T[lang]["info_text"], parse_mode="Markdown")
        return

    if any(w in text for w in admin_words):
        if is_admin(update.effective_user.id):
            await show_admin_panel(update, ctx)
        return

    if any(w in text for w in pick_words):
        return

    # ── Admin menu button handlers ──
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
            await update.message.reply_text("🔢 አዲስ የቁጥሮች ብዛት ፃፍ (10-800):")
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

    if ctx.user_data.get("waiting_name") or ctx.user_data.get("waiting_phone") or ctx.user_data.get("admin_action"):
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
# PAYMENT FLOW
# ══════════════════════════════════════════
async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import json
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
        if ticket and ticket[4] in ("taken", "reserved"):
            await update.message.reply_text(t(ctx, "num_taken", num=num))
            return

    ctx.user_data["selected"]        = numbers
    ctx.user_data["waiting_name"]    = False
    ctx.user_data["waiting_phone"]   = False
    ctx.user_data["waiting_receipt"] = False

    lang = ctx.user_data.get("lang", "am")
    text = T[lang]["payment_intro"].format(
        nums=", ".join(map(str, sorted(numbers))),
        count=len(numbers),
        total=total_price
    )
    keyboard = [
        [InlineKeyboardButton(T[lang]["pay_cbe_btn"],      callback_data="pay_cbe")],
        [InlineKeyboardButton(T[lang]["pay_telebirr_btn"], callback_data="pay_telebirr")],
        [InlineKeyboardButton(T[lang]["pay_back_btn"],     callback_data="main_menu")],
    ]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def payment_method_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang   = ctx.user_data.get("lang", "am")
    method = "CBE" if query.data == "pay_cbe" else "Telebirr"
    ctx.user_data["payment_method"]  = method
    ctx.user_data["waiting_receipt"] = True
    ctx.user_data["waiting_name"]    = False
    ctx.user_data["waiting_phone"]   = False
    await query.delete_message()

    selected    = ctx.user_data.get("selected", [])
    price       = int(await db.get_setting("ticket_price"))
    total_price = len(selected) * price

    if method == "CBE":
        text = T[lang]["cbe_msg"].format(
            account=CBE_ACCOUNT, name=CBE_NAME, total=total_price
        )
    else:
        text = T[lang]["telebirr_msg"].format(
            account=TELEBIRR_ACCOUNT, name=TELEBIRR_NAME, total=total_price
        )

    await update.effective_message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=get_cancel_keyboard(ctx)
    )

# ── Receipt ──
async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("waiting_receipt"):
        return
    photo    = update.message.photo
    document = update.message.document
    if not photo and not document:
        await update.message.reply_text(t(ctx, "receipt_only"), parse_mode="Markdown")
        return
    file_id = photo[-1].file_id if photo else document.file_id
    ctx.user_data["receipt_file_id"] = file_id
    ctx.user_data["waiting_receipt"] = False
    ctx.user_data["waiting_name"]    = True
    await update.message.reply_text(t(ctx, "ask_name"), parse_mode="Markdown",
                                    reply_markup=get_cancel_keyboard(ctx))

# ── Confirm send ──
async def confirm_send_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    user      = update.effective_user
    selected  = ctx.user_data.get("selected", [])
    method    = ctx.user_data.get("payment_method", "CBE")
    full_name = ctx.user_data.get("full_name", user.full_name)
    phone     = ctx.user_data.get("user_phone", "")
    file_id   = ctx.user_data.get("receipt_file_id")
    price     = int(await db.get_setting("ticket_price"))
    total_price = len(selected) * price

    for num in selected:
        ticket = await db.get_ticket(num)
        if ticket and ticket[4] == "taken":
            await query.edit_message_text(t(ctx, "num_taken", num=num))
            return

    username   = f"@{user.username}" if user.username else full_name
    payment_id = await db.add_payment(user.id, username, phone, selected, file_id, method, full_name=full_name)
    await db.reserve_tickets(selected, user.id, username, phone)

    await query.edit_message_text(
        t(ctx, "sent_ok", name=full_name, phone=phone,
          nums=", ".join(map(str, sorted(selected))),
          total=total_price, method=method),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t(ctx, "home_btn"), callback_data="main_menu")
        ]])
    )

    tg_username  = f"@{user.username}" if user.username else "—"
    bot_username = (await ctx.bot.get_me()).username

    admin_caption = (
        f"💳 <b>New Payment!</b>\n"
        f"{'─'*20}\n"
        f"👤 <b>{full_name}</b>\n"
        f"🔗 {tg_username}\n"
        f"📞 {phone}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"{'─'*20}\n"
        f"🎟 <b>Numbers:</b> {', '.join(map(str, sorted(selected)))}\n"
        f"📦 <b>Count:</b> {len(selected)}\n"
        f"💰 <b>Total:</b> {total_price} ETB\n"
        f"💳 <b>Method:</b> {method}\n"
        f"🔖 <b>#{payment_id}</b>"
    )

    receipt_link = f"https://t.me/{bot_username}?start=receipt_{payment_id}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{payment_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{payment_id}")
        ],
        [
            InlineKeyboardButton("🧾 ደረሰኝ ይመልከቱ", url=receipt_link)
        ]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(chat_id=admin_id, photo=file_id,
                                     caption=admin_caption, parse_mode="HTML",
                                     reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Admin notify: {e}")

    ctx.user_data["selected"] = []

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
            await send_full_list_to_group(ctx.bot, total)
        except Exception as e:
            logger.error(f"Group update: {e}")

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

    text = (
        f"⚙️ *SETTING* ⚙️\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔢 ቁጥሮች: {total}\n"
        f"💰 ዋጋ: {price} ETB\n"
        f"🥇 {prize1}\n🥈 {prize2}\n🥉 {prize3}"
    )
    settings_kb = ReplyKeyboardMarkup([
        [KeyboardButton("CHANGE NUMBER 🔢"), KeyboardButton("CHANGE PRICE 💰")],
        [KeyboardButton("PRIZE 1️⃣"), KeyboardButton("PRIZE 2️⃣"), KeyboardButton("PRIZE 3️⃣")],
        [KeyboardButton("⚠️ RESET ⚠️")],
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

# ── Send to Group ──
async def admin_send_list_msg(update, ctx):
    if not is_admin(update.effective_user.id):
        return
    total = int(await db.get_setting("total_tickets"))
    await update.message.reply_text("⏳ Sending to group...")
    count = await send_full_list_to_group(ctx.bot, total)
    await update.message.reply_text(f"✅ {count} messages sent to group!")

# ── Broadcast ──
async def admin_broadcast_msg(update, ctx):
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "broadcast"
    await update.message.reply_text(
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
    sent  = 0
    for (uid,) in users:
        try:
            await ctx.bot.send_message(chat_id=uid, text=f"📢 {msg}")
            sent += 1
        except:
            pass
    try:
        await ctx.bot.send_message(chat_id=GROUP_ID, text=f"📢 {msg}")
    except Exception as e:
        logger.error(f"Group broadcast: {e}")
    await query.edit_message_text(
        f"✅ Sent to {sent} users + group!",
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
# TEXT INPUT HANDLER
# ══════════════════════════════════════════
async def handle_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()

    if ctx.user_data.get("waiting_name"):
        ctx.user_data["full_name"]     = text_input
        ctx.user_data["waiting_name"]  = False
        ctx.user_data["waiting_phone"] = True
        await update.message.reply_text(t(ctx, "ask_phone"), parse_mode="Markdown")
        return

    if ctx.user_data.get("waiting_phone"):
        digits = text_input.replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) < 9:
            await update.message.reply_text(t(ctx, "invalid_phone"))
            return
        ctx.user_data["user_phone"]    = digits
        ctx.user_data["waiting_phone"] = False

        selected    = ctx.user_data.get("selected", [])
        method      = ctx.user_data.get("payment_method", "CBE")
        full_name   = ctx.user_data.get("full_name", update.effective_user.full_name)
        price       = int(await db.get_setting("ticket_price"))
        total_price = len(selected) * price
        lang        = ctx.user_data.get("lang", "am")

        preview = T[lang]["preview_msg"].format(
            nums=", ".join(map(str, sorted(selected))),
            name=full_name, phone=digits,
            total=total_price, method=method
        )
        keyboard = [
            [InlineKeyboardButton(t(ctx, "confirm_send"), callback_data="confirm_send")],
            [InlineKeyboardButton(t(ctx, "home_btn"),     callback_data="main_menu")],
        ]
        await update.message.reply_text(preview, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return

    action = ctx.user_data.get("admin_action")
    if not action or not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = None

    # ── Search ticket ──
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
            if 10 <= val <= 800:
                await db.set_setting("total_tickets", val)
                await update.message.reply_text(f"✅ Tickets → {val}")
            else:
                await update.message.reply_text("⚠️ 10-800 ፃፍ።")
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
    app.add_handler(CallbackQueryHandler(payment_method_cb,    pattern="^pay_(cbe|telebirr)$"))
    app.add_handler(CallbackQueryHandler(confirm_send_cb,      pattern="^confirm_send$"))
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

    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_receipt))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message_home))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
