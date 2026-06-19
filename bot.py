import logging
import asyncio
import json
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Constants ───
MAX_TICKETS_PER_USER = 15
PAGE_SIZE = 50

# ─── Keep Alive ───
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Bot is alive! 🤖"
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
        "ask_name": "👤 *ሙሉ ስምዎን ይፃፉ:*",
        "ask_phone": "📞 *ስልክ ቁጥርዎን ይፃፉ:*",
        "ask_receipt": "✅ ክፍያ ፈፅመው *ደረሰኝ (screenshot)* ይላኩ።",
        "approved": "🎉 *ክፍያዎ ተረጋግጧል!*\n🎟 ቁጥሮቾ: {nums}\n💰 {total} ብር",
        "rejected": "❌ *ክፍያዎ አልተረጋገጠም።*\n🎟 ቁጥሮች: {nums}",
        "choose_lang": "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:",
    },
    "en": {
        "pick_btn": "🎟 Pick Numbers",
        "my_tickets_btn": "📋 My Tickets",
        "admin_btn": "👨‍💼 Admin Panel",
        "home_btn": "🏠 Home",
        "ask_name": "👤 *Enter your full name:*",
        "ask_phone": "📞 *Enter your phone number:*",
        "ask_receipt": "✅ Please send your *receipt (screenshot)*.",
        "approved": "🎉 *Payment confirmed!*\n🎟 Numbers: {nums}\n💰 {total} ETB",
        "rejected": "❌ *Payment not confirmed.*\n🎟 Numbers: {nums}",
        "choose_lang": "🌐 Choose Language:",
    },
    "or": {
        "pick_btn": "🎟 Lakkoofsa Filadhu",
        "my_tickets_btn": "📋 Tikeetii Koo",
        "admin_btn": "👨‍💼 Admin Panel",
        "home_btn": "🏠 Fuula Jalqabaa",
        "ask_name": "👤 *Maqaa guutuu kee barreessi:*",
        "ask_phone": "📞 *Lakkoofsa bilbilaa kee barreessi:*",
        "ask_receipt": "✅ *Screenshot (suuraa)* ergi.",
        "approved": "🎉 *Kaffaltiins mirkanaa'e!*\n🎟 Lakkoofsa: {nums}",
        "rejected": "❌ *Kaffaltiins hin mirkanaa'in.*",
        "choose_lang": "🌐 Afaan filachuu:",
    }
}

def t(ctx, key, **kwargs):
    lang = ctx.user_data.get("lang", "am")
    template = T.get(lang, T["am"]).get(key, key)
    try: return template.format(**kwargs)
    except: return template

def is_admin(user_id): return user_id in ADMIN_IDS

def mask_phone(phone):
    p = str(phone).strip()
    return p + "#" if p else ""

# ─────────────────────────────────────────
# GROUP LIST UPDATER (ሁሉንም ዝርዝር የሚልክ)
# ─────────────────────────────────────────
async def update_group_list(bot):
    total = int(await db.get_setting("total_tickets"))
    # አሮጌ መልዕክቶችን ሰርዝ
    old_msgs = await db.get_group_message_ids()
    for msg_id, chat_id in old_msgs:
        try: await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except: pass
    await db.clear_group_messages()

    # ዝርዝር አዘጋጅና ላክ
    ticket_map = await db.get_all_tickets_full(total)
    CHUNK = 40
    new_msg_ids = []
    for i in range(1, total + 1, CHUNK):
        lines = []
        for n in range(i, min(i + CHUNK, total + 1)):
            info = ticket_map.get(n)
            if info and info[1] == "taken":
                lines.append(f"{n} 👉 {mask_phone(info[0])} ✅")
            else:
                lines.append(f"{n} 👉")
        text = "\n".join(lines)
        msg = await bot.send_message(chat_id=GROUP_ID, text=text)
        new_msg_ids.append(msg.message_id)
    await db.save_group_message_ids(GROUP_ID, new_msg_ids)

# ─────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_or")],
    ]
    await update.message.reply_text(T["am"]["choose_lang"], reply_markup=InlineKeyboardMarkup(keyboard))

async def lang_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ctx.user_data["lang"] = query.data.split("_")[1]
    await query.answer()
    await query.delete_message()
    await show_home(update, ctx)

