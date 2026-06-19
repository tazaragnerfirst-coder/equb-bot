import logging
import asyncio
import json
import re
from threading import Thread
from flask import Flask
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Constants ───
MAX_TICKETS_PER_USER = 15

# ─── Keep Alive ───
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Bot is alive! 🤖"
def keep_alive():
    t = Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080))
    t.daemon = True
    t.start()

# ─── ስልክ ቁጥር ማጣሪያ (Regex) ───
def is_valid_phone(phone):
    pattern = r"^(09|07)\d{8}$"
    return re.match(pattern, phone)

# ─── ኪቦርድ ───
def get_main_keyboard(ctx):
    keyboard = [
        [KeyboardButton(text="🎟 ቁጥር ምረጥ", web_app=WebAppInfo(url="https://tazaragnerfirst-coder.github.io/equb-bot/"))],
        [KeyboardButton(text="📋 የእኔ ትኬቶች"), KeyboardButton(text="❓ እርዳታ/መመሪያ")]
    ]
    if update_user_is_admin(ctx):
        keyboard.append([KeyboardButton(text="👨‍💼 አድሚን ፓነል")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def update_user_is_admin(ctx):
    try: return ctx._user_id in ADMIN_IDS
    except: return False

# ─── START COMMAND ───
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx._user_id = update.effective_user.id
    welcome_text = (
        "👋 እንኳን ወደ እጣ መቁረጫ ቦት በሰላም መጡ!\n\n"
        "📖 *አጠቃቀም መመሪያ:*\n"
        "1️⃣ '🎟 ቁጥር ምረጥ' የሚለውን በተን ተጭነው የሚፈልጉትን ቁጥር ይምረጡ።\n"
        "2️⃣ የመረጡትን ቁጥር ሲያረጋግጡ ስምና ስልክ ይጠየቃሉ።\n"
        "3️⃣ የክፍያ መረጃው ሲመጣልዎ ክፍያ ፈፅመው ደረሰኝ ይላኩ።\n"
        "4️⃣ አድሚን ሲያረጋግጥ ቁጥሩ የእርሶ መሆኑን የሚገልፅ መልዕክት ይደርስዎታል።"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard(ctx))

# ─── WEB APP DATA (ዳታ መቀበያ) ───
async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    if data.get("action") != "buy_tickets": return

    nums = data.get("numbers", [])
    price = await db.get_setting("ticket_price")
    total = len(nums) * int(price)
    
    ctx.user_data["selected"] = nums
    ctx.user_data["total_price"] = total
    ctx.user_data["waiting_name"] = True

    confirm_msg = (
        f"🛒 *ምርጫዎን አረጋግጠዋል*\n\n"
        f"🎟 የመረጧቸው ቁጥሮች: `{', '.join(map(str, nums))}`\n"
        f"💰 ጠቅላላ ዋጋ: *{total} ETB*\n\n"
        f"👤 እባክዎ *ሙሉ ስምዎን* ይፃፉ:"
    )
    await update.message.reply_text(confirm_msg, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

# ─── TEXT & STATE HANDLER ───
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "❓ እርዳታ/መመሪያ":
        await start(update, ctx)
        return

    if text == "👨‍💼 አድሚን ፓነል" and user_id in ADMIN_IDS:
        await show_admin_dashboard(update)
        return

    # የስም መቀበያ
    if ctx.user_data.get("waiting_name"):
        ctx.user_data["full_name"] = text
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = True
        await update.message.reply_text("📞 አሁን ደግሞ *ስልክ ቁጥርዎን* (በ09... ወይም 07...) ያስገቡ:", parse_mode="Markdown")
        return

    # የስልክ መቀበያ
    if ctx.user_data.get("waiting_phone"):
        if not is_valid_phone(text):
            await update.message.reply_text("⚠️ ስህተት! እባክዎ ትክክለኛ የኢትዮጵያ ስልክ ቁጥር ያስገቡ (ምሳሌ: 0912345678)")
            return
        
        ctx.user_data["phone"] = text
        ctx.user_data["waiting_phone"] = False
        ctx.user_data["waiting_receipt"] = True
        
        msg = (
            f"✅ መረጃዎ ተመዝግቧል!\n\n"
            f"🏦 *ክፍያ ለመፈፀም:*\n"
            f"CBE: `{CBE_ACCOUNT}`\n"
            f"Telebirr: `{TELEBIRR_ACCOUNT}`\n\n"
            f"💰 ድምር: *{ctx.user_data['total_price']} ETB*\n\n"
            f"📸 ክፍያውን እንደጨረሱ *ደረሰኙን (Screenshot)* እዚህ ይላኩ።"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

# ─── RECEIPT HANDLER ───
async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("waiting_receipt"): return
    
    file_id = update.message.photo[-1].file_id
    nums = ctx.user_data["selected"]
    name = ctx.user_data["full_name"]
    phone = ctx.user_data["phone"]
    user = update.effective_user

    p_id = await db.add_payment(user.id, name, phone, nums, file_id, "Mobile Banking")
    await db.reserve_tickets(nums, user.id, name, phone)
    
    ctx.user_data["waiting_receipt"] = False
    await update.message.reply_text("🙏 እናመሰግናለን! ደረሰኝዎ ለባለሙያ ተልኳል። ሲረጋገጥ መልዕክት ይደርስዎታል።", reply_markup=get_main_keyboard(ctx))

    # ለአድሚን መላክ
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve_{p_id}"),
         InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"reject_{p_id}")]
    ])
    for adm in ADMIN_IDS:
        await ctx.bot.send_photo(chat_id=adm, photo=file_id, 
                               caption=f"🚨 *አዲስ ክፍያ!*\n\n👤 ስም: {name}\n📞 ስልክ: {phone}\n🎟 ቁጥሮች: {nums}\n💰 {ctx.user_data['total_price']} ETB",
                               reply_markup=admin_keyboard, parse_mode="Markdown")

