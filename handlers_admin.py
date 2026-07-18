# ══════════════════════════════════════════
# handlers_admin.py
# ሁሉም አድሚን-ብቻ handlers፦ admin panel, statistics, pending, search,
# settings, broadcast, reset, approve/reject, text/photo input።
# ══════════════════════════════════════════
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ContextTypes

import database as db
from config import ADMIN_IDS
from config_extra import RENDER_PUBLIC_URL, BRAND_SIGNATURE

from translations import T
from helpers import is_admin
from group_list import send_full_list_to_group, schedule_group_list_update, announce_sold_numbers

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════
async def show_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    total         = int(await db.get_setting("total_tickets"))
    taken         = await db.count_taken_tickets()
    pending_list  = await db.get_pending_payments()
    pending_count = len(pending_list)
    price         = int(await db.get_setting("ticket_price"))
    total_revenue = taken * price

    text = (
        f"🔰 *ADMIN PANEL* 🔰\n"
        f"━━━━━━━━━━━━━━━\n"
        f"የትኬት ብዛት = {total}\n"
        f"የተሸጠ = {taken}\n"
        f"ቀሪ = {total - taken}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"ገቢ = {total_revenue:,} ብር\n"
        f"በሂደት ላይ ያለ = {pending_count}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"for admin only!"
    )

    inline_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"⏳ Pending ({pending_count})", callback_data="admin_pending"),
            InlineKeyboardButton("📊 STATISTICS",                 callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("🔍 SEARCH",  callback_data="admin_find"),
            InlineKeyboardButton("📋 CARDS",   web_app=WebAppInfo(url=f"{RENDER_PUBLIC_URL}/admin.html"))
        ],
    ])

    menu_kb = ReplyKeyboardMarkup([
        [KeyboardButton("📤 SEND TO GROUP 📤")],
        [KeyboardButton("📢 BROADCAST 📢"), KeyboardButton("⚙️ SETTING ⚙️")],
        [KeyboardButton("🏠 Main Menu")],
    ], resize_keyboard=True)

    ctx.user_data["admin_menu"] = True

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=inline_kb)
        except Exception:
            await update.effective_message.reply_text(
                text, parse_mode="Markdown", reply_markup=inline_kb)
        await update.effective_message.reply_text(
            "━━━━━━━━━━━",
            reply_markup=menu_kb
        )
    else:
        await update.effective_message.reply_text(
            text, parse_mode="Markdown", reply_markup=inline_kb)
        await update.effective_message.reply_text(
            "━━━━━━━━━━━",
            reply_markup=menu_kb
        )


async def admin_panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await show_admin_panel(update, ctx)


# ── Settings menu ──
async def show_settings_menu(update, ctx):
    price  = await db.get_setting("ticket_price")
    total  = await db.get_setting("total_tickets")
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")
    home_image = await db.get_setting("home_image")
    image_status = "✅ ተቀናብሯል" if home_image else "❌ የለም"

    text = (
        f"⚙️ *SETTING* ⚙️\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔢 ቁጥሮች: {total}\n"
        f"💰 ዋጋ: {price} ETB\n"
        f"🥇 {prize1}\n🥈 {prize2}\n🥉 {prize3}\n"
        f"🖼 Home ምስል: {image_status}"
    )
    # ◀️ ተመለስ / 🏠 Main Menu ከስር ተቀምጠዋል (አድሚን ከዚህ ስክሪን ለመውጣት /start መተየብ እንዳይኖርበት)
    settings_kb = ReplyKeyboardMarkup([
        [KeyboardButton("CHANGE NUMBER 🔢"), KeyboardButton("CHANGE PRICE 💰")],
        [KeyboardButton("PRIZE 1️⃣"), KeyboardButton("PRIZE 2️⃣"), KeyboardButton("PRIZE 3️⃣")],
        [KeyboardButton("CHANGE IMAGE 🖼"), KeyboardButton("REMOVE IMAGE 🗑")],
        [KeyboardButton("⚠️ RESET ⚠️")],
        [KeyboardButton("◀️ ተመለስ"), KeyboardButton("🏠 Main Menu")],
    ], resize_keyboard=True)

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=settings_kb)