async def show_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    price = await db.get_setting("ticket_price")
    title = await db.get_setting("lottery_title")
    text = f"🎉 *{title}*\n🎟 ዋጋ: *{price} ETB*"
    
    keyboard = [
        [KeyboardButton(t(ctx, "pick_btn"), web_app=WebAppInfo(url="https://tazaragnerfirst-coder.github.io/equb-bot/"))],
        [KeyboardButton(t(ctx, "my_tickets_btn")), KeyboardButton(t(ctx, "home_btn"))]
    ]
    if is_admin(update.effective_user.id):
        keyboard.append([KeyboardButton(t(ctx, "admin_btn"))])
    
    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    if data.get("action") != "buy_tickets": return
    
    nums = data.get("numbers", [])
    ctx.user_data["selected"] = nums
    ctx.user_data["waiting_name"] = True
    await update.message.reply_text(t(ctx, "ask_name"), parse_mode="Markdown")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user

    if text == t(ctx, "home_btn"): await show_home(update, ctx); return
    if text == t(ctx, "admin_btn") and is_admin(user.id): await show_admin_panel(update, ctx); return

    if ctx.user_data.get("waiting_name"):
        ctx.user_data["full_name"] = text
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = True
        await update.message.reply_text(t(ctx, "ask_phone"), parse_mode="Markdown")
    elif ctx.user_data.get("waiting_phone"):
        ctx.user_data["phone"] = text
        ctx.user_data["waiting_phone"] = False
        ctx.user_data["waiting_receipt"] = True
        price = await db.get_setting("ticket_price")
        total = len(ctx.user_data["selected"]) * int(price)
        msg = f"💰 ጠቅላላ፡ *{total} ETB*\nCBE: `{CBE_ACCOUNT}`\n\n{t(ctx, 'ask_receipt')}"
        await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("waiting_receipt"): return
    file_id = update.message.photo[-1].file_id
    nums = ctx.user_data["selected"]
    user = update.effective_user
    
    p_id = await db.add_payment(user.id, user.username or ctx.user_data["full_name"], ctx.user_data["phone"], nums, file_id, "CBE/Tele")
    await db.reserve_tickets(nums, user.id, user.username or ctx.user_data["full_name"], ctx.user_data["phone"])
    
    ctx.user_data["waiting_receipt"] = False
    await update.message.reply_text("✅ ተልኳል!")

    # ለአድሚን
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"app_{p_id}"),
        InlineKeyboardButton("❌ ውድቅ", callback_data=f"rej_{p_id}")
    ]])
    for adm in ADMIN_IDS:
        await ctx.bot.send_photo(chat_id=adm, photo=file_id, caption=f"🎟 ቁጥሮች: {nums}\n👤 {ctx.user_data['full_name']}", reply_markup=keyboard)

async def admin_decision(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, p_id = query.data.split("_")
    payment = await db.get_payment(int(p_id))
    nums = list(map(int, payment[4].split(",")))
    
    if action == "app":
        await db.update_payment_status(int(p_id), "approved", query.from_user.id)
        await db.confirm_tickets(nums, payment[1], payment[2], payment[3])
        await ctx.bot.send_message(chat_id=payment[1], text=t(ctx, "approved", nums=nums, total=""))
        # ግሩፕ ላይ ያለውን ዝርዝር በሙሉ በራስ-ሰር ማዘመን
        await update_group_list(ctx.bot)
        await query.edit_message_caption("✅ ፀድቋል")
    else:
        await db.update_payment_status(int(p_id), "rejected", query.from_user.id)
        await db.free_tickets(nums)
        await query.edit_message_caption("❌ ውድቅ ተደርጓል")

async def show_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 ስታቲስቲክስ", callback_data="adm_stats")],
        [InlineKeyboardButton("📤 ግሩፕ አዘምን", callback_data="adm_update_gp")],
        [InlineKeyboardButton("🔄 Reset", callback_data="adm_reset")]
    ])
    await update.message.reply_text("👨‍💼 Admin Panel", reply_markup=keyboard)

# ─── MAIN ───
def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).post_init(lambda a: db.init_db()).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lang_cb, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(app|rej)_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__": main()