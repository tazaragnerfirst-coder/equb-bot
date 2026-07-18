# ══════════════════════════════════════════
# membership.py
# ግሩፕ/ቻናል አባልነት ማረጋገጫ + ኮንታክት መጠየቅ (onboarding gate)።
# ══════════════════════════════════════════
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes

import database as db
from config import GROUP_ID

logger = logging.getLogger(__name__)

try:
    from config import REQUIRED_GROUP_LINK
except ImportError:
    REQUIRED_GROUP_LINK = f"https://t.me/c/{str(GROUP_ID).replace('-100', '')}"

try:
    from config import CHANNEL_ID, REQUIRED_CHANNEL_LINK
except ImportError:
    CHANNEL_ID = None
    REQUIRED_CHANNEL_LINK = None

from translations import T
from helpers import is_admin


async def is_member_of_group(bot, user_id: int) -> bool:
    """ተጠቃሚ ግሩፕ ውስጥ አለ ወይ አረጋግጥ"""
    try:
        from telegram.constants import ChatMemberStatus
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception as e:
        logger.warning(f"Membership check error for {user_id}: {e}")
        return True


async def is_member_of_channel(bot, user_id: int) -> bool:
    """ተጠቃሚ ቻናል ውስጥ አለ ወይ አረጋግጥ (ቻናል ካልተዋቀረ True ይመልሳል)"""
    if not CHANNEL_ID:
        return True
    try:
        from telegram.constants import ChatMemberStatus
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception as e:
        logger.warning(f"Channel membership check error for {user_id}: {e}")
        return True


async def is_fully_joined(bot, user_id: int) -> bool:
    """ግሩፕ እና (ካለ) ቻናል ሁለቱንም አረጋግጥ"""
    group_ok   = await is_member_of_group(bot, user_id)
    channel_ok = await is_member_of_channel(bot, user_id)
    return group_ok and channel_ok


async def send_join_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ (እና ካለ ቻናል) ቀላቅሉ ማሳወቂያ ይላካል"""
    lang = ctx.user_data.get("lang", "am")

    await update.effective_message.reply_text(
        "⏳",
        reply_markup=ReplyKeyboardRemove()
    )

    keyboard_rows = [[InlineKeyboardButton(T[lang]["join_btn"], url=REQUIRED_GROUP_LINK)]]
    if REQUIRED_CHANNEL_LINK:
        keyboard_rows.append([InlineKeyboardButton(T[lang]["visit_channel_btn"], url=REQUIRED_CHANNEL_LINK)])
    keyboard_rows.append([InlineKeyboardButton(T[lang]["joined_btn"], callback_data="check_membership")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)

    await update.effective_message.reply_text(
        T[lang]["join_required"],
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def send_contact_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ ከተቀላቀሉ በኋላ ኮንታክት እንዲያጋሩ ይጠየቃል"""
    lang = ctx.user_data.get("lang", "am")
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(T[lang]["contact_btn"], request_contact=True)],
         [KeyboardButton(T[lang]["skip_btn"])]],
        resize_keyboard=True
    )
    await update.effective_message.reply_text(
        T[lang]["contact_required"],
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def proceed_after_membership(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """ግሩፕ አባልነት ከተረጋገጠ በኋላ፦ አድሚን ከሆነ ወይም ቀድሞ ኮንታክት ካጋራ ወደ home፣
    ካልሆነ ግን ኮንታክት እንዲያጋራ ይጠየቃል።"""
    # NOTE: show_home is imported lazily inside the function to avoid a
    # circular import (handlers_user.py imports from membership.py too).
    from handlers_user import show_home

    user = update.effective_user
    if is_admin(user.id):
        await show_home(update, ctx)
        return
    profile = await db.get_profile(user.id)
    if not profile:
        await send_contact_prompt(update, ctx)
        return
    ctx.user_data["_profile_checked"] = True
    await show_home(update, ctx)


async def contact_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user    = update.effective_user
    lang    = ctx.user_data.get("lang", "am")

    if not contact or contact.user_id != user.id:
        await update.message.reply_text(T[lang]["contact_own_only"])
        return

    first = contact.first_name or user.first_name or ""
    last  = contact.last_name or user.last_name or ""
    phone = contact.phone_number or ""
    if phone and not phone.startswith("+"):
        phone = "+" + phone

    await db.save_profile(user.id, first, last, phone)
    ctx.user_data["_profile_checked"] = True

    from handlers_user import show_home
    await show_home(update, ctx)
