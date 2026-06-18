import logging
import asyncio
from datetime import date
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import BadRequest
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        "pick_title": "🎟 *ቁጥር ምረጥ*",
        "free": "⬜ ነፃ",
        "pending_color": "🟡 በሂደት",
        "taken_color": "🔴 የተሸጠ",
        "selected_nums": "የመረጥካቸው",
        "none": "ምንም",
        "proceed_btn": "✅ ቀጥል ({n} ትኬት = {price} ብር)",
        "home_btn": "🏠 ዋና ገጽ",
        "cancel_btn": "❌ ሰርዝ",
        "back_btn": "◀️ ተመለስ",
        "payment_title": "💳 *ክፍያ*",
        "selected_nums_label": "🎟 የመረጡዋቸው ቁጥሮች",
        "total_label": "💰 ጠቅላላ",
        "choose_payment": "የክፍያ ዘዴ ይምረጡ:",
        "ask_name": "👤 *ሙሉ ስምዎን ይፃፉ:*\nምሳሌ: አበበ ከበደ",
        "ask_phone": "📞 *ስልክ ቁጥርዎን ይፃፉ:*\nምሳሌ: 0912345678",
        "invalid_phone": "⚠️ ትክክለኛ ስልክ ቁጥር ይፃፉ። ምሳሌ: 0912345678",
        "ask_receipt": "✅ ክፍያ ከፈፀሙ በኋላ *ደረሰኝ (screenshot)* ይላኩ።",
        "preview_title": "📋 *ማረጋገጫ - ከመላኩ በፊት ይፈትሹ:*",
        "name_label": "👤 ስም",
        "phone_label": "📞 ስልክ",
        "method_label": "💳 ዘዴ",
        "nums_label": "🎟 ቁጥሮች",
        "confirm_send": "✅ ልክ ነው፣ ላክ",
        "edit_name": "✏️ ስም ቀይር",
        "edit_phone": "📞 ስልክ ቀይር",
        "edit_nums": "🔢 ቁጥሮች ቀይር",
        "sent_ok": "✅ *ደረሰኝዎ ተልኳል!*\n👤 ስም: {name}\n📞 ስልክ: {phone}\n🎟 ቁጥሮች: {nums}\n💰 ድምር: {total} ብር\n💳 ዘዴ: {method}\n⏳ አድሚን ሲያረጋግጥ notification ይደርስዎታል።",
        "num_taken": "⚠️ ቁጥር {num} ቀድሞ ተይዟል! እንደገና ይምረጡ።",
        "receipt_only": "⚠️ እባክዎ *screenshot (ፎቶ)* ይላኩ።",
        "approved": "🎉 *ክፍያዎ ተረጋግጧል!*\n🎟 ቁጥሮቾ: {nums}\n💰 {total} ብር\n✅ ቁጥሮቾ ተያዘ። እጣ እስኪቆረጥ ድረስ ይጠብቁ!",
        "rejected": "❌ *ክፍያዎ አልተረጋገጠም።*\n🎟 ቁጥሮች: {nums}\nለጥያቄ አድሚን ያናግሩ።",
        "my_tickets_title": "🎟 *የእኔ ትኬቶች*",
        "no_tickets": "ምንም ትኬት የለዎትም።",
        "confirmed_label": "✅ የተረጋገጡ",
        "pending_label": "⏳ በሂደት",
        "limit_reached": "⚠️ እስከ {max} ትኬት ብቻ መምረጥ ይቻላል!",
        "choose_lang": "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:",
    },
    "en": {
        "pick_btn": "🎟 Pick Numbers",
        "my_tickets_btn": "📋 My Tickets",
        "admin_btn": "👨‍💼 Admin Panel",
        "pick_title": "🎟 *Pick a Number*",
        "free": "⬜ Free",
        "pending_color": "🟡 Pending",
        "taken_color": "🔴 Sold",
        "selected_nums": "Selected",
        "none": "None",
        "proceed_btn": "✅ Continue ({n} tickets = {price} ETB)",
        "home_btn": "🏠 Home",
        "cancel_btn": "❌ Cancel",
        "back_btn": "◀️ Back",
        "payment_title": "💳 *Payment*",
        "selected_nums_label": "🎟 Selected Numbers",
        "total_label": "💰 Total",
        "choose_payment": "Choose payment method:",
        "ask_name": "👤 *Enter your full name:*\nExample: Abebe Kebede",
        "ask_phone": "📞 *Enter your phone number:*\nExample: 0912345678",
        "invalid_phone": "⚠️ Please enter a valid phone number.",
        "ask_receipt": "✅ After payment, please send your *receipt (screenshot)*.",
        "preview_title": "📋 *Confirmation - Please review:*",
        "name_label": "👤 Name",
        "phone_label": "📞 Phone",
        "method_label": "💳 Method",
        "nums_label": "🎟 Numbers",
        "confirm_send": "✅ Correct, Send",
        "edit_name": "✏️ Edit Name",
        "edit_phone": "📞 Edit Phone",
        "edit_nums": "🔢 Change Numbers",
        "sent_ok": "✅ *Receipt sent!*\n👤 Name: {name}\n📞 Phone: {phone}\n🎟 Numbers: {nums}\n💰 Total: {total} ETB\n💳 Method: {method}\n⏳ You will be notified once admin confirms.",
        "num_taken": "⚠️ Number {num} is already taken! Please pick again.",
        "receipt_only": "⚠️ Please send a *screenshot (photo)*.",
        "approved": "🎉 *Payment confirmed!*\n🎟 Numbers: {nums}\n💰 {total} ETB\n✅ Your numbers are reserved. Wait for the draw!",
        "rejected": "❌ *Payment not confirmed.*\n🎟 Numbers: {nums}\nPlease contact admin.",
        "my_tickets_title": "🎟 *My Tickets*",
        "no_tickets": "You have no tickets.",
        "confirmed_label": "✅ Confirmed",
        "pending_label": "⏳ Pending",
        "limit_reached": "⚠️ Max {max} tickets allowed!",
        "choose_lang": "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:",
    },
    "or": {
        "pick_btn": "🎟 Lakkoofsa Filadhu",
        "my_tickets_btn": "📋 Tikeetii Koo",
        "admin_btn": "👨‍💼 Admin Panel",
        "pick_title": "🎟 *Lakkoofsa Filadhu*",
        "free": "⬜ Bilisaa",
        "pending_color": "🟡 Eegaa jira",
        "taken_color": "🔴 Gurgurame",
        "selected_nums": "Filatame",
        "none": "Homaa",
        "proceed_btn": "✅ Itti fufi ({n} tikeetii = {price} ETB)",
        "home_btn": "🏠 Fuula Jalqabaa",
        "cancel_btn": "❌ Haquu",
        "back_btn": "◀️ Deebi'i",
        "payment_title": "💳 *Kaffaltii*",
        "selected_nums_label": "🎟 Lakkoofsa filatame",
        "total_label": "💰 Waliigala",
        "choose_payment": "Mala kaffaltii filadhu:",
        "ask_name": "👤 *Maqaa guutuu kee barreessi:*\nFkn: Abebe Kebede",
        "ask_phone": "📞 *Lakkoofsa bilbilaa kee barreessi:*\nFkn: 0912345678",
        "invalid_phone": "⚠️ Lakkoofsa bilbilaa sirrii barreessi.",
        "ask_receipt": "✅ Kaffaltiis booda *beeksisa (screenshot)* ergi.",
        "preview_title": "📋 *Mirkaneessaa - Erguun dura ilaali:*",
        "name_label": "👤 Maqaa",
        "phone_label": "📞 Bilbila",
        "method_label": "💳 Mala",
        "nums_label": "🎟 Lakkoofsa",
        "confirm_send": "✅ Sirriidha, Ergi",
        "edit_name": "✏️ Maqaa jijjiiri",
        "edit_phone": "📞 Bilbila jijjiiri",
        "edit_nums": "🔢 Lakkoofsa jijjiiri",
        "sent_ok": "✅ *Beeksisni ergame!*\n👤 Maqaa: {name}\n📞 Bilbila: {phone}\n🎟 Lakkoofsa: {nums}\n💰 Waliigala: {total} ETB\n💳 Mala: {method}\n⏳ Admin mirkaneesu booda beeksifama.",
        "num_taken": "⚠️ Lakkoofsi {num} fudhataame! Ammas filadhu.",
        "receipt_only": "⚠️ *Screenshot (suuraa)* ergi.",
        "approved": "🎉 *Kaffaltiins mirkanaa'e!*\n🎟 Lakkoofsa: {nums}\n💰 {total} ETB\n✅ Lakkoofsi kee qabame. Fiigichaa eegi!",
        "rejected": "❌ *Kaffaltiins hin mirkanaa'in.*\n🎟 Lakkoofsa: {nums}\nAdmin quunnamaa.",
        "my_tickets_title": "🎟 *Tikeetii Koo*",
        "no_tickets": "Tikeetii hin qabdu.",
        "confirmed_label": "✅ Mirkanaa'e",
        "pending_label": "⏳ Eegaa jira",
        "limit_reached": "⚠️ Tikeetii {max} qofa filachu dandeessa!",
        "choose_lang": "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:",
    }
}

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
    """09123456789 → 09123456789# (ብቻ # ማከል)"""
    phone = str(phone).strip()
    if not phone:
        return ""
    return phone + "#"

