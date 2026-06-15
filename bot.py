import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.error import BadRequest
import database as db
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# States
(STATE_CHOOSE_NUMBERS, STATE_CHOOSE_PAYMENT, STATE_SEND_RECEIPT,
 STATE_ADMIN_BROADCAST, STATE_ADMIN_SET_TICKETS, STATE_ADMIN_SET_PRICE,
 STATE_ADMIN_SET_PRIZE, STATE_ADMIN_DRAW) = range(8)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def mask_phone(phone):
    if len(phone) >= 2:
        return phone[:-1] + "*"
    return phone + "*"

# ─────────────────────────────────────────
# START
# ─────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    title = await db.get_setting("lottery_title")
    price = await db.get_setting("ticket_price")
    total = await db.get_setting("total_tickets")
    taken = await db.count_taken_tickets()
    remaining = int(total) - taken

    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")

    text = (
        f"🎉 *{title}*\n"
        f"{'─'*30}\n"
        f"🎟 የ1 ትኬት ዋጋ: *{price} ብር*\n"
        f"🔢 ጠቅላላ ቁጥሮች: *{total}*\n"
        f"✅ የቀሩ ቁጥሮች: *{remaining}*\n"
        f"{'─'*30}\n"
        f"🥇 1ኛ: {prize1}\n"
        f"🥈 2ኛ: {prize2}\n"
        f"🥉 3ኛ: {prize3}\n"
        f"{'─'*30}\n"
        f"እስከ *5 ቁጥሮች* ድረስ መምረጥ ይችላሉ።"
    )

    keyboard = [
        [InlineKeyboardButton("🎟 ቁጥር ምረጥ", callback_data="pick_numbers")],
        [InlineKeyboardButton("📋 የእኔ ትኬቶች", callback_data="my_tickets")],
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("👨‍💼 አድሚን ፓነል", callback_data="admin_panel")])

    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
    ticket_map = {t[0]: t[1] for t in tickets}

    buttons = []
    row = []
    for num in range(start_num, end_num + 1):
        status = ticket_map.get(num, "free")
        if status == "taken":
            label = f"🔴{num}"
            data = f"taken_{num}"
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

    # Navigation
    nav = []
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"page_{page+1}"))
    buttons.append(nav)

    if selected:
        total_price = len(selected) * int(price)
        buttons.append([
            InlineKeyboardButton(
                f"✅ ቀጥል ({len(selected)} ትኬት = {total_price} ብር)",
                callback_data="proceed_payment"
            )
        ])
    buttons.append([InlineKeyboardButton("🏠 ዋና ምናሌ", callback_data="main_menu")])

    text = (
        f"🎟 *ቁጥር ምረጥ* (ገጽ {page+1}/{total_pages})\n"
        f"{'─'*25}\n"
        f"🟢 ነፃ  🔴 የተያዘ  ✅ የመረጥከው\n"
        f"{'─'*25}\n"
        f"የመረጥካቸው: {selected if selected else 'ምንም'}\n"
        f"(እስከ {MAX_TICKETS_PER_USER} ቁጥሮች)"
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
            await query.answer(
                f"⚠️ እስከ {MAX_TICKETS_PER_USER} ቁጥሮች ብቻ መምረጥ ይቻላል!",
                show_alert=True
            )
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

    elif data == "taken":
        await query.answer("🔴 ይህ ቁጥር ተይዟል!", show_alert=True)
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
        await query.answer("ምንም ቁጥር አልመረጡም!", show_alert=True)
        return

    price = await db.get_setting("ticket_price")
    total_price = len(selected) * int(price)

    text = (
        f"💳 *ክፍያ*\n"
        f"{'─'*25}\n"
        f"🎟 የመረጡዋቸው ቁጥሮች: {', '.join(map(str, sorted(selected)))}\n"
        f"💰 ጠቅላላ: *{total_price} ብር*\n"
        f"{'─'*25}\n"
        f"የክፍያ ዘዴ ይምረጡ:"
    )

    keyboard = [
        [InlineKeyboardButton("🏦 CBE", callback_data="pay_cbe")],
        [InlineKeyboardButton("📱 Telebirr", callback_data="pay_telebirr")],
        [InlineKeyboardButton("◀️ ተመለስ", callback_data="pick_numbers")],
    ]
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def payment_method_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = "CBE" if query.data == "pay_cbe" else "Telebirr"
    ctx.user_data["payment_method"] = method
    ctx.user_data["waiting_name"] = True
    ctx.user_data["waiting_phone"] = False
    ctx.user_data["waiting_receipt"] = False

    await query.edit_message_text(
        "👤 *ሙሉ ስምዎን ይፃፉ:*\nምሳሌ: አበበ ከበደ",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ተመለስ", callback_data="proceed_payment")
        ]])
    )

