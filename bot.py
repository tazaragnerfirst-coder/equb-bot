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

# ─── Keep Alive (For Render) ───
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Bot is alive! 🤖"
def keep_alive():
    t = Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080))
    t.daemon = True
    t.start()

# ─── Helper Functions ───
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_home_keyboard(ctx):
    keyboard = [
        [KeyboardButton(text="🎟 ቁጥር ምረጥ", web_app=WebAppInfo(url="https://tazaragnerfirst-coder.github.io/equb-bot/"))],
        [KeyboardButton(text="📋 የእኔ ትኬቶች"), KeyboardButton(text="🏠 ዋና ገጽ")]
    ]
    if is_admin(ctx._user_id if hasattr(ctx, '_user_id') else 0):
        keyboard.append([KeyboardButton(text="👨‍💼 አድሚን ፓነል")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ─── WEB APP DATA HANDLER ───
async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        if data.get("action") != "buy_tickets": return
        
        numbers = data.get("numbers", [])
        price = await db.get_setting("ticket_price")
        total_price = len(numbers) * int(price)

        # ተይዘው እንደሆነ ቼክ ማድረግ
        for num in numbers:
            t = await db.get_ticket(num)
            if t and t[4] in ("taken", "reserved"):
                await update.message.reply_text(f"⚠️ ቁጥር {num} ተይዟል።")
                return

        ctx.user_data["selected"] = numbers
        ctx.user_data["waiting_name"] = True
        
        await update.message.reply_text(
            f"✅ {len(numbers)} ቁጥሮች ተመርጠዋል። ጠቅላላ፡ {total_price} ETB\n\n👤 ሙሉ ስምዎን ይፃፉ፡",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"WebApp Error: {e}")

# ─── MESSAGE HANDLER (Name, Phone, Receipt) ───
async def handle_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user

    if text == "🏠 ዋና ገጽ":
        await start(update, ctx)
        return

    if text == "📋 የእኔ ትኬቶች":
        confirmed = await db.get_user_tickets(user.id, "taken")
        pending = await db.get_user_tickets(user.id, "reserved")
        msg = "🎟 *የእኔ ትኬቶች*\n"
        if confirmed: msg += f"✅ የተረጋገጡ፡ {', '.join(map(str, [t[0] for t in confirmed]))}\n"
        if pending: msg += f"⏳ በሂደት፡ {', '.join(map(str, [t[0] for t in pending]))}\n"
        if not confirmed and not pending: msg = "ምንም ትኬት የለዎትም።"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if text == "👨‍💼 አድሚን ፓነል" and is_admin(user.id):
        await show_admin_panel(update, ctx)
        return

    # የክፍያ ሂደት
    if ctx.user_data.get("waiting_name"):
        ctx.user_data["full_name"] = text
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = True
        await update.message.reply_text("📞 ስልክ ቁጥርዎን ይፃፉ፡")
        
    elif ctx.user_data.get("waiting_phone"):
        ctx.user_data["phone"] = text
        ctx.user_data["waiting_phone"] = False
        ctx.user_data["waiting_receipt"] = True
        
        price = await db.get_setting("ticket_price")
        total = len(ctx.user_data["selected"]) * int(price)
        
        msg = f"🏦 *የክፍያ መረጃ*\nCBE: `{CBE_ACCOUNT}`\nTelebirr: `{TELEBIRR_ACCOUNT}`\n\n💰 ጠቅላላ፡ *{total} ETB*\n✅ ክፍያ ፈፅመው ደረሰኝ (Screenshot) ይላኩ።"
        await update.message.reply_text(msg, parse_mode="Markdown")

# ─── RECEIPT HANDLER ───
async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("waiting_receipt"): return
    
    user = update.effective_user
    file_id = update.message.photo[-1].file_id
    nums = ctx.user_data["selected"]
    full_name = ctx.user_data["full_name"]
    phone = ctx.user_data["phone"]
    
    # በጊዜያዊነት መያዝ
    payment_id = await db.add_payment(user.id, user.username or full_name, phone, nums, file_id, "CBE/Telebirr")
    await db.reserve_tickets(nums, user.id, user.username or full_name, phone)
    
    ctx.user_data["waiting_receipt"] = False
    await update.message.reply_text("✅ ደረሰኝዎ ተልኳል። አድሚን ሲያረጋግጥ እናሳውቆታለን።")

    # ለአድሚን መላክ
    admin_msg = f"💳 *አዲስ ክፍያ!*\n👤 ስም: {full_name}\n📞 ስልክ: {phone}\n🎟 ቁጥሮች: {nums}\n🆔 ID: #{payment_id}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve_{payment_id}"),
         InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject_{payment_id}")]
    ])
    
    for admin_id in ADMIN_IDS:
        await ctx.bot.send_photo(chat_id=admin_id, photo=file_id, caption=admin_msg, reply_markup=keyboard, parse_mode="Markdown")

# ─── APPROVE / REJECT CALLBACK ───
async def admin_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id): return
    
    action, p_id = query.data.split("_")
    payment = await db.get_payment(int(p_id))
    if not payment: return
    
    nums = list(map(int, payment[4].split(",")))
    user_id = payment[1]

    if action == "approve":
        await db.update_payment_status(int(p_id), "approved", query.from_user.id)
        await db.confirm_tickets(nums, user_id, payment[2], payment[3])
        await ctx.bot.send_message(chat_id=user_id, text=f"🎉 ክፍያዎ ተረጋግጧል! ቁጥሮችዎ፡ {nums}")
        await query.edit_message_caption("✅ ፀድቋል")
    else:
        await db.update_payment_status(int(p_id), "rejected", query.from_user.id)
        await db.free_tickets(nums)
        await ctx.bot.send_message(chat_id=user_id, text=f"❌ ክፍያዎ ውድቅ ተደርጓል (ቁጥር {nums})")
        await query.edit_message_caption("❌ ውድቅ ተደርጓል")

# ─── ADMIN PANEL ───
async def show_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    total = await db.get_setting("total_tickets")
    taken = await db.count_taken_tickets()
    price = await db.get_setting("ticket_price")
    
    text = f"👨‍💼 *Admin Panel*\n\n🎟 ተሸጠዋል: {taken}/{total}\n💰 ገቢ: {taken * int(price)} ETB"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Reset Lottery", callback_data="admin_reset")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_bc")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx._user_id = update.effective_user.id
    await update.message.reply_text("እንኳን ወደ እጣ መቁረጫ ቦት በሰላም መጡ!", reply_markup=get_home_keyboard(ctx))

# ─── MAIN ───
async def post_init(app): await db.init_db()

def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u,c: show_admin_panel(u,c) if is_admin(u.effective_user.id) else None))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(approve|reject)_"))
    
    app.run_polling()

if __name__ == "__main__":
    main()