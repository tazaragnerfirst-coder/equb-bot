import logging, asyncio, json, re
from threading import Thread
from flask import Flask
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Bot is Online"
def keep_alive(): Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080), daemon=True).start()

T = {
    "am": {"pick": "🎟 ቁጥር ምረጥ", "my": "📋 የእኔ ትኬቶች", "adm": "👨‍💼 አድሚን", "ask_n": "👤 ሙሉ ስምዎን ይፃፉ:", "ask_p": "📞 ስልክ ቁጥር ያስገቡ (09...):", "err_p": "⚠️ ስህተት! ትክክለኛ ስልክ ያስገቡ።", "app": "🎉 ተረጋግጧል! ቁጥሮች: {nums}", "rej": "❌ ይቅርታ፣ ደረሰኝዎ አልተረጋገጠም።"},
    "en": {"pick": "🎟 Pick Numbers", "my": "📋 My Tickets", "adm": "👨‍💼 Admin", "ask_n": "👤 Enter Full Name:", "ask_p": "📞 Enter Phone (09...):", "err_p": "⚠️ Invalid phone number.", "app": "🎉 Confirmed! Numbers: {nums}", "rej": "❌ Sorry, your receipt was rejected."},
    "or": {"pick": "🎟 Lakkoofsa Filadhu", "my": "📋 Tikeetii Koo", "adm": "👨‍💼 Admin", "ask_n": "👤 Maqaa keessan barreessaa:", "ask_p": "📞 Bilbila keessan (09...):", "err_p": "⚠️ Dogoggora! Bilbila sirrii galchaa.", "app": "🎉 Mirkanaa'eera! Lakkoofsa: {nums}", "rej": "❌ Kaffaltiin keessan hin mirkanoofne."}
}

async def update_group_list(bot):
    total = int(await db.get_setting("total_tickets"))
    ticket_map = await db.get_all_tickets_full(total)
    CHUNK = 40
    for i in range(1, total + 1, CHUNK):
        lines = [f"{n} 👉 {str(ticket_map.get(n)[0])+'#' if ticket_map.get(n) and ticket_map.get(n)[1]=='taken' else ''} {'✅' if ticket_map.get(n) and ticket_map.get(n)[1]=='taken' else ''}" for n in range(i, min(i+CHUNK, total+1))]
        await bot.send_message(chat_id=GROUP_ID, text="\n".join(lines))

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("አማርኛ", callback_data="l_am"), InlineKeyboardButton("English", callback_data="l_en"), InlineKeyboardButton("Oromoo", callback_data="l_or")]]
    await update.message.reply_text("Choose Language / Afaan filadhu:", reply_markup=InlineKeyboardMarkup(kb))

async def lang_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = query.data.split("_")[1]
    ctx.user_data["lang"] = lang
    await query.answer()
    await query.delete_message()
    
    price = await db.get_setting("ticket_price")
    title = await db.get_setting("lottery_title")
    kb = [[KeyboardButton(T[lang]["pick"], web_app=WebAppInfo(url="https://tazaragnerfirst-coder.github.io/equb-bot/"))], [KeyboardButton(T[lang]["my"])]]
    if update.effective_user.id in ADMIN_IDS: kb.append([KeyboardButton(T[lang]["adm"])])
    
    await ctx.bot.send_message(chat_id=update.effective_user.id, text=f"🎉 {title}\n🎟 Price: {price} ETB", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = json.loads(update.effective_message.web_app_data.data)
    ctx.user_data.update({"nums": data["numbers"], "step": "name"})
    await update.message.reply_text(T[ctx.user_data.get("lang", "am")]["ask_n"])

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt, step, lang = update.message.text, ctx.user_data.get("step"), ctx.user_data.get("lang", "am")
    if step == "name":
        ctx.user_data.update({"name": txt, "step": "phone"})
        await update.message.reply_text(T[lang]["ask_p"])
    elif step == "phone":
        if re.match(r"^(09|07)\d{8}$", txt):
            ctx.user_data.update({"phone": txt, "step": "receipt"})
            p = int(await db.get_setting("ticket_price"))
            await update.message.reply_text(f"💰 Total: {len(ctx.user_data['nums'])*p} ETB\nCBE: `{CBE_ACCOUNT}`\nSend Receipt (Photo):")
        else: await update.message.reply_text(T[lang]["err_p"])

async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if ctx.user_data.get("step") != "receipt": return
    fid, nums = update.message.photo[-1].file_id, ctx.user_data["nums"]
    p_id = await db.add_payment(update.effective_user.id, ctx.user_data["name"], ctx.user_data["phone"], nums, fid, "Bank")
    await db.reserve_tickets(nums, update.effective_user.id, ctx.user_data["name"], ctx.user_data["phone"])
    for adm in ADMIN_IDS:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"a_{p_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"r_{p_id}")]])
        await ctx.bot.send_photo(adm, fid, f"👤 {ctx.user_data['name']}\n📞 {ctx.user_data['phone']}\n🎟 {nums}", reply_markup=kb)
    await update.message.reply_text("✅ Sent! Waiting for admin confirmation.")

async def admin_decision(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, pid = query.data.split("_")
    pay = await db.get_payment(int(pid))
    nums = list(map(int, pay[4].split(",")))
    if action == "a":
        await db.confirm_tickets(nums, pay[1], pay[2], pay[3])
        await ctx.bot.send_message(pay[1], T["am"]["app"].format(nums=nums))
        await update_group_list(ctx.bot)
        await query.edit_message_caption("✅ Approved")
    else:
        await db.free_tickets(nums)
        await ctx.bot.send_message(pay[1], T["am"]["rej"])
        await query.edit_message_caption("❌ Rejected")

def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).post_init(lambda a: db.init_db()).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lang_cb, pattern="^l_"))
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^(a|r)_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__": main()