async def handle_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.user_data.get("waiting_receipt"):
        return

    user = update.effective_user
    photo = update.message.photo
    document = update.message.document

    if not photo and not document:
        await update.message.reply_text(
            "⚠️ እባክዎ *screenshot (ፎቶ)* ይላኩ።",
            parse_mode="Markdown"
        )
        return

    file_id = photo[-1].file_id if photo else document.file_id
    selected = ctx.user_data.get("selected", [])
    method = ctx.user_data.get("payment_method", "CBE")
    full_name = ctx.user_data.get("full_name", user.full_name)
    phone = ctx.user_data.get("user_phone", str(user.id))
    price = await db.get_setting("ticket_price")
    total_price = len(selected) * int(price)

    # Check if numbers still free
    for num in selected:
        ticket = await db.get_ticket(num)
        if ticket and ticket[4] == "taken":
            await update.message.reply_text(
                f"⚠️ ቁጥር {num} ቀድሞ ተይዟል! /start ብለው እንደገና ይምረጡ።"
            )
            ctx.user_data["waiting_receipt"] = False
            return

    username = f"@{user.username}" if user.username else full_name

    payment_id = await db.add_payment(
        user.id, username, phone, selected, file_id, method
    )
    await db.reserve_tickets(selected, user.id, username, phone)

    # Notify user
    await update.message.reply_text(
        f"✅ *ደረሰኝዎ ተልኳል!*\n"
        f"{'─'*25}\n"
        f"👤 ስም: {full_name}\n"
        f"📞 ስልክ: {phone}\n"
        f"🎟 ቁጥሮች: {', '.join(map(str, sorted(selected)))}\n"
        f"💰 ድምር: {total_price} ብር\n"
        f"💳 ዘዴ: {method}\n"
        f"{'─'*25}\n"
        f"⏳ አድሚን ሲያረጋግጥ notification ይደርስዎታል።",
        parse_mode="Markdown"
    )

    # Notify admins
    admin_text = (
        f"💳 *አዲስ ክፍያ ተልኳል!*\n"
        f"{'─'*25}\n"
        f"👤 ስም: {full_name}\n"
        f"📞 ስልክ: {phone}\n"
        f"🔗 TG: {username}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🎟 ቁጥሮች: {', '.join(map(str, sorted(selected)))}\n"
        f"💰 ድምር: {total_price} ብር\n"
        f"💳 ዘዴ: {method}\n"
        f"{'─'*25}"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve_{payment_id}"),
            InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject_{payment_id}")
        ]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=admin_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Admin notify error: {e}")

    ctx.user_data["waiting_receipt"] = False
    ctx.user_data["waiting_name"] = False
    ctx.user_data["waiting_phone"] = False
    ctx.user_data["selected"] = []

