# ══════════════════════════════════════════
# handlers_user.py
# ተጠቃሚ-ተኮር handlers፦ /start, ቋንቋ, home, my-tickets, support,
# ክፍያ ወደ payment.html handoff, referral።
# ══════════════════════════════════════════
import json
import logging
from urllib.parse import quote

from telegram import (
    Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import ContextTypes

import database as db
from config import ADMIN_IDS
from config_extra import INDEX_APP_URL, PAYMENT_APP_URL

from translations import T
from helpers import t, is_admin, remove_menu
from button_matchers import (
    home_words, cancel_words, tickets_words, admin_words, info_words,
    pick_words, back_words, support_words, feedback_words, skip_words,
)
from membership import is_fully_joined, send_join_prompt, proceed_after_membership

logger = logging.getLogger(__name__)

PAYMENT_CONTINUE_TEXT = {
    "am": "💳 ክፍያ ቀጥል",
    "en": "💳 Continue to Payment",
    "or": "💳 Kaffaltiitti Itti Fufi",
}


# ══════════════════════════════════════════
# START / LANGUAGE
# ══════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args

    if args and args[0].startswith("receipt_"):
        if is_admin(user.id):
            try:
                payment_id = int(args[0].replace("receipt_", ""))
                payment = await db.get_payment(payment_id)
                if payment:
                    p_id       = payment[0]
                    p_user_id  = payment[1]
                    p_username = payment[2]
                    p_phone    = payment[3]
                    p_numbers  = payment[4]
                    p_receipt  = payment[5]
                    p_method   = payment[6]
                    p_status   = payment[7]
                    full_name  = payment[8] if payment[8] else p_username

                    price_val   = int(await db.get_setting("ticket_price"))
                    nums_list   = list(map(int, p_numbers.split(",")))
                    total_price = len(nums_list) * price_val
                    status_label = {
                        "pending":  "⏳ Pending",
                        "approved": "✅ Approved",
                        "rejected": "❌ Rejected"
                    }.get(p_status, p_status)

                    caption = (
                        f"🧾 <b>Receipt — Payment #{p_id}</b>\n"
                        f"{'─'*20}\n"
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
                    await ctx.bot.send_photo(
                        chat_id=user.id,
                        photo=p_receipt,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(kb) if kb else None
                    )
                else:
                    await update.message.reply_text("⚠️ Payment not found.")
            except Exception as e:
                logger.error(f"Receipt deep link error: {e}")
                await update.message.reply_text("⚠️ ደረሰኝ ማምጣት አልተቻለም።")
        return

    if args and args[0].startswith("ref_"):
        referrer_id = args[0].replace("ref_", "")
        if referrer_id != str(user.id):
            await db.add_referral(referrer_id, str(user.id))

    if not ctx.user_data.get("lang"):
        keyboard = [
            [InlineKeyboardButton("🇪🇹 አማርኛ",      callback_data="lang_am")],
            [InlineKeyboardButton("🇬🇧 English",      callback_data="lang_en")],
            [InlineKeyboardButton("🇪🇹 Afaan Oromoo", callback_data="lang_or")],
        ]
        await update.message.reply_text(
            "🌐 ቋንቋ ይምረጡ / Choose Language / Afaan filachuu:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if not is_admin(user.id):
        if not await is_fully_joined(ctx.bot, user.id):
            await send_join_prompt(update, ctx)
            return

    await proceed_after_membership(update, ctx)


async def language_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇪🇹 አማርኛ",      callback_data="lang_am")],
        [InlineKeyboardButton("🇬🇧 English",      callback_data="lang_en")],
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

    user = update.effective_user
    if not is_admin(user.id):
        if not await is_fully_joined(ctx.bot, user.id):
            await send_join_prompt(update, ctx)
            return

    await proceed_after_membership(update, ctx)


# ══════════════════════════════════════════
# CHECK MEMBERSHIP CALLBACK
# ══════════════════════════════════════════
async def check_membership_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user  = update.effective_user

    if await is_fully_joined(ctx.bot, user.id):
        await query.answer()
        try:
            await query.delete_message()
        except Exception:
            pass
        await proceed_after_membership(update, ctx)
    else:
        lang = ctx.user_data.get("lang", "am")
        await query.answer(T[lang]["not_joined"], show_alert=True)


# ══════════════════════════════════════════
# HOME
# ══════════════════════════════════════════
async def show_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    title  = await db.get_setting("lottery_title")
    price  = await db.get_setting("ticket_price")
    total  = await db.get_setting("total_tickets")
    prize1 = await db.get_setting("prize_1")
    prize2 = await db.get_setting("prize_2")
    prize3 = await db.get_setting("prize_3")

    text = t(ctx, "home_text", title=title, total=total, price=price,
             prize1=prize1, prize2=prize2, prize3=prize3)

    lang    = ctx.user_data.get("lang", "am")
    lang_url = f"{INDEX_APP_URL}?lang={lang}"
    rows = [
        [KeyboardButton(t(ctx, "pick_btn"), web_app=WebAppInfo(url=lang_url))],
        [KeyboardButton(t(ctx, "my_tickets_btn"))],
        [KeyboardButton(t(ctx, "info_btn")), KeyboardButton(t(ctx, "support_btn"))],
    ]
    if is_admin(user.id):
        rows.append([KeyboardButton(t(ctx, "admin_btn"))])
    reply_markup = ReplyKeyboardMarkup(rows, resize_keyboard=True)

    if update.callback_query:
        try:
            await update.callback_query.delete_message()
        except Exception:
            pass

    home_image = await db.get_setting("home_image")
    if home_image:
        try:
            await update.effective_message.reply_photo(
                photo=home_image, caption=text, parse_mode="Markdown", reply_markup=reply_markup
            )
            return
        except Exception as e:
            logger.warning(f"Home image send failed, falling back to text: {e}")

    await update.effective_message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def home_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["admin_action"] = None
    ctx.user_data["admin_menu"]   = False
    await show_home(update, ctx)


# ══════════════════════════════════════════
# SUPPORT
# ══════════════════════════════════════════
async def show_support_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from config import SUPPORT_CONTACT_USERNAME
    lang = ctx.user_data.get("lang", "am")
    text = T[lang]["support_menu_text"]
    if SUPPORT_CONTACT_USERNAME:
        text += f"\n\n📞 {T[lang]['support_contact_btn']}: @{SUPPORT_CONTACT_USERNAME.lstrip('@')}"
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton(T[lang]["feedback_btn"])],
            [KeyboardButton(T[lang]["back_home_btn"]), KeyboardButton(T[lang]["mainmenu_btn"])],
        ],
        resize_keyboard=True
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def handle_feedback_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = ctx.user_data.get("lang", "am")
    text = update.message.text.strip()
    ctx.user_data["awaiting_feedback"] = False

    uname = f"@{user.username}" if user.username else (user.full_name or "—")
    fb_caption = (
        f"💬 <b>Feedback</b>\n"
        f"{'─'*20}\n"
        f"👤 {uname}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"{'─'*20}\n"
        f"{text}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(chat_id=admin_id, text=fb_caption, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Feedback forward error: {e}")

    await update.message.reply_text(T[lang]["feedback_sent"])


# ══════════════════════════════════════════
# MESSAGE ROUTER
# ══════════════════════════════════════════
async def any_message_home(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # admin-only text/action routing lives in handlers_admin.py;
    # imported lazily to avoid a circular import.
    from handlers_admin import (
        show_admin_panel, admin_send_list_msg, admin_broadcast_msg,
        show_settings_menu, handle_text_input,
    )

    text = update.message.text or ""
    user = update.effective_user

    # ተጠቃሚ አስተያየት (feedback) እየፃፈ ከሆነ ወደ አድሚን ብቻ ላክ
    if ctx.user_data.get("awaiting_feedback"):
        await handle_feedback_text(update, ctx)
        return

    if any(w in text for w in skip_words):
        ctx.user_data["_profile_checked"] = True
        await show_home(update, ctx)
        return

    # ኮንታክት ገና ካላጋሩ (እና አድሚን ካልሆኑ) ማንኛውንም ግብዓት ወደ contact prompt መልስ
    if ctx.user_data.get("lang") and not is_admin(user.id) and not ctx.user_data.get("_profile_checked"):
        profile = await db.get_profile(user.id)
        if not profile:
            from membership import send_contact_prompt
            await send_contact_prompt(update, ctx)
            return
        ctx.user_data["_profile_checked"] = True

    if any(w in text for w in home_words):
        ctx.user_data["admin_action"] = None
        ctx.user_data["admin_menu"]   = False
        await show_home(update, ctx)
        return

    if any(w in text for w in cancel_words):
        selected = ctx.user_data.get("selected", [])
        if selected:
            await db.free_tickets(selected)
        ctx.user_data["admin_action"] = None
        ctx.user_data["admin_menu"]   = False
        ctx.user_data["selected"]     = []
        await update.message.reply_text("❌", reply_markup=remove_menu())
        await show_home(update, ctx)
        return

    if any(w in text for w in tickets_words):
        await show_my_tickets(update, ctx)
        return

    if any(w in text for w in feedback_words):
        lang = ctx.user_data.get("lang", "am")
        ctx.user_data["awaiting_feedback"] = True
        await update.message.reply_text(T[lang]["feedback_prompt"], parse_mode="Markdown")
        return

    if any(w in text for w in support_words):
        await show_support_menu(update, ctx)
        return

    if any(w in text for w in info_words):
        lang = ctx.user_data.get("lang", "am")
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(T[lang]["back_home_btn"]), KeyboardButton(T[lang]["mainmenu_btn"])]],
            resize_keyboard=True
        )
        await update.message.reply_text(
            T[lang]["info_text"], parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    if any(w in text for w in admin_words):
        if is_admin(update.effective_user.id):
            await show_admin_panel(update, ctx)
        return

    if any(w in text for w in pick_words):
        return

    # ── አድሚን ◀️ ተመለስ (ወደ admin panel፣ Home አይደለም) ──
    if any(w in text for w in back_words) and is_admin(update.effective_user.id):
        await show_admin_panel(update, ctx)
        return

    if is_admin(update.effective_user.id):
        if "📤 SEND TO GROUP 📤" in text:
            await admin_send_list_msg(update, ctx)
            return
        if "📢 BROADCAST 📢" in text:
            await admin_broadcast_msg(update, ctx)
            return
        if "⚙️ SETTING ⚙️" in text:
            await show_settings_menu(update, ctx)
            return
        if "CHANGE NUMBER 🔢" in text:
            ctx.user_data["admin_action"] = "set_tickets"
            await update.message.reply_text("🔢 አዲስ የቁጥሮች ብዛት ፃፍ (10-2000):")
            return
        if "CHANGE PRICE 💰" in text:
            ctx.user_data["admin_action"] = "set_price"
            await update.message.reply_text("💰 አዲስ ዋጋ ፃፍ (ETB):")
            return
        if "PRIZE 1️⃣" in text:
            ctx.user_data["admin_action"] = "set_prize_1"
            await update.message.reply_text("🥇 1ኛ ሽልማት ፃፍ:")
            return
        if "PRIZE 2️⃣" in text:
            ctx.user_data["admin_action"] = "set_prize_2"
            await update.message.reply_text("🥈 2ኛ ሽልማት ፃፍ:")
            return
        if "PRIZE 3️⃣" in text:
            ctx.user_data["admin_action"] = "set_prize_3"
            await update.message.reply_text("🥉 3ኛ ሽልማት ፃፍ:")
            return
        if "CHANGE IMAGE 🖼" in text:
            ctx.user_data["admin_action"] = "set_home_image"
            await update.message.reply_text("🖼 አዲስ ምስል (ፎቶ) ላክ፦ Home ገጽ ላይ ይታያል።")
            return
        if "REMOVE IMAGE 🗑" in text:
            await db.set_setting("home_image", "")
            await update.message.reply_text("✅ ምስል ተሰርዟል።")
            return
        if "⚠️ RESET ⚠️" in text:
            await update.message.reply_text(
                "⚠️ *እርግጠኛ ነህ? ሁሉም ቁጥሮች እና ክፍያዎች ይጠፋሉ!*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ አዎ Reset", callback_data="admin_reset_yes")],
                    [InlineKeyboardButton("✖️ አይ",      callback_data="admin_panel")]
                ])
            )
            return

    if ctx.user_data.get("admin_action"):
        await handle_text_input(update, ctx)
    elif not ctx.user_data.get("lang"):
        await show_home(update, ctx)


