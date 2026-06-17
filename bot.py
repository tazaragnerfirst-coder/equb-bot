import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
from config import *

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ሚኒ አፕ ሊንክ ---
MINI_APP_URL = "https://tazaragnerfirst-coder.github.io/equb-bot/"

# ቋንቋዎች እና በተኖች
STRINGS = {
    "am": {
        "welcome": "🎉 እንኳን ደህና መጡ! ቁጥር ለመምረጥ ሚኒ አፑን ይጠቀሙ።",
        "pick_btn": "🎟 ቁጥር ምረጥ (Mini App)",
        "my_tickets": "📋 የእኔ ትኬቶች",
        "admin_btn": "👨‍💼 አድሚን ፓነል",
        "home": "🏠 ዋና ገጽ",
        "cancel": "❌ ሰርዝ",
        "ask_name": "👤 እባክዎ *ሙሉ ስምዎን* ይላኩ:",
        "ask_phone": "📞 አሁን *ስልክ ቁጥርዎን* ይላኩ:",
        "payment": "💳 የክፍያ መንገድ ይምረጡ:",
        "receipt_sent": "✅ ደረሰኝዎ ተልኳል! አድሚን ሲያረጋግጥ እናሳውቅዎታለን።",
        "approved": "🎉 እንኳን ደስ አለዎት! ክፍያዎ ተረጋግጦ እጣዎ ጸድቋል።",
        "rejected": "❌ ይቅርታ፣ ክፍያዎ ውድቅ ተደርጓል። እባክዎ አድሚን ያነጋግሩ።"
    },
    "en": {
        "welcome": "🎉 Welcome! Use the Mini App to pick numbers.",
        "pick_btn": "🎟 Pick Numbers (Mini App)",
        "my_tickets": "📋 My Tickets",
        "admin_btn": "👨‍💼 Admin Panel",
        "home": "🏠 Home",
        "cancel": "❌ Cancel",
        "ask_name": "👤 Please send your *Full Name*:",
        "ask_phone": "📞 Now send your *Phone Number*:",
        "payment": "💳 Choose Payment Method:",
        "receipt_sent": "✅ Receipt sent! You will be notified once admin confirms.",
        "approved": "🎉 Congratulations! Your payment is confirmed.",
        "rejected": "❌ Sorry, your payment was rejected."
    },
    "or": {
        "welcome": "🎉 Baga nagaan dhuftan! Lakkoofsa filachuuf Mini App fayyadamaa.",
        "pick_btn": "🎟 Lakkoofsa Filadhu",
        "my_tickets": "📋 Tikeetii Koo",
        "admin_btn": "👨‍💼 Admin Panel",
        "home": "🏠 Fuula Jalqabaa",
        "cancel": "❌ Haquu",
        "ask_name": "👤 Maqaa guutuu kee ergi:",
        "ask_phone": "📞 Lakkoofsa bilbilaa ergi:",
        "payment": "💳 Mala kaffaltii filadhu:",
        "receipt_sent": "✅ Beeksisni kaffaltii ergameera!",
        "approved": "🎉 Gammadaa! Kaffaltiin keessan mirkanaa'eera.",
        "rejected": "❌ Dhiifama, kaffaltiin keessan fudhatama hin arganne."
    }
}

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_menu_keyboard(lang):
    return ReplyKeyboardMarkup(
        [[KeyboardButton(STRINGS[lang]["home"]), KeyboardButton(STRINGS[lang]["cancel"])]],
        resize_keyboard=True
    )