# ─────────────────────────────────────────
# ADMIN - APPROVE / REJECT
# ─────────────────────────────────────────
async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not is_admin(user.id):
        await query.answer("⛔ አድሚን ብቻ!", show_alert=True)
        return

    action, payment_id = query.data.split("_", 1)
    payment_id = int(payment_id)
    payment = await db.get_payment(payment_id)

    if not payment:
        await query.edit_message_caption("⚠️ ክፍያ አልተገኘም።")
        return

    p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status, *_ = payment

    if p_status != "pending":
        await query.edit_message_caption(
            f"⚠️ ይህ ክፍያ ቀድሞ {'✅ ተረጋግጧል' if p_status == 'approved' else '❌ ውድቅ ሆኗል'}።"
        )
        return

    numbers = list(map(int, p_numbers.split(",")))
    price = await db.get_setting("ticket_price")
    total_price = len(numbers) * int(price)

    if action == "approve":
        await db.update_payment_status(payment_id, "approved", user.id)
        await db.confirm_tickets(numbers, p_user_id, p_username, p_phone)

        # Notify user
        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=(
                    f"🎉 *ክፍያዎ ተረጋግጧል!*\n"
                    f"{'─'*25}\n"
                    f"🎟 ቁጥሮቾ: {', '.join(map(str, sorted(numbers)))}\n"
                    f"💰 {total_price} ብር\n"
                    f"{'─'*25}\n"
                    f"✅ ቁጥሮቾ ተያዘ። እጣ እስኪቆረጥ ድረስ ይጠብቁ!"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User notify error: {e}")

        # Update group message
        await update_group_message(ctx, numbers, p_phone or str(p_user_id))

        await query.edit_message_caption(
            f"✅ *ተረጋግጧል!*\n👤 {p_username}\n🎟 {p_numbers}",
            parse_mode="Markdown"
        )

        # Check if all tickets taken
        total = int(await db.get_setting("total_tickets"))
        taken = await db.count_taken_tickets()
        if taken >= total:
            for admin_id in ADMIN_IDS:
                try:
                    await ctx.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"🎊 *ሁሉም ቁጥሮች ተሸጡ!*\n"
                            f"✅ {taken}/{total} ቁጥሮች ተሸጠዋል።\n"
                            f"እጣ ለመቁረጥ /admin ይጠቀሙ።"
                        ),
                        parse_mode="Markdown"
                    )
                except:
                    pass

    else:  # reject
        await db.update_payment_status(payment_id, "rejected", user.id)
        await db.free_tickets(numbers)

        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=(
                    f"❌ *ክፍያዎ አልተረጋገጠም።*\n"
                    f"{'─'*25}\n"
                    f"🎟 ቁጥሮች: {', '.join(map(str, sorted(numbers)))}\n"
                    f"{'─'*25}\n"
                    f"ለጥያቄ አድሚን ያናግሩ።"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User notify error: {e}")

        await query.edit_message_caption(
            f"❌ *ውድቅ ሆኗል።*\n👤 {p_username}\n🎟 {p_numbers}",
            parse_mode="Markdown"
        )

# ─────────────────────────────────────────
# GROUP MESSAGE UPDATE
# ─────────────────────────────────────────
async def update_group_message(ctx, numbers, phone):
    """Update the group message for the confirmed ticket numbers"""
    try:
        total = int(await db.get_setting("total_tickets"))
        group_msgs = await db.get_group_messages()

        masked = mask_phone(phone)

        for num in numbers:
            for msg in group_msgs:
                msg_id, start, end = msg[1], msg[2], msg[3]
                if start <= num <= end:
                    # Rebuild that message
                    tickets = await db.get_tickets_range(start, end)
                    ticket_map = {t[0]: (t[1], t[2], t[4]) for t in tickets}

                    lines = []
                    for n in range(start, end + 1):
                        info = ticket_map.get(n)
                        if info and info[2] == "taken":
                            ph = info[1] if info[1] else str(info[0])
                            lines.append(f"{n} 👉 {mask_phone(ph)} ✅")
                        else:
                            lines.append(f"{n} 👉")

                    new_text = "\n".join(lines)
                    try:
                        await ctx.bot.edit_message_text(
                            chat_id=GROUP_ID,
                            message_id=msg_id,
                            text=new_text
                        )
                    except Exception as e:
                        logger.error(f"Group edit error: {e}")
                    break
    except Exception as e:
        logger.error(f"update_group_message error: {e}")

# ─────────────────────────────────────────
# ADMIN PANEL
# ─────────────────────────────────────────
async def admin_panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not is_admin(user.id):
        await query.answer("⛔ አድሚን ብቻ!", show_alert=True)
        return

    total = int(await db.get_setting("total_tickets"))
    taken = await db.count_taken_tickets()
    price = await db.get_setting("ticket_price")
    pending = await db.get_pending_payments()

    text = (
        f"👨‍💼 *አድሚን ፓነል*\n"
        f"{'─'*25}\n"
        f"🎟 ቁጥሮች: {taken}/{total}\n"
        f"💰 ዋጋ: {price} ብር\n"
        f"⏳ Pending ክፍያዎች: {len(pending)}\n"
        f"{'─'*25}"
    )
    keyboard = [
        [InlineKeyboardButton(f"⏳ Pending ({len(pending)})", callback_data="admin_pending")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⚙️ ቅንብሮች", callback_data="admin_settings")],
        [InlineKeyboardButton("🎊 እጣ ቁረጥ", callback_data="admin_draw")],
        [InlineKeyboardButton("📤 ዝርዝር ወደ ግሩፕ ላክ", callback_data="admin_send_list")],
        [InlineKeyboardButton("🔄 Reset (አዲስ እጣ)", callback_data="admin_reset_confirm")],
        [InlineKeyboardButton("🏠 ዋና ምናሌ", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
    for p in pending[:10]:  # Show max 10
        p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status, p_created, *_ = p
        numbers = list(map(int, p_numbers.split(",")))
        total_price = len(numbers) * int(price)
        caption = (
            f"💳 *Pending ክፍያ #{p_id}*\n"
            f"👤 {p_username}\n"
            f"🎟 {p_numbers}\n"
            f"💰 {total_price} ብር | {p_method}\n"
            f"🕐 {p_created[:16]}"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve_{p_id}"),
                InlineKeyboardButton("❌ ውድቅ", callback_data=f"reject_{p_id}")
            ]
        ])
        try:
            await ctx.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=p_receipt,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Send pending error: {e}")

async def admin_settings_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        return

    price = await db.get_setting("ticket_price")
    total = await db.get_setting("total_tickets")
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")

    text = (
        f"⚙️ *ቅንብሮች*\n"
        f"{'─'*25}\n"
        f"🔢 ቁጥሮች: {total}\n"
        f"💰 ዋጋ: {price} ብር\n"
        f"🥇 1ኛ: {prize1}\n"
        f"🥈 2ኛ: {prize2}\n"
        f"🥉 3ኛ: {prize3}"
    )
    keyboard = [
        [InlineKeyboardButton("🔢 ቁጥሮች ብዛት ቀይር", callback_data="set_tickets")],
        [InlineKeyboardButton("💰 ዋጋ ቀይር", callback_data="set_price")],
        [InlineKeyboardButton("🥇 1ኛ ሽልማት", callback_data="set_prize_1")],
        [InlineKeyboardButton("🥈 2ኛ ሽልማት", callback_data="set_prize_2")],
        [InlineKeyboardButton("🥉 3ኛ ሽልማት", callback_data="set_prize_3")],
        [InlineKeyboardButton("◀️ ተመለስ", callback_data="admin_panel")],
    ]
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_tickets_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["admin_action"] = "set_tickets"
    await query.edit_message_text(
        "🔢 *አዲስ የቁጥሮች ብዛት ፃፍ (10-1000):*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ሰርዝ", callback_data="admin_settings")
        ]])
    )