def get_menu_keyboard(ctx):
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(ctx, "home_btn")), KeyboardButton(t(ctx, "cancel_btn"))]],
        resize_keyboard=True
    )

def remove_menu():
    return ReplyKeyboardRemove()

# ─────────────────────────────────────────
# GROUP LIST SENDER — ሁሉንም ቁጥሮች ይልካል
# ─────────────────────────────────────────
async def send_full_list_to_group(bot, total):
    """
    ሁሉም ቁጥሮች (taken + free) ወደ ግሩፕ ይላካሉ።
    ቀደም ብሎ የተላኩ messages ይሰረዛሉ።
    Format:
        12 👉 0912345678# ✅
        13 👉
        14 👉 0986532100# ✅
    """
    # 1. አሮጌ messages ሰርዝ
    old_msgs = await db.get_group_message_ids()
    for msg_id, chat_id in old_msgs:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Delete old group msg error: {e}")
    await db.clear_group_messages()

    # 2. ሁሉም ቲኬቶች data ይዘምን
    ticket_map = await db.get_all_tickets_full(total)

    # 3. በ50 chunks ይላካሉ
    CHUNK = 50
    title = await db.get_setting("lottery_title")
    new_msg_ids = []

    # Header
    try:
        hdr = await bot.send_message(
            chat_id=GROUP_ID,
            text=f"🎟 *{title}* — ሁሉም ቁጥሮች\n{'─'*25}",
            parse_mode="Markdown"
        )
        new_msg_ids.append(hdr.message_id)
    except Exception as e:
        logger.error(f"Header send error: {e}")

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
            await asyncio.sleep(0.4)
        except Exception as e:
            logger.error(f"Chunk send error: {e}")

    # 4. አዲስ message IDs ያስቀምጣል
    await db.save_group_message_ids(GROUP_ID, new_msg_ids)
    return len(new_msg_ids)

