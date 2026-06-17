import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ያንተ GitHub Pages ሊንክ እዚህ ጋር ተስተካክሏል ---
MINI_APP_URL = "https://tazaragnerfirst-coder.github.io/equb-bot/"

async def update_group_list(context: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ ላይ ያለውን ዝርዝር አጥፍቶ በአዲስ ይተካል። ፎርማት፡ 091231231# ✅ ስም"""
    total = int(await db.get_setting("total_tickets"))
    tickets = await db.get_all_tickets_status()
    ticket_map = {t[0]: (t[1], t[2], t[3]) for t in tickets}

    lines = ["📊 *የእጣዎች ወቅታዊ ሁኔታ*\n" + "─"*25]
    for i in range(1, total + 1):
        if i in ticket_map and ticket_map[i][2] == 'taken':
            phone, name, _ = ticket_map[i]
            # ስልኩን ደብቆ በመጨረሻው # መጨመር
            safe_phone = phone[:-1] if phone else "09..."
            lines.append(f"{i} 👉 `{safe_phone}#` ✅ {name}")
        else:
            lines.append(f"{i} 👉 `[free]`")

    text = "\n".join(lines)
    
    # የድሮውን መልዕክት ማጥፋት
    last_id = await db.get_setting("last_group_msg_id")
    if last_id and last_id != "0":
        try: await context.bot.delete_message(chat_id=GROUP_ID, message_id=int(last_id))
        except: pass

    # አዲሱን መልዕክት መላክ
    try:
        msg = await context.bot.send_message(chat_id=GROUP_ID, text=text[:4096], parse_mode="Markdown")
        await db.set_setting("last_group_msg_id", msg.message_id)
    except Exception as e:
        logger.error(f"Group update error: {e}")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    title = await db.get_setting("lottery_title")
    kb = [[InlineKeyboardButton("🎟 ቁጥር ምረጥ (Mini App)", web_app=WebAppInfo(url=MINI_APP_URL))]]
    if update.effective_user.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("👨‍💼 አድሚን ፓነል", callback_data="admin_pending")])

    await update.message.reply_text(f"🎉 *{title}*\nእንኳን ደህና መጡ! ቁጥር ለመምረጥ ከታች ያለውን በተን ይጫኑ።", 
                                  parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def handle_webapp_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ከሚኒ አፕ የመጡ ቁጥሮችን መቀበያ"""
    data = json.loads(update.effective_message.web_app_data.data)
    ctx.user_data["selected"] = data
    price = int(await db.get_setting("ticket_price"))
    
    text = (f"🎟 *የመረጥካቸው:* {', '.join(map(str, data))}\n"
            f"💰 *ጠቅላላ:* {len(data) * price} ብር\n\nእባክዎ *ሙሉ ስምዎን* ይላኩ:")
    ctx.user_data["step"] = "name"
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    step = ctx.user_data.get("step")
    if step == "name":
        ctx.user_data["name"] = update.message.text
        ctx.user_data["step"] = "phone"
        await update.message.reply_text("📞 አሁን *ስልክ ቁጥርዎን* ይላኩ:")
    elif step == "phone":
        ctx.user_data["phone"] = update.message.text
        ctx.user_data["step"] = "receipt"
        method_kb = [[InlineKeyboardButton("🏦 CBE", callback_data="m_CBE"), 
                      InlineKeyboardButton("📱 Telebirr", callback_data="m_Tele")]]
        await update.message.reply_text("💳 የክፍያ መንገድ ይምረጡ:", reply_markup=InlineKeyboardMarkup(method_kb))

async def method_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = "CBE" if query.data == "m_CBE" else "Telebirr"
    ctx.user_data["method"] = method
    acc = CBE_ACCOUNT if method == "CBE" else TELEBIRR_ACCOUNT
    name = CBE_NAME if method == "CBE" else TELEBIRR_NAME
    await query.message.reply_text(f"✅ {method} ተመርጧል።\nሒሳብ ቁጥር: `{acc}`\nስም: {name}\n\nአሁን *ደረሰኝ (Screenshot)* ይላኩ።", parse_mode="Markdown")

async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("step") != "receipt": return
    photo = update.message.photo[-1].file_id
    user = update.effective_user
    selected = ctx.user_data["selected"]
    
    p_id = await db.add_payment(user.id, ctx.user_data["name"], ctx.user_data["phone"], selected, photo, ctx.user_data["method"])
    await db.reserve_tickets(selected, user.id, ctx.user_data["name"], ctx.user_data["phone"])
    
    ctx.user_data["step"] = None
    await update.message.reply_text("✅ ደረሰኝዎ ተልኳል! አድሚን ሲያረጋግጥ እናሳውቅዎታለን።")
    
    # ለአድሚን ማሳወቂያ
    admin_msg = (f"💳 *አዲስ ክፍያ (#ID_{p_id})*\n👤 ስም: {ctx.user_data['name']}\n"
                 f"📞 ስልክ: {ctx.user_data['phone']}\n🎟 ቁጥሮች: {selected}")
    kb = [[InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"app_{p_id}"),
           InlineKeyboardButton("❌ ውድቅ", callback_data=f"rej_{p_id}")]]
    for admin in ADMIN_IDS:
        await ctx.bot.send_photo(chat_id=admin, photo=photo, caption=admin_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, p_id = query.data.split("_")
    pay = await db.get_payment(int(p_id))
    
    if action == "app":
        nums = list(map(int, pay[4].split(",")))
        await db.confirm_tickets(nums, pay[1], pay[2], pay[3])
        await db.update_payment_status(int(p_id), "approved", update.effective_user.id)
        await query.edit_message_caption("✅ ክፍያው ተረጋግጧል!")
        await ctx.bot.send_message(chat_id=pay[1], text="🎉 ክፍያዎ ተረጋግጧል!")
        await update_group_list(ctx) # ግሩፕ ላይ አውቶማቲክ እንዲያድስ
    else:
        await db.update_payment_status(int(p_id), "rejected", update.effective_user.id)
        await query.edit_message_caption("❌ ክፍያው ውድቅ ተደርጓል።")

async def post_init(app):
    await db.init_db()

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(method_cb, pattern="^m_"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb, pattern="^(app|rej)_"))
    app.run_polling()

if __name__ == "__main__":
    main()