async def set_price_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["admin_action"] = "set_price"
    await query.edit_message_text(
        "💰 *አዲስ ዋጋ ፃፍ (ብር):*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ሰርዝ", callback_data="admin_settings")
        ]])
    )

async def set_prize_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prize_num = query.data.split("_")[-1]
    ctx.user_data["admin_action"] = f"set_prize_{prize_num}"
    await query.edit_message_text(
        f"🏆 *{prize_num}ኛ ሽልማት ፃፍ:*\nምሳሌ: 50,000 ብር ወይም Toyota Corolla",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ሰርዝ", callback_data="admin_settings")
        ]])
    )

async def handle_admin_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()

    # ── Name collection ──
    if ctx.user_data.get("waiting_name"):
        ctx.user_data["full_name"] = text_input
        ctx.user_data["waiting_name"] = False
        ctx.user_data["waiting_phone"] = True
        await update.message.reply_text(
            "📞 *ስልክ ቁጥርዎን ይፃፉ:*\nምሳሌ: 0912345678",
            parse_mode="Markdown"
        )
        return

    # ── Phone collection ──
    if ctx.user_data.get("waiting_phone"):
        phone = text_input
        if not phone.isdigit() or len(phone) < 9:
            await update.message.reply_text(
                "⚠️ ትክክለኛ ስልክ ቁጥር ይፃፉ። ምሳሌ: 0912345678"
            )
            return
        ctx.user_data["user_phone"] = phone
        ctx.user_data["waiting_phone"] = False

        # Show payment info now
        method = ctx.user_data.get("payment_method", "CBE")
        selected = ctx.user_data.get("selected", [])
        price = await db.get_setting("ticket_price")
        total_price = len(selected) * int(price)

        if method == "CBE":
            account_text = (
                f"🏦 *CBE ባንክ*\n"
                f"{'─'*25}\n"
                f"📋 አካውንት ቁጥር:\n"
                f"`{CBE_ACCOUNT}`\n"
                f"👤 ስም: {CBE_NAME}\n"
            )
        else:
            account_text = (
                f"📱 *Telebirr*\n"
                f"{'─'*25}\n"
                f"📋 ቁጥር:\n"
                f"`{TELEBIRR_ACCOUNT}`\n"
                f"👤 ስም: {TELEBIRR_NAME}\n"
            )

        await update.message.reply_text(
            f"{account_text}"
            f"{'─'*25}\n"
            f"💰 የሚከፍሉት: *{total_price} ብር*\n"
            f"{'─'*25}\n"
            f"✅ ክፍያ ከፈፀሙ በኋላ *ደረሰኝ (screenshot)* ይላኩ።",
            parse_mode="Markdown"
        )
        ctx.user_data["waiting_receipt"] = True
        return

    # ── Admin settings text ──
    action = ctx.user_data.get("admin_action")
    if not action or not is_admin(update.effective_user.id):
        return

    ctx.user_data["admin_action"] = None

    if action == "set_tickets":
        try:
            val = int(text_input)
            if 10 <= val <= 1000:
                await db.set_setting("total_tickets", val)
                await update.message.reply_text(f"✅ ቁጥሮች ወደ {val} ተቀይሯል!")
            else:
                await update.message.reply_text("⚠️ 10-1000 መካከል ፃፍ።")
        except:
            await update.message.reply_text("⚠️ ቁጥር ብቻ ፃፍ።")

    elif action == "set_price":
        try:
            val = int(text_input)
            await db.set_setting("ticket_price", val)
            await update.message.reply_text(f"✅ ዋጋ ወደ {val} ብር ተቀይሯል!")
        except:
            await update.message.reply_text("⚠️ ቁጥር ብቻ ፃፍ።")

    elif action == "set_prize_1":
        await db.set_setting("prize_1", text_input)
        await update.message.reply_text(f"✅ 1ኛ ሽልማት: {text_input}")

    elif action == "set_prize_2":
        await db.set_setting("prize_2", text_input)
        await update.message.reply_text(f"✅ 2ኛ ሽልማት: {text_input}")

    elif action == "set_prize_3":
        await db.set_setting("prize_3", text_input)
        await update.message.reply_text(f"✅ 3ኛ ሽልማት: {text_input}")

    elif action == "broadcast":
        users = await db.get_all_users()
        sent = 0
        for (uid,) in users:
            try:
                await ctx.bot.send_message(chat_id=uid, text=f"📢 {text_input}")
                sent += 1
            except:
                pass
        await update.message.reply_text(f"✅ ለ {sent} ሰዎች ተልኳል!")