# ─────────────────────────────────────────
# LANGUAGE SELECTION
# ─────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
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
    await show_home(update, ctx)

# ─────────────────────────────────────────
# HOME PAGE
# ─────────────────────────────────────────
async def show_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not ctx.user_data.get("lang"):
        keyboard = [
            [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_or")],
        ]
        msg = "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.effective_message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    title = await db.get_setting("lottery_title")
    price = await db.get_setting("ticket_price")
    total = await db.get_setting("total_tickets")
    taken = await db.count_taken_tickets()
    remaining = int(total) - taken
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")

    sep = "─" * 28
    text = (
        f"🎉 *{title}*\n{sep}\n"
        f"🎟 ዋጋ: *{price} ETB*\n"
        f"🔢 ጠቅላላ: *{total}*\n"
        f"✅ የቀሩ: *{remaining}*\n{sep}\n"
        f"🥇 {prize1}\n"
        f"🥈 {prize2}\n"
        f"🥉 {prize3}\n{sep}"
    )

    keyboard = [
        [InlineKeyboardButton(t(ctx, "pick_btn"), callback_data="pick_numbers")],
        [InlineKeyboardButton(t(ctx, "my_tickets_btn"), callback_data="my_tickets")],
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton(t(ctx, "admin_btn"), callback_data="admin_panel")])

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.effective_message.reply_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await update.effective_message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def home_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["waiting_name"] = False
    ctx.user_data["waiting_phone"] = False
    ctx.user_data["waiting_receipt"] = False
    ctx.user_data["admin_action"] = None
    await show_home(update, ctx)

async def any_message_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    home_words = ["ዋና ገጽ", "Home", "Fuula Jalqabaa", "/start"]
    cancel_words = ["❌ ሰርዝ", "Cancel", "Haquu"]

    if any(w in text for w in home_words):
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = False
        ctx.user_data["waiting_receipt"] = False
        ctx.user_data["admin_action"] = None
        await show_home(update, ctx)
        return

    if any(w in text for w in cancel_words):
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = False
        ctx.user_data["waiting_receipt"] = False
        ctx.user_data["admin_action"] = None
        await update.message.reply_text("❌", reply_markup=remove_menu())
        await show_home(update, ctx)
        return

    if ctx.user_data.get("waiting_name") or ctx.user_data.get("waiting_phone") or ctx.user_data.get("admin_action"):
        await handle_text_input(update, ctx)
    elif not ctx.user_data.get("lang"):
        await show_home(update, ctx)

# ─────────────────────────────────────────
# NUMBER PICKER
# ─────────────────────────────────────────
async def show_number_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page: int = 0):
    total = int(await db.get_setting("total_tickets"))
    price = await db.get_setting("ticket_price")
    selected = ctx.user_data.get("selected", [])

    start_num = page * PAGE_SIZE + 1
    end_num = min(start_num + PAGE_SIZE - 1, total)

    tickets = await db.get_tickets_range(start_num, end_num)
    ticket_map = {t[0]: t[2] for t in tickets}  # number: status

    buttons = []
    row = []
    for num in range(start_num, end_num + 1):
        status = ticket_map.get(num, "free")
        if status == "taken":
            label = f"🔴{num}"
            data = f"taken_{num}"
        elif status == "reserved":
            label = f"🟡{num}"
            data = f"pending_{num}"
        elif num in selected:
            label = f"✅{num}"
            data = f"deselect_{num}"
        else:
            label = f"{num}"
            data = f"select_{num}"
        row.append(InlineKeyboardButton(label, callback_data=data))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"page_{page+1}"))
    buttons.append(nav)

    if selected:
        total_price = len(selected) * int(price)
        buttons.append([InlineKeyboardButton(
            t(ctx, "proceed_btn", n=len(selected), price=total_price),
            callback_data="proceed_payment"
        )])
    buttons.append([InlineKeyboardButton(t(ctx, "home_btn"), callback_data="main_menu")])

    lang = ctx.user_data.get("lang", "am")
    text = (
        f"{T[lang]['pick_title']} ({page+1}/{total_pages})\n"
        f"{'─'*25}\n"
        f"⬜=ነፃ  🟡=pending  🔴=የተሸጠ\n"
        f"{'─'*25}\n"
        f"{T[lang]['selected_nums']}: {selected if selected else T[lang]['none']}\n"
        f"(max {MAX_TICKETS_PER_USER})"
    )

    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except BadRequest:
        pass

