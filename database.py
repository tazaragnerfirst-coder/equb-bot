import httpx
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

FIRESTORE_BASE = "https://firestore.googleapis.com/v1/projects/equb-c5f5f/databases/(default)/documents"

async def _get(path):
    url = f"{FIRESTORE_BASE}/{path}"
    async with httpx.AsyncClient() as c:
        r = await c.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None

async def _set(path, fields):
    url = f"{FIRESTORE_BASE}/{path}"
    payload = {"fields": fields}
    async with httpx.AsyncClient() as c:
        await c.patch(url, json=payload, timeout=10)

async def _delete(path):
    url = f"{FIRESTORE_BASE}/{path}"
    async with httpx.AsyncClient() as c:
        await c.delete(url, timeout=10)

async def _list(collection, page_size=1000):
    url = f"{FIRESTORE_BASE}/{collection}?pageSize={page_size}"
    async with httpx.AsyncClient() as c:
        r = await c.get(url, timeout=15)
        if r.status_code == 200:
            return r.json().get("documents", [])
        return []

async def _query(collection, field, op, value, value_type="stringValue"):
    url = f"{FIRESTORE_BASE}:runQuery"
    body = {
        "structuredQuery": {
            "from": [{"collectionId": collection}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": field},
                    "op": op,
                    "value": {value_type: value}
                }
            }
        }
    }
    async with httpx.AsyncClient() as c:
        r = await c.post(url, json=body, timeout=15)
        if r.status_code == 200:
            return [d["document"] for d in r.json() if "document" in d]
        return []

def _sv(v): return {"stringValue": str(v)}
def _iv(v): return {"integerValue": str(int(v))}
def _fv(v): return {"fields": v}

def _parse_field(doc, key):
    fields = doc.get("fields", {})
    f = fields.get(key, {})
    return f.get("stringValue") or f.get("integerValue") or f.get("booleanValue") or None

# ─── INIT ───
async def init_db():
    # defaults
    doc = await _get("settings/config")
    if not doc or not doc.get("fields"):
        await _set("settings/config", {
            "total_tickets": _iv(1000),
            "ticket_price": _iv(400),
            "prize_1": _sv("1ኛ ሽልማት"),
            "prize_2": _sv("2ኛ ሽልማት"),
            "prize_3": _sv("3ኛ ሽልማት"),
            "lottery_title": _sv("GETU DURESA - EQUB"),
            "draw_button_name": _sv("🎊 እጣ ቁረጥ"),
            "draw_message": _sv("🎊 እጣ ተቆርጧል!"),
        })

# ─── SETTINGS ───
async def get_setting(key):
    doc = await _get("settings/config")
    if not doc:
        return None
    return _parse_field(doc, key)

async def set_setting(key, value):
    doc = await _get("settings/config")
    fields = doc.get("fields", {}) if doc else {}
    if isinstance(value, int) or str(value).isdigit():
        fields[key] = _iv(value)
    else:
        fields[key] = _sv(value)
    await _set("settings/config", fields)

# ─── TICKETS ───
async def get_ticket(number):
    doc = await _get(f"tickets/{number}")
    if not doc or not doc.get("fields"):
        return None
    f = doc["fields"]
    return (
        number,
        _parse_field(doc, "user_id"),
        _parse_field(doc, "username"),
        _parse_field(doc, "phone"),
        _parse_field(doc, "status"),
    )

async def get_tickets_range(start, end):
    docs = await _list("tickets")
    result = []
    for doc in docs:
        name = doc.get("name", "")
        num = int(name.split("/")[-1])
        if start <= num <= end:
            result.append((
                num,
                _parse_field(doc, "user_id"),
                _parse_field(doc, "status"),
                _parse_field(doc, "phone"),
            ))
    return result

async def get_all_tickets_full(total):
    docs = await _list("tickets")
    result = {}
    for doc in docs:
        name = doc.get("name", "")
        num = int(name.split("/")[-1])
        if 1 <= num <= total:
            result[num] = (
                _parse_field(doc, "phone") or "",
                _parse_field(doc, "status") or "free",
            )
    return result

async def reserve_tickets(numbers, user_id, username, phone):
    for num in numbers:
        await _set(f"tickets/{num}", {
            "status": _sv("reserved"),
            "user_id": _sv(str(user_id)),
            "username": _sv(str(username)),
            "phone": _sv(str(phone)),
            "created_at": _sv(datetime.now().isoformat()),
        })

async def confirm_tickets(numbers, user_id, username, phone):
    for num in numbers:
        await _set(f"tickets/{num}", {
            "status": _sv("taken"),
            "user_id": _sv(str(user_id)),
            "username": _sv(str(username)),
            "phone": _sv(str(phone)),
            "created_at": _sv(datetime.now().isoformat()),
        })

async def free_tickets(numbers):
    for num in numbers:
        await _delete(f"tickets/{num}")

async def count_taken_tickets():
    docs = await _list("tickets")
    return sum(1 for d in docs if _parse_field(d, "status") == "taken")

async def count_pending_tickets():
    docs = await _list("tickets")
    return sum(1 for d in docs if _parse_field(d, "status") == "reserved")

async def count_tickets_today():
    docs = await _list("payments")
    today = date.today().isoformat()
    count = 0
    for doc in docs:
        if _parse_field(doc, "status") == "approved":
            reviewed = _parse_field(doc, "reviewed_at") or ""
            if reviewed.startswith(today):
                nums = _parse_field(doc, "numbers") or ""
                count += len(nums.split(",")) if nums else 0
    return count

