import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ያንተ GitHub Pages ሊንክ ---
MINI_APP_URL = "https://tazaragnerfirst-coder.github.io/equb-bot/"

STRINGS = {
    "am": {
        "welcome": "🎉 እንኳን ደህና መጡ! ቁጥር ለመምረጥ ሚኒ አፑን ይጠቀሙ።",
        "pick_btn": "🎟 ቁጥር ምረጥ (Mini App)", "ask_name": "👤 ሙሉ ስምዎን ይላኩ:",
        "ask_phone": "📞 ስልክ ቁጥርዎን ይላኩ:", "payment": "💳 የክፍያ መንገድ ይምረጡ:",
        "approved": "🎉 እንኳን ደስ አለዎት! ክፍያዎ ተረጋግጦ እጣዎ ጸድቋል።"
    },
    "en": {
        "welcome": "🎉 Welcome! Use the Mini App to pick numbers.",
        "pick_btn": "🎟 Pick Numbers (Mini App)", "ask_name": "👤 Send your full name:",
        "ask_phone": "📞 Send your phone number:", "payment": "💳 Choose payment method:",
        "approved": "🎉 Congratulations! Your payment is confirmed."
    },
    "or": {
        "welcome": "🎉 Baga nagaan dhuftan! Lakkoofsa filachuuf Mini App fayyadamaa.",
        "pick_btn": "🎟 Lakkoofsa Filadhu", "ask_name": "👤 Maqaa guutuu ergi:",
        "ask_phone": "📞 Lakkoofsa bilbilaa ergi:", "payment": "💳 Mala kaffaltii filadhu:",
        "approved": "🎉 Gammadaa! Kaffaltiin keessan mirkanaa'eera."
    }
}

async def update_group_list(context: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ ላይ ዝርዝሩን ያድሳል። ፎርማት፡ 091231231# ✅ Name"""
    total = int(await db.get_setting("total_tickets"))
    tickets = await db.get_all_tickets_status()
    ticket_map = {t[0]: (t[1], t[2], t[3]) for t in tickets}

    lines = ["📊 *የእጣዎች ወቅታዊ ሁኔታ*\n" + "─"*25]
    for i in range(1, total + 1):
        if i in ticket_map and ticket_map[i][2] == 'taken':
            phone, name, _ = ticket_map[i]
            # ፎርማት: 091231231# ✅ Name (ስልኩን 9 ዲጂት ብቻ በማሳየት)
            safe_phone = phone[:9] if phone else "09..."
            lines.append(f"{i} 👉 `{safe_phone}#` ✅ {name}")
        else:
            lines.append(f"{i} 👉 `[free]`")

    text = "\n".join(lines)
    last_id = await db.get_setting("last_group_msg_id")
    if last_id and last_id != "0":
        try: await context.bot.delete_message(chat_id=GROUP_ID, message_id=int(last_id))
        except: pass

    try:
        msg = await context.bot.send_message(chat_id=GROUP_ID, text=text[:4096], parse_mode="Markdown")
        await db.set_setting("last_group_msg_id", msg.message_id)
    except Exception as e: logger.error(f"Group update error: {e}")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_or")]
    ]
    await update.message.reply_text("🌐 Choose Language / ቋንቋ ይምረጡ:", reply_markup=InlineKeyboardMarkup(kb))

async def lang_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    ctx.user_data["lang"] = lang
    title = await db.get_setting("lottery_title")
    kb = [[InlineKeyboardButton(STRINGS[lang]["pick_btn"], web_app=WebAppInfo(url=MINI_APP_URL))]]
    await query.edit_message_text(f"🎉 *{title}*\n{STRINGS[lang]['welcome']}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def handle_webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    ctx.user_data["selected"] = data
    lang = ctx.user_data.get("lang", "am")
    await update.message.reply_text(f"🎟 {data}\n{STRINGS[lang]['ask_name']}")
    ctx.user_data["step"] = "name"

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    step = ctx.user_data.get("step")
    lang = ctx.user_data.get("lang", "am")
    if step == "name":
        ctx.user_data["name"] = update.message.text
        ctx.user_data["step"] = "phone"
        await update.message.reply_text(STRINGS[lang]["ask_phone"])
    elif step == "phone":
        ctx.user_data["phone"] = update.message.text
        ctx.user_data["step"] = "receipt"
        kb = [[InlineKeyboardButton("🏦 CBE", callback_data="m_CBE"), InlineKeyboardButton("📱 Telebirr", callback_data="m_Tele")]]
        await update.message.reply_text(STRINGS[lang]["payment"], reply_markup=InlineKeyboardMarkup(kb))

async def method_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    method = "CBE" if query.data == "m_CBE" else "Telebirr"
    ctx.user_data["method"] = method
    acc = CBE_ACCOUNT if method == "CBE" else TELEBIRR_ACCOUNT
    await query.message.reply_text(f"✅ {method}: `{acc}`\nአሁን ደረሰኝ (Screenshot) ላክ።")

async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("step") != "receipt": return
    photo = update.message.photo[-1].file_id
    user = update.effective_user
    p_id = await db.add_payment(user.id, ctx.user_data["name"], ctx.user_data["phone"], ctx.user_data["selected"], photo, ctx.user_data["method"])
    await db.reserve_tickets(ctx.user_data["selected"], user.id, ctx.user_data["name"], ctx.user_data["phone"])
    await update.message.reply_text("✅ ደረሰኝ ተልኳል።")
    
    admin_cap = (f"ID: {p_id}\nName: {ctx.user_data['name']}\nPhone: {ctx.user_data['phone']}\n"
                 f"Nums: {ctx.user_data['selected']}\nMethod: {ctx.user_data['method']}")
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{p_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{p_id}")]]
    for admin in ADMIN_IDS: await ctx.bot.send_photo(chat_id=admin, photo=photo, caption=admin_cap, reply_markup=InlineKeyboardMarkup(kb))

async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, p_id = query.data.split("_")
    pay = await db.get_payment(int(p_id))
    lang = "am" # ማሳወቂያው በአማርኛ ይሁን ከተባለ
    if action == "app":
        nums = list(map(int, pay[4].split(",")))
        await db.confirm_tickets(nums, pay[1], pay[2], pay[3])
        await db.update_payment_status(int(p_id), "approved", update.effective_user.id)
        await query.edit_message_caption("✅ Approved")
        await ctx.bot.send_message(chat_id=pay[1], text=STRINGS[lang]["approved"])
        await update_group_list(ctx)
    else:
        await db.update_payment_status(int(p_id), "rejected", update.effective_user.id)
        await query.edit_message_caption("❌ Rejected")

async def post_init(app): await db.init_db()

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lang_cb, pattern="^lang_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(method_cb, pattern="^m_"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb, pattern="^(app|rej)_"))
    
    # Conflict ለመከላከል drop_pending_updates=True የግድ ነው
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()