import os
import json
import asyncio
import logging
from datetime import date, datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

# --- INIT ADMIN SDK ---
_cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
if _cred_json and not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(_cred_json))
    firebase_admin.initialize_app(cred)

db = firestore.client()

async def _run(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

# --- INIT SETTINGS ---
def _init_db_sync():
    ref = db.collection("settings").document("config")
    if not ref.get().exists:
        ref.set({
            "total_tickets": 1000, "ticket_price": 400,
            "prize_1": "1st Prize", "prize_2": "2nd Prize", "prize_3": "3rd Prize",
            "lottery_title": "GETU DURESA - EQUB",
        })

async def init_db(): await _run(_init_db_sync)

# --- USER PROFILES (saved from Telegram "Share Contact") ---
def _save_profile_sync(user_id, first, last, phone):
    db.collection("user_profiles").document(str(user_id)).set({
        "first_name": first, "last_name": last, "phone": phone,
        "updated_at": datetime.now().isoformat()
    })

async def save_profile(user_id, first, last, phone): await _run(_save_profile_sync, user_id, first, last, phone)

def _get_profile_sync(user_id):
    doc = db.collection("user_profiles").document(str(user_id)).get()
    return doc.to_dict() if doc.exists else None

async def get_profile(user_id): return await _run(_get_profile_sync, user_id)

# --- SETTINGS & TICKETS ---
async def get_setting(key):
    doc = await _run(lambda: db.collection("settings").document("config").get())
    return doc.to_dict().get(key) if doc.exists else None

async def set_setting(key, value):
    await _run(lambda: db.collection("settings").document("config").set({key: value}, merge=True))

async def get_ticket(number):
    doc = await _run(lambda: db.collection("tickets").document(str(number)).get())
    if not doc.exists: return None
    d = doc.to_dict()
    return (number, d.get("user_id"), d.get("username"), d.get("phone"), d.get("status"))

async def reserve_tickets(numbers, user_id, username, phone):
    def _sync():
        batch = db.batch()
        for num in numbers:
            ref = db.collection("tickets").document(str(num))
            batch.set(ref, {"status": "reserved", "user_id": str(user_id), "username": str(username), "phone": str(phone), "created_at": datetime.now().isoformat()})
        batch.commit()
    await _run(_sync)

async def confirm_tickets(numbers, user_id, username, phone):
    def _sync():
        batch = db.batch()
        for num in numbers:
            ref = db.collection("tickets").document(str(num))
            batch.set(ref, {"status": "taken", "user_id": str(user_id), "username": str(username), "phone": str(phone), "created_at": datetime.now().isoformat()})
        batch.commit()
    await _run(_sync)

async def free_tickets(numbers):
    def _sync():
        batch = db.batch()
        for num in numbers: batch.delete(db.collection("tickets").document(str(num)))
        batch.commit()
    await _run(_sync)

async def lock_tickets_pending_payment(numbers, user_id, username):
    def _sync():
        batch = db.batch()
        now = datetime.now().isoformat()
        for num in numbers:
            ref = db.collection("tickets").document(str(num))
            batch.set(ref, {"status": "pending_payment", "user_id": str(user_id), "username": str(username), "locked_at": now})
        batch.commit()
    await _run(_sync)

async def release_expired_pending(max_age_seconds=300):
    def _sync():
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        docs = db.collection("tickets").where("status", "==", "pending_payment").stream()
        released = []
        batch = db.batch()
        for doc in docs:
            d = doc.to_dict()
            if datetime.fromisoformat(d["locked_at"]) <= cutoff:
                released.append((int(doc.id), d.get("user_id")))
                batch.delete(doc.reference)
        batch.commit()
        return released
    return await _run(_sync)

async def count_taken_tickets():
    docs = await _run(lambda: db.collection("tickets").where("status", "==", "taken").stream())
    return sum(1 for _ in docs)

async def get_user_tickets(user_id, status):
    docs = await _run(lambda: db.collection("tickets").where("user_id", "==", str(user_id)).where("status", "==", status).stream())
    return [(int(doc.id),) for doc in docs]

# --- PAYMENTS ---
async def add_payment(user_id, username, phone, numbers, file_id, method, full_name=""):
    def _sync():
        docs = db.collection("payments").stream()
        ids = [int(doc.id) for doc in docs]
        p_id = max(ids) + 1 if ids else 1
        db.collection("payments").document(str(p_id)).set({
            "user_id": str(user_id), "username": str(username), "full_name": str(full_name),
            "phone": str(phone), "numbers": ",".join(map(str, numbers)),
            "receipt_file_id": str(file_id), "payment_method": str(method),
            "status": "pending", "created_at": datetime.now().isoformat()
        })
        return p_id
    return await _run(_sync)

async def get_payment(payment_id):
    doc = await _run(lambda: db.collection("payments").document(str(payment_id)).get())
    if not doc.exists: return None
    d = doc.to_dict()
    return (payment_id, d.get("user_id"), d.get("username"), d.get("phone"), d.get("numbers"), d.get("receipt_file_id"), d.get("payment_method"), d.get("status"), d.get("full_name"))

async def get_pending_payments():
    docs = await _run(lambda: db.collection("payments").where("status", "==", "pending").stream())
    res = []
    for doc in docs:
        d = doc.to_dict()
        res.append((int(doc.id), d.get("user_id"), d.get("username"), d.get("phone"), d.get("numbers"), d.get("receipt_file_id"), d.get("payment_method"), d.get("status")))
    return sorted(res, key=lambda x: x[0])

async def update_payment_status(pid, status, admin_id):
    await _run(lambda: db.collection("payments").document(str(pid)).update({"status": status, "reviewed_by": str(admin_id), "reviewed_at": datetime.now().isoformat()}))

async def find_payment_by_number(number):
    docs = await _run(lambda: db.collection("payments").stream())
    for doc in docs:
        d = doc.to_dict()
        if str(number) in (d.get("numbers") or "").split(","):
            return (int(doc.id), d.get("user_id"), d.get("username"), d.get("phone"), d.get("numbers"), d.get("receipt_file_id"), d.get("payment_method"), d.get("status"), d.get("reviewed_at"))
    return None

async def get_all_users():
    docs = await _run(lambda: db.collection("payments").stream())
    uids = {doc.to_dict().get("user_id") for doc in docs if doc.to_dict().get("user_id")}
    return [(uid,) for uid in uids]

# --- META & REFERRAL ---
async def save_group_message_ids(chat_id, ids):
    await _run(lambda: db.collection("meta").document("group_messages").set({"chat_id": str(chat_id), "message_ids": ",".join(map(str, ids))}))

async def get_group_message_ids():
    doc = await _run(lambda: db.collection("meta").document("group_messages").get())
    if not doc.exists: return []
    d = doc.to_dict()
    return [(int(i), int(d["chat_id"])) for i in (d.get("message_ids") or "").split(",") if i]

async def clear_group_messages():
    await _run(lambda: db.collection("meta").document("group_messages").set({"chat_id":"", "message_ids":""}))

async def get_all_tickets_full(total):
    docs = await _run(lambda: db.collection("tickets").stream())
    res = {n: ("", "free") for n in range(1, total+1)}
    for doc in docs:
        num = int(doc.id)
        if 1 <= num <= total:
            d = doc.to_dict()
            res[num] = (d.get("phone") or "", d.get("status") or "free")
    return res

async def add_referral(ref_id, new_id):
    def _sync():
        if db.collection("referrals").document(str(new_id)).get().exists: return
        db.collection("referrals").document(str(new_id)).set({"referrer_id": str(ref_id), "at": datetime.now().isoformat()})
        c_ref = db.collection("referral_counts").document(str(ref_id))
        snap = c_ref.get()
        curr = snap.to_dict().get("count", 0) if snap.exists else 0
        c_ref.set({"count": curr + 1}, merge=True)
    await _run(_sync)

async def get_referral_count(uid):
    doc = await _run(lambda: db.collection("referral_counts").document(str(uid)).get())
    return doc.to_dict().get("count", 0) if doc.exists else 0

# --- SOLD-TICKET GROUP ANNOUNCEMENTS ---
# ለእያንዳንዱ የተሸጠ ቁጥር 1 መልክት ብቻ ግሩፕ ላይ ይላካል (duplicate guard)።
# ስብስቡ 10 ሲደርስ ሁሉንም አጥፍቶ ከ0 ይጀምራል።
async def has_sold_announcement(number):
    doc = await _run(lambda: db.collection("sold_announcements").document(str(number)).get())
    return doc.exists

async def add_sold_announcement(number, message_id, chat_id):
    await _run(lambda: db.collection("sold_announcements").document(str(number)).set({
        "message_id": message_id, "chat_id": chat_id, "created_at": datetime.now().isoformat()
    }))

async def get_sold_announcements():
    def _sync():
        docs = db.collection("sold_announcements").stream()
        res = []
        for doc in docs:
            d = doc.to_dict()
            res.append((doc.id, d.get("message_id"), d.get("chat_id"), d.get("created_at") or ""))
        return sorted(res, key=lambda x: x[3])
    return await _run(_sync)

async def clear_sold_announcements():
    def _sync():
        docs = db.collection("sold_announcements").stream()
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
    await _run(_sync)

async def reset_lottery():
    def _sync():
        for coll in ["tickets", "payments", "sold_announcements"]:
            for doc in db.collection(coll).stream(): doc.reference.delete()
        db.collection("meta").document("group_messages").set({"chat_id":"", "message_ids":""})
    await _run(_sync)