async def pick_numbers_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["selected"] = []
    ctx.user_data["page"] = 0
    await show_number_page(update, ctx, 0)

async def number_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    selected = ctx.user_data.get("selected", [])
    page = ctx.user_data.get("page", 0)

    if data.startswith("select_"):
        num = int(data.split("_")[1])
        if len(selected) >= MAX_TICKETS_PER_USER:
            await query.answer(t(ctx, "limit_reached", max=MAX_TICKETS_PER_USER), show_alert=True)
            return
        if num not in selected:
            selected.append(num)
        ctx.user_data["selected"] = selected

    elif data.startswith("deselect_"):
        num = int(data.split("_")[1])
        if num in selected:
            selected.remove(num)
        ctx.user_data["selected"] = selected

    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        ctx.user_data["page"] = page

    elif data.startswith("taken_") or data.startswith("pending_"):
        await query.answer("🔴", show_alert=False)
        return

    elif data == "noop":
        await query.answer()
        return

    await query.answer()
    await show_number_page(update, ctx, page)

async def proceed_payment_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected = ctx.user_data.get("selected", [])
    if not selected:
        await query.answer("!", show_alert=True)
        return
    price = await db.get_setting("ticket_price")
    total_price = len(selected) * int(price)
    lang = ctx.user_data.get("lang", "am")
    text = (
        f"{T[lang]['payment_title']}\n{'─'*25}\n"
        f"{T[lang]['selected_nums_label']}: {', '.join(map(str, sorted(selected)))}\n"
        f"{T[lang]['total_label']}: *{total_price} ETB*\n{'─'*25}\n"
        f"{T[lang]['choose_payment']}"
    )
    keyboard = [
        [InlineKeyboardButton("🏦 CBE", callback_data="pay_cbe")],
        [InlineKeyboardButton("📱 Telebirr", callback_data="pay_telebirr")],
        [InlineKeyboardButton(t(ctx, "back_btn"), callback_data="pick_numbers")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def payment_method_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = "CBE" if query.data == "pay_cbe" else "Telebirr"
    ctx.user_data["payment_method"] = method
    ctx.user_data["waiting_name"] = True
    ctx.user_data["waiting_phone"] = False
    ctx.user_data["waiting_receipt"] = False
    await query.delete_message()
    await update.effective_message.reply_text(
        t(ctx, "ask_name"), parse_mode="Markdown",
        reply_markup=get_menu_keyboard(ctx)
    )

# ─────────────────────────────────────────
# RECEIPT HANDLER
# ─────────────────────────────────────────
async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("waiting_receipt"):
        await any_message_home(update, ctx)
        return

    user = update.effective_user
    photo = update.message.photo
    document = update.message.document

    if not photo and not document:
        await update.message.reply_text(t(ctx, "receipt_only"), parse_mode="Markdown")
        return

    file_id = photo[-1].file_id if photo else document.file_id
    selected = ctx.user_data.get("selected", [])
    method = ctx.user_data.get("payment_method", "CBE")
    full_name = ctx.user_data.get("full_name", user.full_name)
    phone = ctx.user_data.get("user_phone", "")
    price = await db.get_setting("ticket_price")
    total_price = len(selected) * int(price)

    ctx.user_data["receipt_file_id"] = file_id
    ctx.user_data["waiting_receipt"] = False

    lang = ctx.user_data.get("lang", "am")
    preview = (
        f"{T[lang]['preview_title']}\n{'─'*25}\n"
        f"{T[lang]['name_label']}: {full_name}\n"
        f"{T[lang]['phone_label']}: {phone}\n"
        f"{T[lang]['method_label']}: {method}\n"
        f"{T[lang]['nums_label']}: {', '.join(map(str, sorted(selected)))}\n"
        f"{T[lang]['total_label']}: {total_price} ETB\n"
        f"{'─'*25}"
    )
    keyboard = [
        [InlineKeyboardButton(t(ctx, "confirm_send"), callback_data="confirm_send")],
        [InlineKeyboardButton(t(ctx, "edit_name"), callback_data="edit_name")],
        [InlineKeyboardButton(t(ctx, "edit_phone"), callback_data="edit_phone")],
        [InlineKeyboardButton(t(ctx, "edit_nums"), callback_data="pick_numbers")],
        [InlineKeyboardButton(t(ctx, "home_btn"), callback_data="main_menu")],
    ]
    await update.message.reply_text(
        preview, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_send_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    selected = ctx.user_data.get("selected", [])
    method = ctx.user_data.get("payment_method", "CBE")
    full_name = ctx.user_data.get("full_name", user.full_name)
    phone = ctx.user_data.get("user_phone", "")
    file_id = ctx.user_data.get("receipt_file_id")
    price = await db.get_setting("ticket_price")
    total_price = len(selected) * int(price)

    # Check numbers still free
    for num in selected:
        ticket = await db.get_ticket(num)
        if ticket and ticket[4] == "taken":
            await query.edit_message_text(t(ctx, "num_taken", num=num))
            return

    username = f"@{user.username}" if user.username else full_name
    payment_id = await db.add_payment(user.id, username, phone, selected, file_id, method)
    await db.reserve_tickets(selected, user.id, username, phone)

    await query.edit_message_text(
        t(ctx, "sent_ok", name=full_name, phone=phone,
          nums=', '.join(map(str, sorted(selected))),
          total=total_price, method=method),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t(ctx, "home_btn"), callback_data="main_menu")
        ]])
    )

    # ── Admin notification (receipt + approve/reject buttons) ──
    admin_text = (
        f"💳 *አዲስ ክፍያ!*\n{'─'*25}\n"
        f"👤 {full_name}\n📞 {phone}\n🔗 {username}\n"
        f"🆔 `{user.id}`\n"
        f"🎟 {', '.join(map(str, sorted(selected)))}\n"
        f"💰 {total_price} ETB | {method}\n"
        f"🕐 ቁ: #{payment_id}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve_{payment_id}"),
        InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject_{payment_id}")
    ]])
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(
                chat_id=admin_id, photo=file_id,
                caption=admin_text, parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Admin notify: {e}")

    ctx.user_data["selected"] = []

async def edit_field_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data
    if field == "edit_name":
        ctx.user_data["waiting_name"] = True
        await query.edit_message_text(t(ctx, "ask_name"), parse_mode="Markdown")
    elif field == "edit_phone":
        ctx.user_data["waiting_phone"] = True
        await query.edit_message_text(t(ctx, "ask_phone"), parse_mode="Markdown")

# ─────────────────────────────────────────
# APPROVE / REJECT — auto group update
# ─────────────────────────────────────────
async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not is_admin(user.id):
        return

    action, payment_id = query.data.split("_", 1)
    payment_id = int(payment_id)
    payment = await db.get_payment(payment_id)
    if not payment:
        return

    p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status = payment[:8]
    if p_status != "pending":
        await query.answer("Already reviewed!", show_alert=True)
        return

    numbers = list(map(int, p_numbers.split(",")))
    price = await db.get_setting("ticket_price")
    total_price = len(numbers) * int(price)
    total = int(await db.get_setting("total_tickets"))

    if action == "approve":
        await db.update_payment_status(payment_id, "approved", user.id)
        await db.confirm_tickets(numbers, p_user_id, p_username, p_phone)

        # ── User notification ──
        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=T["am"]["approved"].format(
                    nums=', '.join(map(str, sorted(numbers))),
                    total=total_price
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User approved notify: {e}")

        await query.edit_message_caption(
            f"✅ *Approved*\n👤 {p_username}\n📞 {p_phone}\n🎟 {p_numbers}\n💰 {total_price} ETB",
            parse_mode="Markdown"
        )

        # ── Auto send full list to group ──
        try:
            await send_full_list_to_group(ctx.bot, total)
        except Exception as e:
            logger.error(f"Group update error: {e}")

        # All sold check
        taken = await db.count_taken_tickets()
        if taken >= total:
            for admin_id in ADMIN_IDS:
                try:
                    await ctx.bot.send_message(
                        chat_id=admin_id,
                        text=f"🎊 *ሁሉም ቁጥሮች ተሸጡ!* {taken}/{total}\nእጣ ለመቁረጥ /admin ይጠቀሙ።",
                        parse_mode="Markdown"
                    )
                except:
                    pass

    else:  # reject
        await db.update_payment_status(payment_id, "rejected", user.id)
        await db.free_tickets(numbers)

        # ── User notification ──
        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=T["am"]["rejected"].format(
                    nums=', '.join(map(str, sorted(numbers)))
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User rejected notify: {e}")

        await query.edit_message_caption(
            f"❌ *Rejected*\n👤 {p_username}\n📞 {p_phone}\n🎟 {p_numbers}",
            parse_mode="Markdown"
        )

# ─────────────────────────────────────────
# MY TICKETS
# ─────────────────────────────────────────
async def my_tickets_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    confirmed = await db.get_user_tickets(user.id, "taken")
    pending = await db.get_user_tickets(user.id, "reserved")
    lang = ctx.user_data.get("lang", "am")

    if not confirmed and not pending:
        text = f"{T[lang]['my_tickets_title']}\n\n{T[lang]['no_tickets']}"
    else:
        price = await db.get_setting("ticket_price")
        text = f"{T[lang]['my_tickets_title']}\n{'─'*25}\n"
        if confirmed:
            nums = sorted([t[0] for t in confirmed])
            text += f"{T[lang]['confirmed_label']}: {', '.join(map(str, nums))}\n💰 {len(nums)*int(price)} ETB\n\n"
        if pending:
            nums = sorted([t[0] for t in pending])
            text += f"{T[lang]['pending_label']}: {', '.join(map(str, nums))}\n"

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(t(ctx, "home_btn"), callback_data="main_menu")
        ]])
    )