async def get_user_tickets(user_id, status):
    docs = await _list("tickets")
    result = []
    for doc in docs:
        if _parse_field(doc, "user_id") == str(user_id) and _parse_field(doc, "status") == status:
            name = doc.get("name", "")
            num = int(name.split("/")[-1])
            result.append((num,))
    return result

# ─── PAYMENTS ───
async def _next_payment_id():
    docs = await _list("payments")
    if not docs:
        return 1
    ids = []
    for d in docs:
        name = d.get("name", "")
        try:
            ids.append(int(name.split("/")[-1]))
        except:
            pass
    return max(ids) + 1 if ids else 1

async def add_payment(user_id, username, phone, numbers, receipt_file_id, payment_method):
    p_id = await _next_payment_id()
    numbers_str = ",".join(map(str, numbers))
    await _set(f"payments/{p_id}", {
        "user_id": _sv(str(user_id)),
        "username": _sv(str(username)),
        "phone": _sv(str(phone)),
        "numbers": _sv(numbers_str),
        "receipt_file_id": _sv(str(receipt_file_id)),
        "payment_method": _sv(str(payment_method)),
        "status": _sv("pending"),
        "created_at": _sv(datetime.now().isoformat()),
        "reviewed_by": _sv(""),
        "reviewed_at": _sv(""),
    })
    return p_id

async def get_payment(payment_id):
    doc = await _get(f"payments/{payment_id}")
    if not doc or not doc.get("fields"):
        return None
    return (
        payment_id,
        _parse_field(doc, "user_id"),
        _parse_field(doc, "username"),
        _parse_field(doc, "phone"),
        _parse_field(doc, "numbers"),
        _parse_field(doc, "receipt_file_id"),
        _parse_field(doc, "payment_method"),
        _parse_field(doc, "status"),
        _parse_field(doc, "created_at"),
        _parse_field(doc, "reviewed_by"),
        _parse_field(doc, "reviewed_at"),
    )

async def get_pending_payments():
    docs = await _list("payments")
    result = []
    for doc in docs:
        if _parse_field(doc, "status") == "pending":
            name = doc.get("name", "")
            p_id = int(name.split("/")[-1])
            result.append((
                p_id,
                _parse_field(doc, "user_id"),
                _parse_field(doc, "username"),
                _parse_field(doc, "phone"),
                _parse_field(doc, "numbers"),
                _parse_field(doc, "receipt_file_id"),
                _parse_field(doc, "payment_method"),
                _parse_field(doc, "status"),
            ))
    return sorted(result, key=lambda x: x[0])

async def get_all_approved_payments():
    docs = await _list("payments")
    result = []
    for doc in docs:
        if _parse_field(doc, "status") == "approved":
            name = doc.get("name", "")
            p_id = int(name.split("/")[-1])
            result.append((
                p_id,
                _parse_field(doc, "username"),
                _parse_field(doc, "phone"),
                _parse_field(doc, "numbers"),
                _parse_field(doc, "receipt_file_id"),
                _parse_field(doc, "payment_method"),
                _parse_field(doc, "reviewed_at"),
            ))
    return sorted(result, key=lambda x: x[0], reverse=True)

async def update_payment_status(payment_id, status, reviewed_by):
    doc = await _get(f"payments/{payment_id}")
    if not doc:
        return
    fields = doc.get("fields", {})
    fields["status"] = _sv(status)
    fields["reviewed_by"] = _sv(str(reviewed_by))
    fields["reviewed_at"] = _sv(datetime.now().isoformat())
    await _set(f"payments/{payment_id}", fields)

async def find_payment_by_number(number):
    """ቁጥር ፈልግ — admin feature"""
    docs = await _list("payments")
    for doc in docs:
        nums = _parse_field(doc, "numbers") or ""
        if str(number) in nums.split(","):
            name = doc.get("name", "")
            p_id = int(name.split("/")[-1])
            return (
                p_id,
                _parse_field(doc, "user_id"),
                _parse_field(doc, "username"),
                _parse_field(doc, "phone"),
                _parse_field(doc, "numbers"),
                _parse_field(doc, "receipt_file_id"),
                _parse_field(doc, "payment_method"),
                _parse_field(doc, "status"),
                _parse_field(doc, "reviewed_at"),
            )
    return None

# ─── USERS ───
async def get_all_users():
    docs = await _list("payments")
    seen = set()
    result = []
    for doc in docs:
        uid = _parse_field(doc, "user_id")
        if uid and uid not in seen:
            seen.add(uid)
            result.append((uid,))
    return result

# ─── GROUP MESSAGES ───
async def save_group_message_ids(chat_id, message_ids):
    await _set("meta/group_messages", {
        "chat_id": _sv(str(chat_id)),
        "message_ids": _sv(",".join(map(str, message_ids))),
    })

async def get_group_message_ids():
    doc = await _get("meta/group_messages")
    if not doc or not doc.get("fields"):
        return []
    ids_str = _parse_field(doc, "message_ids") or ""
    chat_id = _parse_field(doc, "chat_id") or ""
    if not ids_str or not chat_id:
        return []
    return [(int(i), int(chat_id)) for i in ids_str.split(",") if i]

async def clear_group_messages():
    await _set("meta/group_messages", {
        "chat_id": _sv(""),
        "message_ids": _sv(""),
    })

# ─── RESET ───
async def reset_lottery():
    tickets = await _list("tickets")
    for doc in tickets:
        name = doc.get("name", "")
        num = name.split("/")[-1]
        await _delete(f"tickets/{num}")
    payments = await _list("payments")
    for doc in payments:
        name = doc.get("name", "")
        p_id = name.split("/")[-1]
        await _delete(f"payments/{p_id}")
    await clear_group_messages()