# ─── APPROVE/REJECT LOGIC ───
async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, p_id = query.data.split("_")
    payment = await db.get_payment(int(p_id))
    if not payment: return

    user_id = payment[1]
    nums = payment[4]

    if action == "approve":
        await db.update_payment_status(int(p_id), "approved", query.from_user.id)
        await db.confirm_tickets(list(map(int, nums.split(","))), user_id, payment[2], payment[3])
        try:
            await ctx.bot.send_message(chat_id=user_id, text=f"🎉 ደስ የሚል ዜና! የትኬት ክፍያዎ ተረጋግጧል።\n🎟 ቁጥሮችዎ: {nums}\nመልካም እድል!")
        except: pass
        await query.edit_message_caption(caption=f"✅ ተረጋግጧል\n🎟 ቁጥሮች: {nums}")
    else:
        await db.update_payment_status(int(p_id), "rejected", query.from_user.id)
        await db.free_tickets(list(map(int, nums.split(","))))
        try:
            await ctx.bot.send_message(chat_id=user_id, text=f"❌ ይቅርታ፣ የላኩት ደረሰኝ አልተረጋገጠም። እባክዎ በትክክል መላክዎን ያረጋግጡ ወይም አድሚን ያናግሩ።")
        except: pass
        await query.edit_message_caption(caption="❌ ውድቅ ተደርጓል")

# ─── ADMIN DASHBOARD ───
async def show_admin_dashboard(update):
    total = await db.get_setting("total_tickets")
    price = await db.get_setting("ticket_price")
    taken = await db.count_taken_tickets()
    
    msg = (
        f"👨‍💼 *የአድሚን መቆጣጠሪያ*\n\n"
        f"📊 *ስታቲስቲክስ:*\n"
        f"🎟 ጠቅላላ እጣ: {total}\n"
        f"✅ የተሸጡ: {taken}\n"
        f"💰 የአንዱ ዋጋ: {price} ETB\n\n"
        f"ምን ማድረግ ይፈልጋሉ?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 ሁሉንም ተሸጦች እይ", callback_data="adm_history")],
        [InlineKeyboardButton("⚙️ ዋጋ/ርዕስ ቀይር", callback_data="adm_settings")],
        [InlineKeyboardButton("🔄 አዲስ እጣ ጀምር (Reset)", callback_data="adm_reset")]
    ])
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")

# ─── MAIN ───
def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).post_init(lambda a: db.init_db()).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(approve|reject)_"))
    app.run_polling()

if __name__ == "__main__": main()