import os
import json
import asyncio
import logging
from datetime import date, datetime

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

# ─── INIT ADMIN SDK ───
_cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
if _cred_json and not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(_cred_json))
    firebase_admin.initialize_app(cred)

db = firestore.client()


# ─── HELPER: run sync Firestore calls in a thread (keeps async bot non-blocking) ───
async def _run(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


# ─── INIT ───
def _init_db_sync():
    ref = db.collection("settings").document("config")
    doc = ref.get()
    if not doc.exists:
        ref.set({
            "total_tickets": 1000,
            "ticket_price": 400,
            "prize_1": "1ኛ ሽልማት",
            "prize_2": "2ኛ ሽልማት",
            "prize_3": "3ኛ ሽልማት",
            "lottery_title": "GETU DURESA - EQUB",
        })

async def init_db():
    await _run(_init_db_sync)


# ─── SETTINGS ───
def _get_setting_sync(key):
    doc = db.collection("settings").document("config").get()
    if not doc.exists:
        return None
    return doc.to_dict().get(key)

async def get_setting(key):
    return await _run(_get_setting_sync, key)

def _set_setting_sync(key, value):
    db.collection("settings").document("config").set({key: value}, merge=True)

async def set_setting(key, value):
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    await _run(_set_setting_sync, key, value)


# ─── TICKETS ───
def _get_ticket_sync(number):
    doc = db.collection("tickets").document(str(number)).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    return (
        number,
        d.get("user_id"),
        d.get("username"),
        d.get("phone"),
        d.get("status"),
    )

async def get_ticket(number):
    return await _run(_get_ticket_sync, number)

def _get_tickets_range_sync(start, end):
    docs = db.collection("tickets").stream()
    result = []
    for doc in docs:
        num = int(doc.id)
        if start <= num <= end:
            d = doc.to_dict()
            result.append((num, d.get("user_id"), d.get("status"), d.get("phone")))
    return result

async def get_tickets_range(start, end):
    return await _run(_get_tickets_range_sync, start, end)

def _get_all_tickets_full_sync(total):
    docs = db.collection("tickets").stream()
    result = {}
    for doc in docs:
        num = int(doc.id)
        if 1 <= num <= total:
            d = doc.to_dict()
            result[num] = (d.get("phone") or "", d.get("status") or "free")
    return result

async def get_all_tickets_full(total):
    return await _run(_get_all_tickets_full_sync, total)

def _reserve_tickets_sync(numbers, user_id, username, phone):
    batch = db.batch()
    for num in numbers:
        ref = db.collection("tickets").document(str(num))
        batch.set(ref, {
            "status": "reserved",
            "user_id": str(user_id),
            "username": str(username),
            "phone": str(phone),
            "created_at": datetime.now().isoformat(),
        })
    batch.commit()

async def reserve_tickets(numbers, user_id, username, phone):
    await _run(_reserve_tickets_sync, numbers, user_id, username, phone)

def _confirm_tickets_sync(numbers, user_id, username, phone):
    batch = db.batch()
    for num in numbers:
        ref = db.collection("tickets").document(str(num))
        batch.set(ref, {
            "status": "taken",
            "user_id": str(user_id),
            "username": str(username),
            "phone": str(phone),
            "created_at": datetime.now().isoformat(),
        })
    batch.commit()

async def confirm_tickets(numbers, user_id, username, phone):
    await _run(_confirm_tickets_sync, numbers, user_id, username, phone)

def _free_tickets_sync(numbers):
    batch = db.batch()
    for num in numbers:
        batch.delete(db.collection("tickets").document(str(num)))
    batch.commit()

async def free_tickets(numbers):
    await _run(_free_tickets_sync, numbers)

def _count_taken_tickets_sync():
    docs = db.collection("tickets").where("status", "==", "taken").stream()
    return sum(1 for _ in docs)

async def count_taken_tickets():
    return await _run(_count_taken_tickets_sync)

def _count_pending_tickets_sync():
    docs = db.collection("tickets").where("status", "==", "reserved").stream()
    return sum(1 for _ in docs)

async def count_pending_tickets():
    return await _run(_count_pending_tickets_sync)

def _count_tickets_today_sync():
    today = date.today().isoformat()
    docs = db.collection("payments").where("status", "==", "approved").stream()
    count = 0
    for doc in docs:
        d = doc.to_dict()
        reviewed = d.get("reviewed_at") or ""
        if reviewed.startswith(today):
            nums = d.get("numbers") or ""
            count += len(nums.split(",")) if nums else 0
    return count

async def count_tickets_today():
    return await _run(_count_tickets_today_sync)

def _get_user_tickets_sync(user_id, status):
    docs = db.collection("tickets").where("user_id", "==", str(user_id)).where("status", "==", status).stream()
    return [(int(doc.id),) for doc in docs]

async def get_user_tickets(user_id, status):
    return await _run(_get_user_tickets_sync, user_id, status)


# ─── PAYMENTS ───
def _next_payment_id_sync():
    docs = db.collection("payments").stream()
    ids = [int(doc.id) for doc in docs]
    return max(ids) + 1 if ids else 1

def _add_payment_sync(user_id, username, phone, numbers, receipt_file_id, payment_method):
    p_id = _next_payment_id_sync()
    numbers_str = ",".join(map(str, numbers))
    db.collection("payments").document(str(p_id)).set({
        "user_id": str(user_id),
        "username": str(username),
        "phone": str(phone),
        "numbers": numbers_str,
        "receipt_file_id": str(receipt_file_id),
        "payment_method": str(payment_method),
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "reviewed_by": "",
        "reviewed_at": "",
    })
    return p_id

async def add_payment(user_id, username, phone, numbers, receipt_file_id, payment_method):
    return await _run(_add_payment_sync, user_id, username, phone, numbers, receipt_file_id, payment_method)

def _get_payment_sync(payment_id):
    doc = db.collection("payments").document(str(payment_id)).get()
    if not doc.exists:
        return None
    d = doc.to_dict()
    return (
        payment_id, d.get("user_id"), d.get("username"), d.get("phone"),
        d.get("numbers"), d.get("receipt_file_id"), d.get("payment_method"),
        d.get("status"), d.get("created_at"), d.get("reviewed_by"), d.get("reviewed_at"),
    )

async def get_payment(payment_id):
    return await _run(_get_payment_sync, payment_id)

def _get_pending_payments_sync():
    docs = db.collection("payments").where("status", "==", "pending").stream()
    result = []
    for doc in docs:
        d = doc.to_dict()
        result.append((
            int(doc.id), d.get("user_id"), d.get("username"), d.get("phone"),
            d.get("numbers"), d.get("receipt_file_id"), d.get("payment_method"), d.get("status"),
        ))
    return sorted(result, key=lambda x: x[0])

async def get_pending_payments():
    return await _run(_get_pending_payments_sync)

def _get_all_approved_payments_sync():
    docs = db.collection("payments").where("status", "==", "approved").stream()
    result = []
    for doc in docs:
        d = doc.to_dict()
        result.append((
            int(doc.id), d.get("username"), d.get("phone"), d.get("numbers"),
            d.get("receipt_file_id"), d.get("payment_method"), d.get("reviewed_at"),
        ))
    return sorted(result, key=lambda x: x[0], reverse=True)

async def get_all_approved_payments():
    return await _run(_get_all_approved_payments_sync)

def _update_payment_status_sync(payment_id, status, reviewed_by):
    db.collection("payments").document(str(payment_id)).set({
        "status": status,
        "reviewed_by": str(reviewed_by),
        "reviewed_at": datetime.now().isoformat(),
    }, merge=True)

async def update_payment_status(payment_id, status, reviewed_by):
    await _run(_update_payment_status_sync, payment_id, status, reviewed_by)

def _find_payment_by_number_sync(number):
    docs = db.collection("payments").stream()
    for doc in docs:
        d = doc.to_dict()
        nums = d.get("numbers") or ""
        if str(number) in nums.split(","):
            return (
                int(doc.id), d.get("user_id"), d.get("username"), d.get("phone"),
                d.get("numbers"), d.get("receipt_file_id"), d.get("payment_method"),
                d.get("status"), d.get("reviewed_at"),
            )
    return None

async def find_payment_by_number(number):
    return await _run(_find_payment_by_number_sync, number)


# ─── USERS ───
def _get_all_users_sync():
    docs = db.collection("payments").stream()
    seen, result = set(), []
    for doc in docs:
        uid = doc.to_dict().get("user_id")
        if uid and uid not in seen:
            seen.add(uid)
            result.append((uid,))
    return result

async def get_all_users():
    return await _run(_get_all_users_sync)


# ─── GROUP MESSAGES ───
def _save_group_message_ids_sync(chat_id, message_ids):
    db.collection("meta").document("group_messages").set({
        "chat_id": str(chat_id),
        "message_ids": ",".join(map(str, message_ids)),
    })

async def save_group_message_ids(chat_id, message_ids):
    await _run(_save_group_message_ids_sync, chat_id, message_ids)

def _get_group_message_ids_sync():
    doc = db.collection("meta").document("group_messages").get()
    if not doc.exists:
        return []
    d = doc.to_dict()
    ids_str = d.get("message_ids") or ""
    chat_id = d.get("chat_id") or ""
    if not ids_str or not chat_id:
        return []
    return [(int(i), int(chat_id)) for i in ids_str.split(",") if i]

async def get_group_message_ids():
    return await _run(_get_group_message_ids_sync)

def _clear_group_messages_sync():
    db.collection("meta").document("group_messages").set({"chat_id": "", "message_ids": ""})

async def clear_group_messages():
    await _run(_clear_group_messages_sync)


# ─── REFERRAL SYSTEM ───
def _add_referral_sync(referrer_id, new_user_id):
    ref_doc = db.collection("referrals").document(str(new_user_id))
    if ref_doc.get().exists:
        return
    ref_doc.set({
        "referrer_id": str(referrer_id),
        "referred_at": datetime.now().isoformat(),
    })
    count_ref = db.collection("referral_counts").document(str(referrer_id))
    snap = count_ref.get()
    current = 0
    if snap.exists:
        try:
            current = int(snap.to_dict().get("count", 0))
        except (TypeError, ValueError):
            current = 0
    count_ref.set({
        "count": current + 1,
        "updated_at": datetime.now().isoformat(),
    })

async def add_referral(referrer_id: str, new_user_id: str):
    await _run(_add_referral_sync, referrer_id, new_user_id)

def _get_referral_count_sync(user_id):
    doc = db.collection("referral_counts").document(str(user_id)).get()
    if not doc.exists:
        return 0
    try:
        return int(doc.to_dict().get("count", 0))
    except (TypeError, ValueError):
        return 0

async def get_referral_count(user_id: str) -> int:
    return await _run(_get_referral_count_sync, user_id)

def _get_all_referral_counts_sync():
    docs = db.collection("referral_counts").stream()
    result = []
    for doc in docs:
        try:
            count = int(doc.to_dict().get("count", 0))
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            result.append((doc.id, count))
    return sorted(result, key=lambda x: x[1], reverse=True)

async def get_all_referral_counts():
    return await _run(_get_all_referral_counts_sync)


# ─── RESET ───
def _reset_lottery_sync():
    # Note: referrals and referral_counts are intentionally NOT cleared here.
    # Referral data persists permanently across lottery rounds (not tied to a round).
    for doc in db.collection("tickets").stream():
        doc.reference.delete()
    for doc in db.collection("payments").stream():
        doc.reference.delete()
    _clear_group_messages_sync()

async def reset_lottery():
    await _run(_reset_lottery_sync)