# ─────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────
async def admin_panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await show_admin_panel(update, ctx)

async def show_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    total = int(await db.get_setting("total_tickets"))
    taken = await db.count_taken_tickets()
    pending_count = len(await db.get_pending_payments())
    price = await db.get_setting("ticket_price")
    total_revenue = taken * int(price)
    draw_btn_name = await db.get_setting("draw_button_name") or "🎊 እጣ ቁረጥ"

    text = (
        f"👨‍💼 *Admin Panel*\n{'─'*25}\n"
        f"🎟 ቁጥሮች: {taken}/{total}\n"
        f"💰 ጠቅላላ ገቢ: {total_revenue:,} ETB\n"
        f"⏳ Pending: {pending_count}\n"
        f"{'─'*25}"
    )
    keyboard = [
        [InlineKeyboardButton(f"⏳ Pending ({pending_count})", callback_data="admin_pending")],
        [InlineKeyboardButton("📊 ስታቲስቲክስ", callback_data="admin_stats")],
        [InlineKeyboardButton("📋 ሁሉም ቲኬቶች", callback_data="admin_all_tickets")],
        [InlineKeyboardButton("📤 ዝርዝር ወደ ግሩፕ ላክ", callback_data="admin_send_list")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton(f"{draw_btn_name}", callback_data="admin_draw_msg")],
        [InlineKeyboardButton("⚙️ ቅንብሮች", callback_data="admin_settings")],
        [InlineKeyboardButton("🔄 Reset", callback_data="admin_reset_confirm")],
        [InlineKeyboardButton("🏠 ዋና ገጽ", callback_data="main_menu")],
    ]
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.effective_message.reply_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await update.effective_message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ── ሁሉም ቲኬቶች (Admin view) ──
async def admin_all_tickets_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    payments = await db.get_all_approved_payments()
    if not payments:
        await query.edit_message_text(
            "📭 ምንም approved ክፍያ የለም።",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ ተመለስ", callback_data="admin_panel")
            ]])
        )
        return

    await query.edit_message_text(
        f"📋 *ሁሉም የተረጋገጡ ቲኬቶች* ({len(payments)})\nወደ DM እየተላኩ ነው...",
        parse_mode="Markdown"
    )

    price = int(await db.get_setting("ticket_price"))
    for p in payments:
        p_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_reviewed_at = p
        numbers = list(map(int, p_numbers.split(",")))
        total_price = len(numbers) * price
        caption = (
            f"✅ *ክፍያ #{p_id}*\n{'─'*20}\n"
            f"👤 {p_username}\n"
            f"📞 {p_phone}\n"
            f"🎟 {p_numbers}\n"
            f"💰 {total_price} ETB | {p_method}\n"
            f"🕐 {str(p_reviewed_at)[:16] if p_reviewed_at else 'N/A'}"
        )
        try:
            await ctx.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=p_receipt,
                caption=caption,
                parse_mode="Markdown"
            )
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"All tickets send: {e}")