# ══════════════════════════════════════════
# MY TICKETS
# ══════════════════════════════════════════
async def show_my_tickets(update, ctx):
    user      = update.effective_user
    lang      = ctx.user_data.get("lang", "am")
    confirmed = await db.get_user_tickets(user.id, "taken")
    pending_t = await db.get_user_tickets(user.id, "reserved")
    price     = int(await db.get_setting("ticket_price"))
    username  = user.full_name or user.username or "—"

    if not confirmed and not pending_t:
        reply_text = T[lang]["no_tickets"]
    else:
        reply_text = T[lang]["my_tickets_hdr"] + "\n"
        if confirmed:
            nums  = sorted([r[0] for r in confirmed])
            total = len(nums) * price
            reply_text += "\n" + T[lang]["my_tickets_body"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums),
                total=total
            )
        if pending_t:
            nums  = sorted([r[0] for r in pending_t])
            total = len(nums) * price
            reply_text += "\n" + T[lang]["my_tickets_pending"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums),
                total=total
            )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(T[lang]["referral_btn"],  callback_data="show_referral")],
        [InlineKeyboardButton(T[lang]["back_home_btn"], callback_data="main_menu")],
    ])
    await update.message.reply_text(reply_text, parse_mode="Markdown", reply_markup=keyboard)