# ── Admin panel inline callbacks ──
async def admin_pending_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    pending = await db.get_pending_payments()
    if not pending:
        await query.edit_message_text(
            "✅ No pending payments.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back", callback_data="admin_panel")
            ]])
        )
        return
    price = int(await db.get_setting("ticket_price"))
    await query.edit_message_text(
        f"⏳ Sending *{len(pending)}* pending payments to DM...",
        parse_mode="Markdown"
    )
    for p in pending:
        p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status = p[:8]
        numbers     = list(map(int, p_numbers.split(",")))
        total_price = len(numbers) * price
        caption = (
            f"💳 <b>#{p_id}</b>\n{'─'*20}\n"
            f"👤 {p_username}\n📞 {p_phone}\n"
            f"🎫 {p_numbers}\n"
            f"💰 {total_price} ETB | {p_method}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{p_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{p_id}")
        ]])
        try:
            await ctx.bot.send_photo(chat_id=update.effective_user.id,
                                     photo=p_receipt, caption=caption,
                                     parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Pending send error: {e}")
        await asyncio.sleep(0.3)


async def admin_stats_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total         = int(await db.get_setting("total_tickets"))
    taken         = await db.count_taken_tickets()
    price         = int(await db.get_setting("ticket_price"))
    today_count   = await db.count_tickets_today()
    pending_count = len(await db.get_pending_payments())
    reserved      = await db.count_pending_tickets()
    percent       = round((taken / total) * 100, 1) if total > 0 else 0
    filled        = int(percent / 10)
    bar           = "█" * filled + "░" * (10 - filled)

    text = (
        f"📊 *STATISTICS*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎟 Total Tickets: *{total}*\n"
        f"✅ Approved (Sold): *{taken}*\n"
        f"⏳ Reserved (Pending): *{reserved}*\n"
        f"🆓 Free: *{total - taken - reserved}*\n"
        f"⌛ Pending Payments: *{pending_count}*\n"
        f"📅 Today Approved: *{today_count}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 Sales Progress:\n"
        f"[{bar}] {percent}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Approved Revenue: *{taken * price:,} ETB*\n"
        f"⏳ Pending Revenue: *{pending_count * price:,} ETB*\n"
        f"💎 Total Possible: *{total * price:,} ETB*"
    )
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back", callback_data="admin_panel")
        ]])
    )


async def admin_find_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["admin_action"] = "find_ticket"
    await query.edit_message_text(
        "🔍 *SEARCH*\n━━━━━━━━━━━━━━━\nየቲኬት ቁጥር ፃፍ:\nምሳሌ: 5",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Cancel", callback_data="admin_panel")
        ]])
    )


async def watch_pending_payments(bot, interval_seconds=30, max_age_seconds=300):
    """በየ30 ሰከንድ ይፈትሻል፣ 5 ደቂቃ ካለፈ ቁጥሩን free ያደርጋል + ለተጠቃሚው ያሳውቃል"""
    while True:
        try:
            released = await db.release_expired_pending(max_age_seconds)
            for num, user_id in released:
                if not user_id:
                    continue
                try:
                    await bot.send_message(
                        chat_id=int(user_id),
                        text=(
                            f"⏳ የቁጥር {num} ማስያዣ ጊዜ አልቋል።\n"
                            f"ደረሰኝ ስላልደረሰን ቁጥሩ ነፃ ወጥቷል። እንደገና ይምረጡ።"
                        )
                    )
                except Exception as e:
                    logger.warning(f"Notify release failed for {user_id}: {e}")
        except Exception as e:
            logger.error(f"watch_pending_payments error: {e}")
        await asyncio.sleep(interval_seconds)


# ── Send to Group ──
async def admin_send_list_msg(update, ctx):
    if not is_admin(update.effective_user.id):
        return
    total = int(await db.get_setting("total_tickets"))
    await update.message.reply_text("⏳ Sending to group...")

    async def _runner():
        try:
            count = await send_full_list_to_group(ctx.bot, total)
            await ctx.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ {count} messages updated in group!"
            )
        except Exception as e:
            logger.error(f"admin_send_list_msg error: {e}")
            await ctx.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Group update failed."
            )

    asyncio.create_task(_runner())