# ── Admin stats ──
async def admin_stats_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total = int(await db.get_setting("total_tickets"))
    taken = await db.count_taken_tickets()
    price = int(await db.get_setting("ticket_price"))
    today_count = await db.count_tickets_today()
    pending = len(await db.get_pending_payments())

    text = (
        f"📊 *ስታቲስቲክስ*\n{'─'*25}\n"
        f"🎟 የተሸጡ: {taken}/{total}\n"
        f"⏳ Pending: {pending}\n"
        f"✅ የቀሩ: {total - taken}\n"
        f"📅 ዛሬ approved: {today_count}\n"
        f"{'─'*25}\n"
        f"💰 ጠቅላላ ገቢ: *{taken * price:,} ETB*\n"
        f"⏳ Pending ገቢ: *{pending * price:,} ETB*"
    )
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ተመለስ", callback_data="admin_panel")
        ]])
    )

# ── Manual send list to group ──
async def admin_send_list_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    total = int(await db.get_setting("total_tickets"))
    await query.edit_message_text("⏳ ወደ ግሩፕ እየተላከ ነው...")
    count = await send_full_list_to_group(ctx.bot, total)
    await ctx.bot.send_message(
        chat_id=update.effective_user.id,
        text=f"✅ {count} messages ወደ ግሩፕ ተልኳል!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ወደ ፓነል", callback_data="admin_panel")
        ]])
    )

# ── Admin pending ──
async def admin_pending_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    pending = await db.get_pending_payments()
    if not pending:
        await query.edit_message_text(
            "✅ Pending ክፍያ የለም።",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ ተመለስ", callback_data="admin_panel")
            ]])
        )
        return

    price = await db.get_setting("ticket_price")
    await query.edit_message_text(f"⏳ {len(pending)} pending ክፍያዎች:")
    for p in pending[:10]:
        p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status = p[:8]
        numbers = list(map(int, p_numbers.split(",")))
        total_price = len(numbers) * int(price)
        caption = (
            f"💳 *#{p_id}*\n👤 {p_username}\n📞 {p_phone}\n"
            f"🎟 {p_numbers}\n💰 {total_price} ETB | {p_method}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve_{p_id}"),
            InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject_{p_id}")
        ]])
        try:
            await ctx.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=p_receipt, caption=caption,
                parse_mode="Markdown", reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Pending photo: {e}")

