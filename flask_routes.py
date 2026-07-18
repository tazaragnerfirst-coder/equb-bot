# ══════════════════════════════════════════
# flask_routes.py
# ሁሉም Flask endpoints (keep-alive server + Mini App API) እዚህ ብቻ ናቸው።
# ══════════════════════════════════════════
import json
import asyncio
import logging
from threading import Thread

import requests as req_lib
from flask import Flask, Response, request

import database as db
from database import db as fdb
from config import BOT_TOKEN, ADMIN_IDS, CBE_ACCOUNT, CBE_NAME, TELEBIRR_ACCOUNT, TELEBIRR_NAME
from config_extra import BRAND_SIGNATURE
from translations import T

logger = logging.getLogger(__name__)

flask_app = Flask('', static_folder='.', static_url_path='')


@flask_app.route('/')
def home():
    return "Bot is alive! 🤖"


# ══════════════════════════════════════════
# CORS HELPERS (payment.html is hosted on GitHub Pages — different origin)
# ══════════════════════════════════════════
def _cors_json(data, status=200):
    resp = flask_app.response_class(
        response=json.dumps(data),
        status=status,
        mimetype='application/json'
    )
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


def _cors_preflight():
    resp = flask_app.response_class(status=204)
    resp.headers['Access-Control-Allow-Origin']  = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    return resp


_bot_username_cache = {"value": None}


def _get_bot_username_cached():
    if _bot_username_cache["value"]:
        return _bot_username_cache["value"]
    try:
        r = req_lib.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10)
        r.raise_for_status()
        username = r.json().get("result", {}).get("username")
        if username:
            _bot_username_cache["value"] = username
        return username
    except Exception as e:
        logger.error(f"getMe error: {e}")
        return None


# ══════════════════════════════════════════
# RECEIPT IMAGE PROXY
# ══════════════════════════════════════════
@flask_app.route('/get-receipt/<int:pid>')
def get_receipt_image(pid):
    try:
        doc = fdb.collection('payments').document(str(pid)).get()
        if not doc.exists:
            return "Not found", 404
        file_id = doc.to_dict().get('receipt_file_id')
        if not file_id:
            return "No receipt", 404
        r = req_lib.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=10
        )
        r.raise_for_status()
        result = r.json().get("result", {})
        file_path = result.get("file_path")
        if not file_path:
            return "File path not found", 404
        img = req_lib.get(
            f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}",
            timeout=15
        )
        img.raise_for_status()
        return Response(
            img.content,
            content_type=img.headers.get('content-type', 'image/jpeg')
        )
    except req_lib.exceptions.Timeout:
        logger.error(f"get_receipt_image timeout: pid={pid}")
        return "Timeout", 504
    except Exception as e:
        logger.error(f"get_receipt_image error pid={pid}: {e}")
        return "Error", 500


# ══════════════════════════════════════════
# PAYMENT CONFIG (bank accounts + price) — for payment.html
# ══════════════════════════════════════════
@flask_app.route('/payment-config', methods=['GET', 'OPTIONS'])
def payment_config():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    try:
        price = asyncio.run(db.get_setting("ticket_price"))
        return _cors_json({
            "cbe_account": CBE_ACCOUNT,
            "cbe_name": CBE_NAME,
            "telebirr_account": TELEBIRR_ACCOUNT,
            "telebirr_name": TELEBIRR_NAME,
            "ticket_price": int(price) if price else 0,
        })
    except Exception as e:
        logger.error(f"payment_config error: {e}")
        return _cors_json({"status": "error", "message": "Server error"}, 500)