# ── Broadcast ──
async def admin_broadcast_msg(update, ctx):
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "broadcast"
    await update.message.reply_text(
        "📢 *BROADCAST*\n━━━━━━━━━━━━━━━\nWrite the message to send to all users + group:",
        parse_mode="Markdown"
    )


async def admin_broadcast_edit_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = "broadcast"
    await query.edit_message_text(
        "📢 *BROADCAST*\n━━━━━━━━━━━━━━━\nWrite the message to send to all users + group:",
        parse_mode="Markdown"
    )


async def broadcast_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    msg   = ctx.user_data.get("broadcast_msg", "")
    users = await db.get_all_users()
    sent, failed = 0, 0
    for (uid,) in users:
        try:
            await ctx.bot.send_message(chat_id=uid, text=f"📢 {msg}")
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast failed for user {uid}: {e}")
        await asyncio.sleep(0.05)

    try:
        from config import GROUP_ID
        await ctx.bot.send_message(chat_id=GROUP_ID, text=f"📢 {msg}")
    except Exception as e:
        logger.error(f"Group broadcast: {e}")

    await query.edit_message_text(
        f"✅ Sent to {sent} users + group!\n⚠️ Failed: {failed}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="admin_panel")
        ]])
    )


# ── Reset ──
async def admin_reset_yes_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    await db.reset_lottery()
    await query.edit_message_text(
        "✅ *New lottery started!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")
        ]])
    )