# ── Admin settings ──
async def admin_settings_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    price = await db.get_setting("ticket_price")
    total = await db.get_setting("total_tickets")
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")
    text = (
        f"⚙️ *ቅንብሮች*\n{'─'*25}\n"
        f"🔢 ቁጥሮች: {total}\n💰 ዋጋ: {price} ETB\n"
        f"🥇 {prize1}\n🥈 {prize2}\n🥉 {prize3}"
    )
    keyboard = [
        [InlineKeyboardButton("🔢 ቁጥሮች ብዛት", callback_data="set_tickets")],
        [InlineKeyboardButton("💰 ዋጋ", callback_data="set_price")],
        [InlineKeyboardButton("🥇 1ኛ ሽልማት", callback_data="set_prize_1")],
        [InlineKeyboardButton("🥈 2ኛ ሽልማት", callback_data="set_prize_2")],
        [InlineKeyboardButton("🥉 3ኛ ሽልማት", callback_data="set_prize_3")],
        [InlineKeyboardButton("◀️ ተመለስ", callback_data="admin_panel")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def set_field_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data
    prompts = {
        "set_tickets": "🔢 አዲስ የቁጥሮች ብዛት ፃፍ (10-1000):",
        "set_price": "💰 አዲስ ዋጋ ፃፍ (ETB):",
        "set_prize_1": "🥇 1ኛ ሽልማት ፃፍ:",
        "set_prize_2": "🥈 2ኛ ሽልማት ፃፍ:",
        "set_prize_3": "🥉 3ኛ ሽልማት ፃፍ:",
    }
    ctx.user_data["admin_action"] = field
    await query.edit_message_text(
        prompts.get(field, "ፃፍ:"),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ሰርዝ", callback_data="admin_settings")
        ]])
    )

# ── Broadcast ──
async def admin_broadcast_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "broadcast"
    await query.edit_message_text(
        "📢 *Broadcast መልዕክት ፃፍ:*\n(ለሁሉም ተጠቃሚዎች + ግሩፕ ይላካል)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ሰርዝ", callback_data="admin_panel")
        ]])
    )

# ── Draw message ──
async def admin_draw_msg_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "set_draw_msg"
    draw_btn_name = await db.get_setting("draw_button_name") or "🎊 እጣ ቁረጥ"
    current_msg = await db.get_setting("draw_message") or ""
    await query.edit_message_text(
        f"🎊 *Draw Settings*\n{'─'*25}\n"
        f"አሁን: {draw_btn_name}\n"
        f"መልዕክት: {current_msg or 'N/A'}\n\n"
        f"አዲስ ፃፍ (ቅርጸ: `ስም | መልዕክት`):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 አሁን ያለውን ላክ", callback_data="admin_draw_send")],
            [InlineKeyboardButton("◀️ ተመለስ", callback_data="admin_panel")]
        ])
    )

async def admin_draw_send_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draw_msg = await db.get_setting("draw_message") or "🎊 እጣ ተቆርጧል!"
    await query.edit_message_text(
        f"📋 *Preview:*\n{'─'*25}\n{draw_msg}\n{'─'*25}\nለሁሉም ተጠቃሚዎች + ግሩፕ ይላካል። ትክክል ነው?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ አዎ፣ ላክ", callback_data="admin_draw_confirm")],
            [InlineKeyboardButton("❌ አይ", callback_data="admin_panel")]
        ])
    )

async def admin_draw_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    draw_msg = await db.get_setting("draw_message") or "🎊 እጣ ተቆርጧል!"
    users = await db.get_all_users()
    sent = 0
    for (uid,) in users:
        try:
            await ctx.bot.send_message(chat_id=uid, text=f"🎊 {draw_msg}")
            sent += 1
        except:
            pass
    try:
        await ctx.bot.send_message(chat_id=GROUP_ID, text=f"🎊 {draw_msg}")
    except Exception as e:
        logger.error(f"Group draw: {e}")
    await query.edit_message_text(
        f"✅ ለ {sent} ተጠቃሚዎች + ግሩፕ ተልኳል!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ወደ ፓነል", callback_data="admin_panel")
        ]])
    )

# ── Reset ──
async def admin_reset_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⚠️ *እርግጠኛ ነህ? ሁሉም ቁጥሮች እና ክፍያዎች ይጠፋሉ!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ አዎ Reset", callback_data="admin_reset_yes")],
            [InlineKeyboardButton("❌ አይ", callback_data="admin_panel")]
        ])
    )

async def admin_reset_yes_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await db.reset_lottery()
    await query.edit_message_text(
        "✅ *አዲስ እጣ ተጀምሯል!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ወደ ፓነል", callback_data="admin_panel")
        ]])
    )

async def broadcast_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    msg = ctx.user_data.get("broadcast_msg", "")
    users = await db.get_all_users()
    sent = 0
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
        f"✅ ለ {sent} ተጠቃሚዎች + ግሩፕ ተልኳል!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ወደ ፓነል", callback_data="admin_panel")
        ]])
    )