# ─────────────────────────────────────────
# BROADCAST
# ─────────────────────────────────────────
async def admin_broadcast_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "broadcast"
    await query.edit_message_text(
        "📢 *መልዕክቱን ፃፍ (ለሁሉም ተጠቃሚዎች ይላካል):*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ ሰርዝ", callback_data="admin_panel")
        ]])
    )

# ─────────────────────────────────────────
# DRAW
# ─────────────────────────────────────────
async def admin_draw_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    import random
    taken = await db.count_taken_tickets()
    if taken == 0:
        await query.edit_message_text("⚠️ ምንም ቁጥር አልተሸጠም!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️", callback_data="admin_panel")]]))
        return

    total = int(await db.get_setting("total_tickets"))
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")
    title = await db.get_setting("lottery_title")

    async with __import__('aiosqlite').connect("data/equb.db") as dbc:
        async with dbc.execute("SELECT number, user_id, username FROM tickets WHERE status='taken'") as cur:
            all_tickets = await cur.fetchall()

    winners = random.sample(all_tickets, min(3, len(all_tickets)))

    result = f"🎊 *{title} - እጣ ውጤት!*\n{'─'*25}\n"
    prizes = [prize1, prize2, prize3]
    medals = ["🥇", "🥈", "🥉"]

    for i, (num, uid, uname) in enumerate(winners):
        result += f"{medals[i]} *{prizes[i]}*\n"
        result += f"   🎟 ቁጥር: {num} | 👤 {uname}\n\n"

    result += f"{'─'*25}\n축하합니다! / እንኳን ደስ አለዎት!"

    # Send to group and all users
    try:
        await ctx.bot.send_message(chat_id=GROUP_ID, text=result, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Group draw send error: {e}")

    users = await db.get_all_users()
    for (uid,) in users:
        try:
            await ctx.bot.send_message(chat_id=uid, text=result, parse_mode="Markdown")
        except:
            pass

    await query.edit_message_text(result, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️", callback_data="admin_panel")]]))

# ─────────────────────────────────────────
# SEND LIST TO GROUP
# ─────────────────────────────────────────
async def admin_send_list_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    total = int(await db.get_setting("total_tickets"))
    title = await db.get_setting("lottery_title")

    # Clear old group messages tracking
    async with __import__('aiosqlite').connect("data/equb.db") as dbc:
        await dbc.execute("DELETE FROM group_messages")
        await dbc.commit()

    # Send header
    header = f"🎟 *{title}*\n{'─'*30}"
    try:
        await ctx.bot.send_message(chat_id=GROUP_ID, text=header, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Header send error: {e}")

    # Send in chunks of 50
    for start in range(1, total + 1, PAGE_SIZE):
        end = min(start + PAGE_SIZE - 1, total)
        tickets = await db.get_tickets_range(start, end)
        ticket_map = {t[0]: (t[1], t[4]) for t in tickets}

        lines = []
        for n in range(start, end + 1):
            info = ticket_map.get(n)
            if info and info[1] == "taken":
                lines.append(f"{n} 👉 {mask_phone(str(info[0]))} ✅")
            else:
                lines.append(f"{n} 👉")

        text = "\n".join(lines)
        try:
            msg = await ctx.bot.send_message(chat_id=GROUP_ID, text=text)
            await db.save_group_message(msg.message_id, start, end)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Send list error: {e}")

    await query.edit_message_text(
        f"✅ ዝርዝር ወደ ግሩፕ ተልኳል! ({total} ቁጥሮች)",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️", callback_data="admin_panel")]])
    )

# ─────────────────────────────────────────
# RESET
# ─────────────────────────────────────────
async def admin_reset_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await query.edit_message_text(
        "⚠️ *እርግጠኛ ነህ?*\nሁሉም ቁጥሮች እና ክፍያዎች ይጠፋሉ!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ አዎ፣ Reset አድርግ", callback_data="admin_reset_yes")],
            [InlineKeyboardButton("❌ አይ", callback_data="admin_panel")]
        ])
    )

