import hashlib
import hmac
from urllib.parse import parse_qsl
from flask import request, jsonify
from firebase_admin import auth as fb_auth
from config import BOT_TOKEN, ADMIN_IDS

def _check_telegram_auth(init_data: str) -> dict | None:
    """initData ያረጋግጣል (Telegram HMAC signature)። ትክክል ካልሆነ None ይመልሳል።"""
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None
    return parsed


def register_admin_verify_route(flask_app):
    @flask_app.route("/verify-admin", methods=["POST"])
    def verify_admin():
        body = request.get_json(silent=True) or {}
        init_data = body.get("initData", "")

        parsed = _check_telegram_auth(init_data)
        if not parsed:
            return jsonify({"error": "invalid_signature"}), 401

        import json as _json
        user = _json.loads(parsed.get("user", "{}"))
        user_id = user.get("id")

        if user_id not in ADMIN_IDS:
            return jsonify({"error": "not_admin"}), 403

        token = fb_auth.create_custom_token(str(user_id))
        return jsonify({"token": token.decode()})