async def update_group_list(context: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ ላይ ዝርዝሩን ያድሳል። ፎርማት፡ 091231231# ✅ ስም"""
    total = int(await db.get_setting("total_tickets"))
    tickets = await db.get_all_tickets_status()
    ticket_map = {t[0]: (t[1], t[2], t[3]) for t in tickets}

    lines = ["📊 *የእጣዎች ወቅታዊ ሁኔታ*\n" + "─"*25]
    for i in range(1, total + 1):
        if i in ticket_map and ticket_map[i][2] == 'taken':
            phone, name, _ = ticket_map[i]
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
    except Exception as e:
        logger.error(f"Group update error: {e}")

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
    kb = [
        [InlineKeyboardButton(STRINGS[lang]["pick_btn"], web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton(STRINGS[lang]["my_tickets"], callback_data="my_tickets")]
    ]
    if is_admin(update.effective_user.id):
        kb.append([InlineKeyboardButton(STRINGS[lang]["admin_btn"], callback_data="admin_panel")])
        
    await query.edit_message_text(
        f"🎉 *{title}*\n{STRINGS[lang]['welcome']}", 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    ctx.user_data["selected"] = data
    lang = ctx.user_data.get("lang", "am")
    price = int(await db.get_setting("ticket_price"))
    
    text = (f"🎟 *የመረጥካቸው:* {', '.join(map(str, data))}\n"
            f"💰 *ድምር ዋጋ:* {len(data) * price} ብር\n\n{STRINGS[lang]['ask_name']}")
    
    ctx.user_data["step"] = "name"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_menu_keyboard(lang))

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    lang = ctx.user_data.get("lang", "am")
    
    # Home ወይም Cancel በተን ከተጫነ
    if text in [STRINGS[l][k] for l in STRINGS for k in ["home", "cancel"]]:
        ctx.user_data.clear()
        ctx.user_data["lang"] = lang
        title = await db.get_setting("lottery_title")
        kb = [[InlineKeyboardButton(STRINGS[lang]["pick_btn"], web_app=WebAppInfo(url=MINI_APP_URL))],
              [InlineKeyboardButton(STRINGS[lang]["my_tickets"], callback_data="my_tickets")]]
        if is_admin(update.effective_user.id):
            kb.append([InlineKeyboardButton(STRINGS[lang]["admin_btn"], callback_data="admin_panel")])
            
        await update.message.reply_text("🏠", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text(f"🎉 *{title}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    step = ctx.user_data.get("step")
    if step == "name":
        ctx.user_data["name"] = text
        ctx.user_data["step"] = "phone"
        await update.message.reply_text(STRINGS[lang]["ask_phone"])
    elif step == "phone":
        ctx.user_data["phone"] = text
        ctx.user_data["step"] = "receipt"
        kb = [[InlineKeyboardButton("🏦 CBE", callback_data="m_CBE"), 
               InlineKeyboardButton("📱 Telebirr", callback_data="m_Tele")]]
        await update.message.reply_text(STRINGS[lang]["payment"], reply_markup=InlineKeyboardMarkup(kb))

async def method_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = "CBE" if query.data == "m_CBE" else "Telebirr"
    ctx.user_data["method"] = method
    acc = CBE_ACCOUNT if method == "CBE" else TELEBIRR_ACCOUNT
    name = CBE_NAME if method == "CBE" else TELEBIRR_NAME
    await query.message.reply_text(f"✅ {method}: `{acc}`\n👤 ስም: {name}\n\nአሁን ደረሰኝ (Screenshot) ይላኩ።")

async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("step") != "receipt": return
    photo = update.message.photo[-1].file_id
    user = update.effective_user
    lang = ctx.user_data.get("lang", "am")
    
    p_id = await db.add_payment(user.id, ctx.user_data["name"], ctx.user_data["phone"], 
                               ctx.user_data["selected"], photo, ctx.user_data["method"])
    await db.reserve_tickets(ctx.user_data["selected"], user.id, ctx.user_data["name"], ctx.user_data["phone"])
    
    ctx.user_data["step"] = None
    await update.message.reply_text(STRINGS[lang]["receipt_sent"], parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    
    # ለአድሚን ማሳወቂያ
    admin_cap = (f"💳 *አዲስ ክፍያ (#ID_{p_id})*\n👤 ስም: {ctx.user_data['name']}\n"
                 f"📞 ስልክ: {ctx.user_data['phone']}\n🎟 ቁጥሮች: {ctx.user_data['selected']}\n"
                 f"💰 ዘዴ: {ctx.user_data['method']}")
    kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{p_id}"), 
           InlineKeyboardButton("❌ Reject", callback_data=f"rej_{p_id}")]]
    
    for admin in ADMIN_IDS:
        await ctx.bot.send_photo(chat_id=admin, photo=photo, caption=admin_cap, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, p_id = query.data.split("_")
    pay = await db.get_payment(int(p_id))
    
    if action == "app":
        nums = list(map(int, pay[4].split(",")))
        await db.confirm_tickets(nums, pay[1], pay[2], pay[3])
        await db.update_payment_status(int(p_id), "approved", update.effective_user.id)
        await query.edit_message_caption("✅ Approved")
        await ctx.bot.send_message(chat_id=pay[1], text=STRINGS["am"]["approved"])
        await update_group_list(ctx)
    else:
        await db.update_payment_status(int(p_id), "rejected", update.effective_user.id)
        await query.edit_message_caption("❌ Rejected")
        await ctx.bot.send_message(chat_id=pay[1], text=STRINGS["am"]["rejected"])

async def admin_panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id): return
    
    # እዚህ ጋር የአድሚን ዝርዝር መረጃዎችን ማሳየት ይቻላል
    await query.message.reply_text("🛠 የአድሚን ገጽ በቅርቡ ይጠናቀቃል።")

async def post_init(app):
    await db.init_db()

def main():
    # drop_pending_updates=True ቶከን Conflict እንዳይፈጥር ይረዳል
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lang_cb, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(admin_panel_cb, pattern="^admin_panel$"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(method_cb, pattern="^m_"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb, pattern="^(app|rej)_"))
    
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main() 