# ══════════════════════════════════════════
# APPROVE / REJECT
# ══════════════════════════════════════════
async def approve_reject_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return

    action, payment_id = query.data.split("_", 1)
    payment_id = int(payment_id)
    payment    = await db.get_payment(payment_id)
    if not payment:
        return

    p_id      = payment[0]
    p_user_id = payment[1]
    p_username= payment[2]
    p_phone   = payment[3]
    p_numbers = payment[4]
    p_receipt = payment[5]
    p_method  = payment[6]
    p_status  = payment[7]
    full_name = payment[8] if payment[8] else p_username

    if p_status != "pending":
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.answer("Already reviewed!", show_alert=True)
        return

    numbers     = list(map(int, p_numbers.split(",")))
    price       = int(await db.get_setting("ticket_price"))
    total_price = len(numbers) * price
    total       = int(await db.get_setting("total_tickets"))
    user_lang   = "am"

    if action == "approve":
        await db.update_payment_status(payment_id, "approved", update.effective_user.id)
        await db.confirm_tickets(numbers, p_user_id, p_username, p_phone)

        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=T[user_lang]["approved"].format(
                    nums=", ".join(map(str, sorted(numbers))),
                    total=total_price,
                    brand=BRAND_SIGNATURE,
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User approved notify: {e}")

        try:
            await query.edit_message_caption(
                caption=(f"✅ <b>Approved</b>\n"
                         f"👤 {full_name}\n"
                         f"🔗 {p_username}\n📞 {p_phone}\n"
                         f"🎟 {p_numbers}\n💰 {total_price} ETB"),
                parse_mode="HTML", reply_markup=None
            )
        except Exception as e:
            logger.error(f"Edit caption: {e}")

        try:
            asyncio.create_task(schedule_group_list_update(ctx.bot, total))
        except Exception as e:
            logger.error(f"Group update schedule error: {e}")

        try:
            asyncio.create_task(announce_sold_numbers(ctx.bot, numbers))
        except Exception as e:
            logger.error(f"Sold announce schedule error: {e}")

        taken = await db.count_taken_tickets()
        if taken >= total:
            for admin_id in ADMIN_IDS:
                try:
                    await ctx.bot.send_message(
                        chat_id=admin_id,
                        text=f"🎊 *All tickets sold!* {taken}/{total}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
    else:
        await db.update_payment_status(payment_id, "rejected", update.effective_user.id)
        await db.free_tickets(numbers)

        try:
            await ctx.bot.send_message(
                chat_id=p_user_id,
                text=T[user_lang]["rejected"].format(
                    nums=", ".join(map(str, sorted(numbers)))
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"User rejected notify: {e}")

        try:
            await query.edit_message_caption(
                caption=(f"❌ <b>Rejected</b>\n"
                         f"👤 {full_name}\n"
                         f"🔗 {p_username}\n📞 {p_phone}\n🎟 {p_numbers}"),
                parse_mode="HTML", reply_markup=None
            )
        except Exception as e:
            logger.error(f"Edit caption: {e}")


# ══════════════════════════════════════════
# TEXT INPUT HANDLER (admin actions only — payment info is
# collected entirely inside payment.html, not via chat text)
# ══════════════════════════════════════════
async def handle_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()

    action = ctx.user_data.get("admin_action")
    if not action or not is_admin(update.effective_user.id):
        return
    ctx.user_data["admin_action"] = None

    if action == "find_ticket":
        try:
            num = int(text_input)
        except Exception:
            await update.message.reply_text("⚠️ ቁጥር ብቻ ፃፍ።")
            return
        payment = await db.find_payment_by_number(num)
        if not payment:
            await update.message.reply_text(f"❌ ቁጥር {num} ምንም መረጃ የለም።")
            return

        p_id, p_user_id, p_username, p_phone, p_numbers, p_receipt, p_method, p_status, p_reviewed_at = payment
        full_payment = await db.get_payment(p_id)
        full_name    = full_payment[8] if full_payment and full_payment[8] else p_username

        price_val    = int(await db.get_setting("ticket_price"))
        nums_list    = list(map(int, p_numbers.split(",")))
        total_price  = len(nums_list) * price_val
        status_label = {
            "pending":  "⏳ Pending",
            "approved": "✅ Approved",
            "rejected": "❌ Rejected"
        }.get(p_status, p_status)

        caption = (
            f"🔍 <b>Ticket {num} Search</b>\n"
            f"{'─'*20}\n"
            f"💳 Payment #{p_id}\n"
            f"👤 <b>{full_name}</b>\n"
            f"🔗 {p_username}\n"
            f"📞 {p_phone}\n"
            f"🎟 {p_numbers}\n"
            f"💰 {total_price} ETB | {p_method}\n"
            f"📊 {status_label}"
        )
        kb = []
        if p_status == "pending":
            kb.append([
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{p_id}"),
                InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{p_id}")
            ])
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        try:
            await ctx.bot.send_photo(chat_id=update.effective_user.id,
                                     photo=p_receipt, caption=caption,
                                     parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            await update.message.reply_text(caption, parse_mode="HTML",
                                            reply_markup=InlineKeyboardMarkup(kb))
        return

    if action == "set_tickets":
        try:
            val = int(text_input)
            if 10 <= val <= 2000:
                await db.set_setting("total_tickets", val)
                await update.message.reply_text(f"✅ Tickets → {val}")
            else:
                await update.message.reply_text("⚠️ 10-2000 ፃፍ።")
        except Exception:
            await update.message.reply_text("⚠️ ቁጥር ብቻ።")

    elif action == "set_price":
        try:
            val = int(text_input)
            await db.set_setting("ticket_price", val)
            await update.message.reply_text(f"✅ Price → {val} ETB")
        except Exception:
            await update.message.reply_text("⚠️ ቁጥር ብቻ።")

    elif action in ["set_prize_1", "set_prize_2", "set_prize_3"]:
        key = action.replace("set_", "")
        await db.set_setting(key, text_input)
        await update.message.reply_text(f"✅ {text_input}")

    elif action == "broadcast":
        ctx.user_data["broadcast_msg"] = text_input
        await update.message.reply_text(
            f"📋 *Preview:*\n━━━━━━━━━━━━━━━\n📢 {text_input}\n━━━━━━━━━━━━━━━\nSend to all + group?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes, Send", callback_data="broadcast_confirm")],
                [InlineKeyboardButton("✏️ Edit",      callback_data="admin_broadcast")],
                [InlineKeyboardButton("✖️ Cancel",    callback_data="admin_panel")]
            ])
        )


# ══════════════════════════════════════════
# ADMIN PHOTO HANDLER (home banner image upload)
# ══════════════════════════════════════════
async def admin_photo_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    if ctx.user_data.get("admin_action") != "set_home_image":
        return
    photo = update.message.photo[-1]
    await db.set_setting("home_image", photo.file_id)
    ctx.user_data["admin_action"] = None
    await update.message.reply_text("✅ Home ምስል ተቀናብሯል!")
