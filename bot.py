"""
OPEN TICKET - New /start flow
/start -> Choose language -> Join Channel & Group -> Mini App
Each step deletes the previous bot message before sending the next.

Requires: python-telegram-bot==20.7
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
CHANNEL_ID = -1004418912771
GROUP_ID = -1004316748630
MINI_APP_URL = "https://tazaragnerfirst-coder.github.io/equb-bot"

CHANNEL_LINK = "https://t.me/OpenTicket_GE"
GROUP_LINK = "https://t.me/taza_equb"

TEXT = {
    "am": {
        "choose_lang": "ቋንቋ ይምረጡ / Choose language",
        "join": "✅ ለመቀጠል Channel እና Group ውስጥ ይግቡ፣ ከዛ 'አረጋግጥ' ይጫኑ።",
        "not_joined": "❌ እባክዎ ሁለቱንም (Channel እና Group) ይግቡ፣ ከዛ እንደገና ይሞክሩ።",
        "verify_btn": "✅ አረጋግጥ",
        "join_channel_btn": "📢 Channel ግባ",
        "join_group_btn": "👥 Group ግባ",
        "open_app": "🎟️ ትኬት ለመግዛት ይክፈቱ",
        "welcome": "🎉 እንኳን ደህና መጡ! Mini App ን ይክፈቱ፡",
    },
    "en": {
        "choose_lang": "ቋንቋ ይምረጡ / Choose language",
        "join": "✅ Please join the Channel and Group to continue, then tap 'Verify'.",
        "not_joined": "❌ Please join BOTH the Channel and Group, then try again.",
        "verify_btn": "✅ Verify",
        "join_channel_btn": "📢 Join Channel",
        "join_group_btn": "👥 Join Group",
        "open_app": "🎟️ Open to buy ticket",
        "welcome": "🎉 Welcome! Open the Mini App:",
    },
    "or": {
        "choose_lang": "ቋንቋ ይምረጡ / Choose language",
        "join": "✅ Itti fufuu keessan dura Channel fi Group seenaa, ergasii 'Mirkaneessi' tuqaa.",
        "not_joined": "❌ Maaloo Channel fi Group lamaan seenaa, ergasii irra deebi'ii yaali.",
        "verify_btn": "✅ Mirkaneessi",
        "join_channel_btn": "📢 Channel Seeni",
        "join_group_btn": "👥 Group Seeni",
        "open_app": "🎟️ Tikeeta bituuf banaa",
        "welcome": "🎉 Baga nagaan dhuftan! Mini App banaa:",
    },
}


async def _delete_prev(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Delete the previously tracked bot message, if any."""
    msg_id = context.user_data.get("last_msg_id")
    if msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.debug(f"Could not delete message {msg_id}: {e}")
        context.user_data["last_msg_id"] = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # delete the user's /start message too (optional, keeps chat clean)
    try:
        await update.message.delete()
    except Exception:
        pass

    await _delete_prev(context, chat_id)

    keyboard = [
        [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("Afaan Oromoo", callback_data="lang_or")],
    ]
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=TEXT["en"]["choose_lang"],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data["last_msg_id"] = sent.message_id


async def language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    lang = query.data.split("_")[1]  # am / en / or
    context.user_data["lang"] = lang
    t = TEXT[lang]

    await _delete_prev(context, chat_id)
    await show_join_step(update, context, lang)


async def show_join_step(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    chat_id = update.effective_chat.id
    t = TEXT[lang]

    keyboard = [
        [InlineKeyboardButton(t["join_channel_btn"], url=CHANNEL_LINK)],
        [InlineKeyboardButton(t["join_group_btn"], url=GROUP_LINK)],
        [InlineKeyboardButton(t["verify_btn"], callback_data="verify_join")],
    ]
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=t["join"],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data["last_msg_id"] = sent.message_id


async def verify_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    lang = context.user_data.get("lang", "en")
    t = TEXT[lang]

    in_channel = await _is_member(context, CHANNEL_ID, user_id)
    in_group = await _is_member(context, GROUP_ID, user_id)

    if in_channel and in_group:
        await _delete_prev(context, chat_id)
        await show_mini_app(update, context, lang)
    else:
        await query.answer(t["not_joined"], show_alert=True)


async def _is_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Membership check failed for {chat_id}: {e}")
        return False


async def show_mini_app(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    chat_id = update.effective_chat.id
    t = TEXT[lang]

    app_url = f"{MINI_APP_URL}?lang={lang}"
    keyboard = [
        [InlineKeyboardButton(t["open_app"], web_app=WebAppInfo(url=app_url))]
    ]
    sent = await context.bot.send_message(
        chat_id=chat_id,
        text=t["welcome"],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data["last_msg_id"] = sent.message_id


def register_start_flow(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(language_chosen, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(verify_join, pattern="^verify_join$"))
