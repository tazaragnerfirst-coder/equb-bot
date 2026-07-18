# ══════════════════════════════════════════
# main.py
# Entry point ብቻ፦ Application መገንባት፣ handlers መመዝገብ፣ Flask + bot ማስጀመር።
# ⚠️ Business logic እዚህ የለም — ሁሉም በተለያዩ ፋይሎች ውስጥ ነው (handlers_user.py,
#    handlers_admin.py, membership.py, group_list.py, flask_routes.py)።
# ══════════════════════════════════════════
import asyncio
import logging

from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters,
)

import database as db
from config import BOT_TOKEN

from flask_routes import keep_alive
from helpers import is_admin

from handlers_user import (
    start, language_cmd, lang_cb, check_membership_cb,
    home_cb, my_tickets_cb, referral_cb, web_app_data_handler,
    any_message_home,
)
from handlers_admin import (
    admin_panel_cb, admin_pending_cb, admin_stats_cb, admin_find_cb,
    admin_reset_yes_cb, broadcast_confirm_cb, admin_broadcast_edit_cb,
    approve_reject_cb, admin_photo_handler, show_admin_panel,
    watch_pending_payments,
)
from membership import contact_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def post_init(application):
    await db.init_db()
    asyncio.create_task(watch_pending_payments(application.bot))


def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("language", language_cmd))

    async def admin_cmd(update, ctx):
        if is_admin(update.effective_user.id):
            await show_admin_panel(update, ctx)
    app.add_handler(CommandHandler("admin", admin_cmd))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(lang_cb,              pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(home_cb,              pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(my_tickets_cb,        pattern="^my_tickets$"))
    app.add_handler(CallbackQueryHandler(referral_cb,          pattern="^show_referral$"))
    app.add_handler(CallbackQueryHandler(approve_reject_cb,    pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(check_membership_cb,  pattern="^check_membership$"))

    app.add_handler(CallbackQueryHandler(admin_panel_cb,       pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_pending_cb,     pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_stats_cb,       pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_find_cb,        pattern="^admin_find$"))
    app.add_handler(CallbackQueryHandler(admin_reset_yes_cb,   pattern="^admin_reset_yes$"))
    app.add_handler(CallbackQueryHandler(broadcast_confirm_cb, pattern="^broadcast_confirm$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_edit_cb, pattern="^admin_broadcast$"))

    # Message handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.PHOTO, admin_photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, any_message_home))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