# ─────────────────────────────────────────
# TEXT INPUT HANDLER
# ─────────────────────────────────────────
async def handle_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()

    if ctx.user_data.get("waiting_name"):
        ctx.user_data["full_name"] = text_input
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = True
        await update.message.reply_text(t(ctx, "ask_phone"), parse_mode="Markdown")
        return

    if ctx.user_data.get("waiting_phone"):
        digits = text_input.replace(" ", "").replace("-", "")
        if not digits.isdigit() or len(digits) < 9:
            await update.message.reply_text(t(ctx, "invalid_phone"))
            return
        ctx.user_data["user_phone"] = digits
        ctx.user_data["waiting_phone"] = False

        method = ctx.user_data.get("payment_method", "CBE")
        selected = ctx.user_data.get("selected", [])
        price = await db.get_setting("ticket_price")
        total_price = len(selected) * int(price)

        if method == "CBE":
            account_text = f"🏦 *CBE*\n`{CBE_ACCOUNT}`\n👤 {CBE_NAME}"
        else:
            account_text = f"📱 *Telebirr*\n`{TELEBIRR_ACCOUNT}`\n👤 {TELEBIRR_NAME}"

        await update.message.reply_text(
            f"{account_text}\n{'─'*25}\n💰 *{total_price} ETB*\n{'─'*25}\n{t(ctx, 'ask_receipt')}",
            parse_mode="Markdown",
            reply_markup=get_menu_keyboard(ctx)
        )
        ctx.user_data["waiting_receipt"] = True
        return

    action = ctx.user_data.get("admin_action")
    if not action or not is_admin(update.effective_user.id):
        return

    ctx.user_data["admin_action"] = None

    if action == "set_tickets":
        try:
            val = int(text_input)
            if 10 <= val <= 1000:
                await db.set_setting("total_tickets", val)
                await update.message.reply_text(f"✅ ቁጥሮች → {val}")
            else:
                await update.message.reply_text("⚠️ 10-1000 መካከል ፃፍ።")
        except:
            await update.message.reply_text("⚠️ ቁጥር ብቻ ፃፍ።")

    elif action == "set_price":
        try:
            val = int(text_input)
            await db.set_setting("ticket_price", val)
            await update.message.reply_text(f"✅ ዋጋ → {val} ETB")
        except:
            await update.message.reply_text("⚠️ ቁጥር ብቻ ፃፍ።")

    elif action in ["set_prize_1", "set_prize_2", "set_prize_3"]:
        key = action.replace("set_", "")
        await db.set_setting(key, text_input)
        await update.message.reply_text(f"✅ {text_input}")

    elif action == "broadcast":
        ctx.user_data["broadcast_msg"] = text_input
        await update.message.reply_text(
            f"📋 *Preview:*\n{'─'*25}\n📢 {text_input}\n{'─'*25}\nለሁሉም + ግሩፕ ይላካል። ትክክል ነው?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ አዎ፣ ላክ", callback_data="broadcast_confirm")],
                [InlineKeyboardButton("✏️ ቀይር", callback_data="admin_broadcast")],
                [InlineKeyboardButton("❌ ሰርዝ", callback_data="admin_panel")]
            ])
        )

    elif action == "set_draw_msg":
        parts = text_input.split("|", 1)
        if len(parts) == 2:
            btn_name = parts[0].strip()
            msg = parts[1].strip()
            await db.set_setting("draw_button_name", btn_name)
            await db.set_setting("draw_message", msg)
            await update.message.reply_text(f"✅ ስም: {btn_name}\nመልዕክት: {msg}")
        else:
            await db.set_setting("draw_message", text_input)
            await update.message.reply_text("✅ መልዕክት ተቀምጧል!")

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
async def post_init(application):
    await db.init_db()

def main():
    keep_alive()
        global app
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()


    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u, c: show_admin_panel(u, c) if is_admin(u.effective_user.id) else None))

    app.add_handler(CallbackQueryHandler(lang_cb, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(home_cb, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(pick_numbers_cb, pattern="^pick_numbers$"))
    app.add_handler(CallbackQueryHandler(number_cb, pattern="^(select|deselect|taken|pending|page|noop)_"))
    app.add_handler(CallbackQueryHandler(proceed_payment_cb, pattern="^proceed_payment$"))
    app.add_handler(CallbackQueryHandler(payment_method_cb, pattern="^pay_(cbe|telebirr)$"))
    app.add_handler(CallbackQueryHandler(confirm_send_cb, pattern="^confirm_send$"))
    app.add_handler(CallbackQueryHandler(edit_field_cb, pattern="^edit_(name|phone)$"))
    app.add_handler(CallbackQueryHandler(my_tickets_cb, pattern="^my_tickets$"))

    app.add_handler(CallbackQueryHandler(admin_panel_cb, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_pending_cb, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_stats_cb, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_all_tickets_cb, pattern="^admin_all_tickets$"))
    app.add_handler(CallbackQueryHandler(admin_settings_cb, pattern="^admin_settings$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_cb, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(broadcast_confirm_cb, pattern="^broadcast_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_send_list_cb, pattern="^admin_send_list$"))
    app.add_handler(CallbackQueryHandler(admin_draw_msg_cb, pattern="^admin_draw_msg$"))
    app.add_handler(CallbackQueryHandler(admin_draw_send_cb, pattern="^admin_draw_send$"))
    app.add_handler(CallbackQueryHandler(admin_draw_confirm_cb, pattern="^admin_draw_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_reset_confirm_cb, pattern="^admin_reset_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_reset_yes_cb, pattern="^admin_reset_yes$"))
    app.add_handler(CallbackQueryHandler(set_field_cb, pattern="^set_(tickets|price|prize_)"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb, pattern="^(approve|reject)_"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message_home))

from flask import Flask
import threading

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is Running!"

def run_telegram_bot():
    app.run_polling(drop_pending_updates=True)

bot_thread = threading.Thread(target=run_telegram_bot)
bot_thread.start()

flask_app.run(host="0.0.0.0", port=10000)