async def my_tickets_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user     = update.effective_user
    lang     = ctx.user_data.get("lang", "am")
    confirmed= await db.get_user_tickets(user.id, "taken")
    pending_t= await db.get_user_tickets(user.id, "reserved")
    price    = int(await db.get_setting("ticket_price"))
    username = user.full_name or user.username or "—"

    if not confirmed and not pending_t:
        text = T[lang]["no_tickets"]
    else:
        text = T[lang]["my_tickets_hdr"] + "\n"
        if confirmed:
            nums  = sorted([r[0] for r in confirmed])
            total = len(nums) * price
            text += "\n" + T[lang]["my_tickets_body"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums), total=total
            )
        if pending_t:
            nums  = sorted([r[0] for r in pending_t])
            total = len(nums) * price
            text += "\n" + T[lang]["my_tickets_pending"].format(
                username=username,
                nums=", ".join(map(str, nums)),
                count=len(nums), total=total
            )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(T[lang]["referral_btn"],  callback_data="show_referral")],
        [InlineKeyboardButton(T[lang]["back_home_btn"], callback_data="main_menu")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ══════════════════════════════════════════
# PAYMENT FLOW — numbers arrive from index.html, payment itself is
# handled entirely in payment.html (separate Mini App) + Flask endpoints
# (/payment-config, /submit-payment). This handler only locks the
# numbers and hands off to the payment Mini App via a WebApp button.
# ══════════════════════════════════════════
async def web_app_data_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
    except Exception as e:
        logger.error(f"WebApp data parse error: {e}")
        return

    if data.get("action") != "buy_tickets":
        return

    numbers = data.get("numbers", [])
    if not numbers:
        return

    price       = int(await db.get_setting("ticket_price"))
    total_price = len(numbers) * price

    for num in numbers:
        ticket = await db.get_ticket(num)
        if ticket and ticket[4] in ("taken", "reserved", "pending_payment"):
            await update.message.reply_text(t(ctx, "num_taken", num=num))
            return

    user     = update.effective_user
    username = f"@{user.username}" if user.username else (user.full_name or "—")
    await db.lock_tickets_pending_payment(numbers, user.id, username)

    ctx.user_data["selected"] = numbers

    lang     = ctx.user_data.get("lang", "am")
    nums_str = ",".join(map(str, sorted(numbers)))

    # ቀድሞ የተጋራው ኮንታክት (ስም/ስልክ) ካለ payment mini app ላይ ቅድመ-ሙላ ይደረጋል
    profile    = await db.get_profile(user.id)
    first_name = profile.get("first_name", "") if profile else ""
    last_name  = profile.get("last_name", "") if profile else ""
    phone      = profile.get("phone", "") if profile else ""

    payment_url = (
        f"{PAYMENT_APP_URL}"
        f"?numbers={nums_str}&total={total_price}&user_id={user.id}"
        f"&username={quote(username)}&lang={lang}"
        f"&first_name={quote(first_name)}&last_name={quote(last_name)}&phone={quote(phone)}"
    )

    text = t(ctx, "payment_intro",
             nums=", ".join(map(str, sorted(numbers))),
             count=len(numbers),
             total=total_price)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            PAYMENT_CONTINUE_TEXT.get(lang, PAYMENT_CONTINUE_TEXT["am"]),
            web_app=WebAppInfo(url=payment_url)
        )],
        [InlineKeyboardButton(t(ctx, "pay_back_btn"), callback_data="main_menu")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


# ══════════════════════════════════════════
# REFERRAL
# ══════════════════════════════════════════
async def referral_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user         = update.effective_user
    lang         = ctx.user_data.get("lang", "am")
    bot_username = (await ctx.bot.get_me()).username
    ref_link     = f"https://t.me/{bot_username}?start=ref_{user.id}"
    count        = await db.get_referral_count(str(user.id))
    reward       = count * 2

    text = T[lang]["referral_info"].format(link=ref_link, count=count, reward=reward)
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(T[lang]["back_home_btn"], callback_data="main_menu")
        ]])
    )