# ══════════════════════════════════════════
# SUBMIT PAYMENT — receives phone/name/method/receipt from payment.html
# ══════════════════════════════════════════
@flask_app.route('/submit-payment', methods=['POST', 'OPTIONS'])
def submit_payment():
    if request.method == 'OPTIONS':
        return _cors_preflight()
    try:
        numbers_str = request.form.get('numbers', '').strip()
        user_id     = request.form.get('user_id', '').strip()
        username    = request.form.get('username', '—').strip() or '—'
        full_name   = request.form.get('full_name', '').strip()
        phone       = request.form.get('phone', '').strip()
        method      = request.form.get('method', '').strip()
        lang        = request.form.get('lang', 'am').strip() or 'am'
        receipt     = request.files.get('receipt')

        if lang not in T:
            lang = 'am'

        if not (numbers_str and user_id and full_name and phone and method and receipt):
            return _cors_json({"status": "error", "message": "Missing fields"}, 400)

        try:
            numbers = [int(n) for n in numbers_str.split(',') if n.strip().isdigit()]
        except ValueError:
            numbers = []
        if not numbers:
            return _cors_json({"status": "error", "message": "No valid numbers"}, 400)

        # Re-validate availability (guards against race conditions since selection)
        for num in numbers:
            ticket = asyncio.run(db.get_ticket(num))
            if ticket and ticket[4] == "taken":
                return _cors_json({"status": "error", "message": f"Number {num} already taken"}, 409)

        price       = int(asyncio.run(db.get_setting("ticket_price")) or 0)
        total_price = len(numbers) * price

        # Upload receipt bytes to Telegram once, to obtain a reusable file_id
        log_chat_id = ADMIN_IDS[0]
        upload = req_lib.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": log_chat_id, "caption": "📥 Receipt (Mini App upload)"},
            files={"photo": (receipt.filename or "receipt.jpg", receipt.stream, receipt.mimetype or "image/jpeg")},
            timeout=20
        )
        upload.raise_for_status()
        upload_result = upload.json().get("result", {})
        photos = upload_result.get("photo", [])
        if not photos:
            return _cors_json({"status": "error", "message": "Receipt upload failed"}, 502)
        file_id = photos[-1]["file_id"]

        payment_id = asyncio.run(db.add_payment(
            user_id, username, phone, numbers, file_id, method, full_name=full_name
        ))
        asyncio.run(db.reserve_tickets(numbers, user_id, username, phone))

        bot_username  = _get_bot_username_cached()
        receipt_link  = f"https://t.me/{bot_username}?start=receipt_{payment_id}" if bot_username else None
        tg_username   = username if str(username).startswith("@") or username == "—" else f"@{username}"

        admin_caption = (
            f"💳 <b>New Payment!</b>\n"
            f"{'─'*20}\n"
            f"👤 <b>{full_name}</b>\n"
            f"🔗 {tg_username}\n"
            f"📞 {phone}\n"
            f"🆔 <code>{user_id}</code>\n"
            f"{'─'*20}\n"
            f"🎟 <b>Numbers:</b> {', '.join(map(str, sorted(numbers)))}\n"
            f"📦 <b>Count:</b> {len(numbers)}\n"
            f"💰 <b>Total:</b> {total_price} ETB\n"
            f"💳 <b>Method:</b> {method}\n"
            f"🔖 <b>#{payment_id}</b>"
        )

        inline_kb = [[
            {"text": "✅ Approve", "callback_data": f"approve_{payment_id}"},
            {"text": "❌ Reject",  "callback_data": f"reject_{payment_id}"}
        ]]
        if receipt_link:
            inline_kb.append([{"text": "🧾 ደረሰኝ ይመልከቱ", "url": receipt_link}])
        keyboard = {"inline_keyboard": inline_kb}

        for admin_id in ADMIN_IDS:
            try:
                req_lib.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                    data={
                        "chat_id": admin_id,
                        "photo": file_id,
                        "caption": admin_caption,
                        "parse_mode": "HTML",
                        "reply_markup": json.dumps(keyboard),
                    },
                    timeout=15
                )
            except Exception as e:
                logger.error(f"Admin notify (mini app) error: {e}")

        # ── ተጠቃሚው ደረሰኙ በትክክል መላኩን የሚያረጋግጥ መልክት ──
        try:
            confirm_text = T[lang]["sent_ok"].format(
                name=full_name,
                phone=phone,
                nums=", ".join(map(str, sorted(numbers))),
                total=total_price,
                method=method,
                brand=BRAND_SIGNATURE,
            )
            req_lib.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": user_id, "text": confirm_text, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            logger.error(f"User confirm notify error: {e}")

        return _cors_json({"status": "ok", "payment_id": payment_id})

    except Exception as e:
        logger.error(f"submit_payment error: {e}")
        return _cors_json({"status": "error", "message": "Server error"}, 500)


def keep_alive():
    th = Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080))
    th.daemon = True
    th.start()


# admin_auth registers its own route on the shared flask_app instance
from admin_auth import register_admin_verify_route
register_admin_verify_route(flask_app)
