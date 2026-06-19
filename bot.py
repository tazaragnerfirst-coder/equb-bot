import logging
import asyncio
from datetime import date
from threading import Thread
from flask import Flask
import json
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import BadRequest
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Constants ───
PAGE_SIZE = 50          
MAX_TICKETS_PER_USER = 15  

# ─── Keep Alive ───
flask_app = Flask('')
@flask_app.route('/')
def home():
    return "Bot is alive! 🤖"
def keep_alive():
    t = Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080))
    t.daemon = True
    t.start()

# ─── TRANSLATIONS ───
T = {
    "am": {
        "pick_btn": "🎟 ቁጥር ምረጥ",
        "my_tickets_btn": "📋 የእኔ ትኬቶች",
        "admin_btn": "👨‍💼 አድሚን ፓነል",
        "home_btn": "🏠 ዋና ገጽ",
        "cancel_btn": "❌ ሰርዝ",
        "ask_name": "👤 *ሙሉ ስምዎን ይፃፉ:*\nምሳሌ: አበበ ከበደ",
        "ask_phone": "📞 *ስልክ ቁጥርዎን ይፃፉ:*\nምሳሌ: 0911223344",
        "invalid_phone": "⚠️ ትክክለኛ ስልክ ቁጥር ይፃፉ።",
        "ask_receipt": "✅ ክፍያ ከፈፀሙ በኋላ *ደረሰኝ (screenshot)* ይላኩ።",
        "sent_ok": "✅ *ደረሰኝዎ ተልኳል!*\n⏳ አድሚን ሲያረጋግጥ notification ይደርስዎታል።",
        "approved": "🎉 *ክፍያዎ ተረጋግጧል!*\n🎟 ቁጥሮቾ: {nums}\n💰 {total} ብር",
        "rejected": "❌ *ክፍያዎ አልተረጋገጠም።*",
        "my_tickets_title": "🎟 *የእኔ ትኬቶች*",
        "no_tickets": "ምንም ትኬት የለዎትም።",
        "confirmed_label": "✅ የተረጋገጡ",
        "pending_label": "⏳ በሂደት",
    }
}

def t(ctx, key, **kwargs):
    lang = ctx.user_data.get("lang", "am")
    template = T.get(lang, T["am"]).get(key, key)
    try:
        return template.format(**kwargs)
    except:
        return template

def is_admin(user_id):
    return user_id in ADMIN_IDS

def mask_phone(phone):
    phone = str(phone).strip()
    return phone + "#" if phone else ""

# ─────────────────────────────────────────
# WEB APP DATA HANDLER (Mini App → Bot)
# ─────────────────────────────────────────
async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
    except:
        return

    if data.get("action") != "buy_tickets":
        return

    numbers = data.get("numbers", [])
    if not numbers:
        return

    price = await db.get_setting("ticket_price")
    total_price = len(numbers) * int(price)

    # Check availability
    for num in numbers:
        ticket = await db.get_ticket(num)
        if ticket and ticket[4] in ("taken", "reserved"):
            await update.message.reply_text(f"⚠️ ቁጥር {num} ቀድሞ ተይዟል!")
            return

    ctx.user_data["selected"] = numbers
    ctx.user_data["waiting_name"] = True
    
    await update.message.reply_text(
        f"✅ *{len(numbers)} ቁጥሮች ተመርጠዋል:* {', '.join(map(str, sorted(numbers)))}\n"
        f"💰 ጠቅላላ: *{total_price} ETB*\n\n"
        f"{t(ctx, 'ask_name')}",
        parse_mode="Markdown"
    )

# ─────────────────────────────────────────
# HOME & UI
# ─────────────────────────────────────────
async def show_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not ctx.user_data.get("lang"):
        ctx.user_data["lang"] = "am"

    title = await db.get_setting("lottery_title")
    price = await db.get_setting("ticket_price")
    total = await db.get_setting("total_tickets")
    taken = await db.count_taken_tickets()
    
    text = f"🎉 *{title}*\n🎟 ዋጋ: *{price} ETB*\n🔢 ጠቅላላ: *{total}*\n✅ ተሸጠዋል: *{taken}*"

    # ሚኒ አፑ ዳታ እንዲልክ KeyboardButton መሆን አለበት (Reply Keyboard)
    keyboard = [
        [KeyboardButton(text=t(ctx, "pick_btn"), web_app=WebAppInfo(url="https://tazaragnerfirst-coder.github.io/equb-bot/"))],
        [KeyboardButton(text=t(ctx, "my_tickets_btn")), KeyboardButton(text=t(ctx, "home_btn"))]
    ]
    if is_admin(user.id):
        keyboard.append([KeyboardButton(text=t(ctx, "admin_btn"))])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await show_home(update, ctx)

async def any_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    user = update.effective_user

    # Handle Reply Keyboard buttons
    if text == t(ctx, "my_tickets_btn"):
        # My Tickets Logic
        confirmed = await db.get_user_tickets(user.id, "taken")
        pending = await db.get_user_tickets(user.id, "reserved")
        if not confirmed and not pending:
            await update.message.reply_text(t(ctx, "no_tickets"))
        else:
            msg = f"{t(ctx, 'my_tickets_title')}\n"
            if confirmed: msg += f"✅ ተረጋግጠዋል: {len(confirmed)}\n"
            if pending: msg += f"⏳ በሂደት: {len(pending)}\n"
            await update.message.reply_text(msg)
        return

    if text == t(ctx, "admin_btn") and is_admin(user.id):
        await update.message.reply_text("👨‍💼 የአድሚን ፓነል ለመክፈት /admin ይፃፉ")
        return

    if text == t(ctx, "home_btn"):
        await show_home(update, ctx)
        return

    # Handle standard text inputs (Name, Phone, Admin actions)
    if ctx.user_data.get("waiting_name"):
        ctx.user_data["full_name"] = text
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = True
        await update.message.reply_text(t(ctx, "ask_phone"), parse_mode="Markdown")
    elif ctx.user_data.get("waiting_phone"):
        ctx.user_data["user_phone"] = text
        ctx.user_data["waiting_phone"] = False
        ctx.user_data["waiting_receipt"] = True
        # አካውንት መረጃ እዚህ ጋር ይላካል...
        await update.message.reply_text(f"💰 ክፍያ ፈፅመው ደረሰኝ ይላኩ።\n{t(ctx, 'ask_receipt')}")

# ─────────────────────────────────────────
# ADMIN & SYSTEM
# ─────────────────────────────────────────
async def post_init(application):
    await db.init_db()

def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u, c: show_home(u, c) if is_admin(u.effective_user.id) else None))
    
    # ሚኒ አፕ ዳታ መቀበያ
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    
    # ፅሁፎችን መቀበያ
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message_handler))
    
    # ፎቶ መቀበያ (ደረሰኝ)
    app.add_handler(MessageHandler(filters.PHOTO, lambda u, c: u.message.reply_text("✅ ደረሰኝ ተቀብለናል!")))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

# ይህ ፋይሉ መጨረሻ ላይ መሆን አለበት
if __name__ == "__main__":
    main()