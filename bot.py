import logging
import json
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
from config import *

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Render እንዲሰራ (Keep Alive) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is running..."
def run(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- ገጽታዎች እና ቋንቋዎች ---
MINI_APP_URL = "https://tazaragnerfirst-coder.github.io/equb-bot/"

STRINGS = {
    "am": {
        "home": "🏠 ዋና ገጽ", "cancel": "❌ ሰርዝ", "admin": "👨‍💼 አድሚን",
        "pick": "🎟 ቁጥር ምረጥ (Mini App)", "tickets": "📋 የእኔ ትኬቶች",
        "name": "👤 ሙሉ ስምዎን ይላኩ:", "phone": "📞 ስልክ ቁጥርዎን ይላኩ:",
        "payment": "💳 የክፍያ መንገድ ይምረጡ:", "receipt": "✅ ደረሰኝ (Screenshot) ይላኩ:"
    },
    "en": {
        "home": "🏠 Home", "cancel": "❌ Cancel", "admin": "👨‍💼 Admin",
        "pick": "🎟 Pick Numbers (Mini App)", "tickets": "📋 My Tickets",
        "name": "👤 Send full name:", "phone": "📞 Send phone number:",
        "payment": "💳 Choose Payment:", "receipt": "✅ Send receipt (Screenshot):"
    },
    "or": {
        "home": "🏠 Fuula Jalqabaa", "cancel": "❌ Haquu", "admin": "👨‍💼 Admin",
        "pick": "🎟 Lakkoofsa Filadhu", "tickets": "📋 Tikeetii Koo",
        "name": "👤 Maqaa guutuu ergi:", "phone": "📞 Bilbila ergi:",
        "payment": "💳 Mala kaffaltii:", "receipt": "✅ Beeksisa kaffaltii ergi:"
    }
}

def get_kb(lang):
    return ReplyKeyboardMarkup([[KeyboardButton(STRINGS[lang]["home"]), KeyboardButton(STRINGS[lang]["cancel"])]], resize_keyboard=True)

async def update_group_list(context: ContextTypes.DEFAULT_TYPE):
    total = int(await db.get_setting("total_tickets"))
    tickets = await db.get_all_tickets_status()
    t_map = {t[0]: (t[1], t[2], t[3]) for t in tickets}
    lines = ["📊 *የእጣዎች ሁኔታ*\n" + "─"*25]
    for i in range(1, total + 1):
        if i in t_map and t_map[i][2] == 'taken':
            lines.append(f"{i} 👉 `{t_map[i][0][:9]}#` ✅ {t_map[i][1]}")
        else: lines.append(f"{i} 👉 `[free]`")
    text = "\n".join(lines)
    last_id = await db.get_setting("last_group_msg_id")
    if last_id and last_id != "0":
        try: await context.bot.delete_message(chat_id=GROUP_ID, message_id=int(last_id))
        except: pass
    msg = await context.bot.send_message(chat_id=GROUP_ID, text=text[:4096], parse_mode="Markdown")
    await db.set_setting("last_group_msg_id", msg.message_id)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")],
           [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
           [InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_or")]]
    await update.message.reply_text("🌐 Choose Language:", reply_markup=InlineKeyboardMarkup(kb))

async def lang_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = query.data.split("_")[1]
    ctx.user_data["lang"] = lang
    title = await db.get_setting("lottery_title")
    kb = [[InlineKeyboardButton(STRINGS[lang]["pick"], web_app=WebAppInfo(url=MINI_APP_URL))],
          [InlineKeyboardButton(STRINGS[lang]["tickets"], callback_data="my_tickets")]]
    if update.effective_user.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton(STRINGS[lang]["admin"], callback_data="admin_panel")])
    await query.edit_message_text(f"🎉 *{title}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def handle_webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    ctx.user_data["selected"] = data
    lang = ctx.user_data.get("lang", "am")
    ctx.user_data["step"] = "name"
    await update.message.reply_text(f"🎟 {data}\n{STRINGS[lang]['name']}", reply_markup=get_kb(lang))

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = ctx.user_data.get("lang", "am")
    
    # Home/Cancel Logic
    if text in [STRINGS[l][k] for l in STRINGS for k in ["home", "cancel"]]:
        ctx.user_data.clear()
        ctx.user_data["lang"] = lang
        await update.message.reply_text("🏠", reply_markup=ReplyKeyboardRemove())
        # መልሶ ቋንቋ ሳይጠይቅ ዋና ገጽ እንዲከፍት
        kb = [[InlineKeyboardButton(STRINGS[lang]["pick"], web_app=WebAppInfo(url=MINI_APP_URL))]]
        if update.effective_user.id in ADMIN_IDS:
            kb.append([InlineKeyboardButton(STRINGS[lang]["admin"], callback_data="admin_panel")])
        await update.message.reply_text("ዋና ገጽ", reply_markup=InlineKeyboardMarkup(kb))
        return

    step = ctx.user_data.get("step")
    if step == "name":
        ctx.user_data["name"] = text
        ctx.user_data["step"] = "phone"
        await update.message.reply_text(STRINGS[lang]["phone"])
    elif step == "phone":
        ctx.user_data["phone"] = text
        ctx.user_data["step"] = "receipt"
        kb = [[InlineKeyboardButton("🏦 CBE", callback_data="m_CBE"), InlineKeyboardButton("📱 Telebirr", callback_data="m_Tele")]]
        await update.message.reply_text(STRINGS[lang]["payment"], reply_markup=InlineKeyboardMarkup(kb))

async def method_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = "CBE" if query.data == "m_CBE" else "Telebirr"
    ctx.user_data["method"] = method
    acc = CBE_ACCOUNT if method == "CBE" else TELEBIRR_ACCOUNT
    await query.message.reply_text(f"✅ {method}: `{acc}`\n{STRINGS[ctx.user_data['lang']]['receipt']}")

async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("step") != "receipt": return
    photo = update.message.photo[-1].file_id
    p_id = await db.add_payment(update.effective_user.id, ctx.user_data["name"], ctx.user_data["phone"], ctx.user_data["selected"], photo, ctx.user_data["method"])
    await db.reserve_tickets(ctx.user_data["selected"], update.effective_user.id, ctx.user_data["name"], ctx.user_data["phone"])
    await update.message.reply_text("✅ ተልኳል!", reply_markup=ReplyKeyboardRemove())
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{p_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{p_id}")]]
    for admin in ADMIN_IDS: await ctx.bot.send_photo(chat_id=admin, photo=photo, caption=f"ID: {p_id}\nName: {ctx.user_data['name']}\nNums: {ctx.user_data['selected']}", reply_markup=InlineKeyboardMarkup(kb))

async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, p_id = query.data.split("_")
    pay = await db.get_payment(int(p_id))
    if action == "app":
        nums = list(map(int, pay[4].split(",")))
        await db.confirm_tickets(nums, pay[1], pay[2], pay[3])
        await db.update_payment_status(int(p_id), "approved", update.effective_user.id)
        await query.edit_message_caption("✅ Approved")
        await update_group_list(ctx)
    else:
        await db.update_payment_status(int(p_id), "rejected", update.effective_user.id)
        await query.edit_message_caption("❌ Rejected")

async def post_init(app): await db.init_db()

if __name__ == "__main__":
    Thread(target=run).start() # Flask server starts in a thread
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lang_cb, pattern="^lang_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(method_cb, pattern="^m_"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb, pattern="^(app|rej)_"))
    app.run_polling(drop_pending_updates=True)