async def admin_reset_yes_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await db.reset_lottery()
    await query.edit_message_text(
        "✅ *አዲስ እጣ ተጀምሯል!*\nሁሉም ቁጥሮች ተሰርዘዋል።",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ወደ ፓነል", callback_data="admin_panel")]])
    )

# ─────────────────────────────────────────
# MY TICKETS
# ─────────────────────────────────────────
async def my_tickets_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    tickets = await db.get_user_tickets(user.id)

    if not tickets:
        text = "🎟 *የእርስዎ ትኬቶች*\n\nምንም ትኬት የለዎትም።"
    else:
        nums = sorted([t[0] for t in tickets])
        price = await db.get_setting("ticket_price")
        total = len(nums) * int(price)
        text = (
            f"🎟 *የእርስዎ ትኬቶች*\n"
            f"{'─'*25}\n"
            f"ቁጥሮች: {', '.join(map(str, nums))}\n"
            f"ድምር ዋጋ: {total} ብር"
        )

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ ዋና ምናሌ", callback_data="main_menu")]])
    )

# ─────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────
async def main_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    title = await db.get_setting("lottery_title")
    price = await db.get_setting("ticket_price")
    total = await db.get_setting("total_tickets")
    taken = await db.count_taken_tickets()
    remaining = int(total) - taken
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")

    text = (
        f"🎉 *{title}*\n"
        f"{'─'*30}\n"
        f"🎟 የ1 ትኬት ዋጋ: *{price} ብር*\n"
        f"🔢 ጠቅላላ ቁጥሮች: *{total}*\n"
        f"✅ የቀሩ ቁጥሮች: *{remaining}*\n"
        f"{'─'*30}\n"
        f"🥇 1ኛ: {prize1}\n"
        f"🥈 2ኛ: {prize2}\n"
        f"🥉 3ኛ: {prize3}\n"
        f"{'─'*30}\n"
        f"እስከ *5 ቁጥሮች* ድረስ መምረጥ ይችላሉ።"
    )
    keyboard = [
        [InlineKeyboardButton("🎟 ቁጥር ምረጥ", callback_data="pick_numbers")],
        [InlineKeyboardButton("📋 የእኔ ትኬቶች", callback_data="my_tickets")],
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("👨‍💼 አድሚን ፓነል", callback_data="admin_panel")])

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    asyncio.run(db.init_db())

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u, c: admin_panel_cb(u, c) if is_admin(u.effective_user.id) else None))

    app.add_handler(CallbackQueryHandler(pick_numbers_cb, pattern="^pick_numbers$"))
    app.add_handler(CallbackQueryHandler(number_cb, pattern="^(select|deselect|taken|page|noop)_"))
    app.add_handler(CallbackQueryHandler(proceed_payment_cb, pattern="^proceed_payment$"))
    app.add_handler(CallbackQueryHandler(payment_method_cb, pattern="^pay_(cbe|telebirr)$"))
    app.add_handler(CallbackQueryHandler(my_tickets_cb, pattern="^my_tickets$"))
    app.add_handler(CallbackQueryHandler(main_menu_cb, pattern="^main_menu$"))

    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin_panel_cb, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_pending_cb, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_settings_cb, pattern="^admin_settings$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_cb, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_draw_cb, pattern="^admin_draw$"))
    app.add_handler(CallbackQueryHandler(admin_send_list_cb, pattern="^admin_send_list$"))
    app.add_handler(CallbackQueryHandler(admin_reset_confirm_cb, pattern="^admin_reset_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_reset_yes_cb, pattern="^admin_reset_yes$"))
    app.add_handler(CallbackQueryHandler(set_tickets_cb, pattern="^set_tickets$"))
    app.add_handler(CallbackQueryHandler(set_price_cb, pattern="^set_price$"))
    app.add_handler(CallbackQueryHandler(set_prize_cb, pattern="^set_prize_"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb, pattern="^(approve|reject)_"))

    # Text handlers
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
