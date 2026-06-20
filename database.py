import aiosqlite
import os
from datetime import date

DB_PATH = "data/equb.db"
os.makedirs("data", exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS tickets (
            number INTEGER PRIMARY KEY, user_id INTEGER, username TEXT,
            phone TEXT, status TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_to_group INTEGER DEFAULT 0
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            username TEXT, phone TEXT, numbers TEXT,
            receipt_file_id TEXT, payment_method TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER, reviewed_at TIMESTAMP
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS group_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            chat_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        defaults = {
            "total_tickets": "1000", "ticket_price": "400",
            "prize_1": "1ኛ ሽልማት", "prize_2": "2ኛ ሽልማት", "prize_3": "3ኛ ሽልማት",
            "lottery_title": "GETU DURESA - EQUB",
            "draw_button_name": "🎊 እጣ ቁረጥ", "draw_message": "🎊 እጣ ተቆርጧል!",
        }
        for key, value in defaults.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
        for col in ["sent_to_group"]:
            try:
                await db.execute(f"ALTER TABLE tickets ADD COLUMN {col} INTEGER DEFAULT 0")
            except:
                pass
        await db.commit()

async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_ticket(number):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM tickets WHERE number=?", (number,)) as cur:
            return await cur.fetchone()

async def get_tickets_range(start, end):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT number, user_id, status, phone FROM tickets WHERE number BETWEEN ? AND ?", (start, end)
        ) as cur:
            return await cur.fetchall()

async def get_all_tickets_full(total):
    """ሁሉንም ቁጥሮች ከ1 እስከ total ያወጣል (phone, status, username)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT number, phone, status, username FROM tickets WHERE number BETWEEN 1 AND ?", (total,)
        ) as cur:
            rows = await cur.fetchall()
            return {r[0]: (r[1], r[2], r[3]) for r in rows}  # number: (phone, status, username)

async def reserve_tickets(numbers, user_id, username, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        for num in numbers:
            await db.execute(
                "INSERT OR REPLACE INTO tickets (number, user_id, username, phone, status, sent_to_group) VALUES (?, ?, ?, ?, 'reserved', 0)",
                (num, user_id, username, phone)
            )
        await db.commit()

async def confirm_tickets(numbers, user_id, username, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        for num in numbers:
            await db.execute(
                "INSERT OR REPLACE INTO tickets (number, user_id, username, phone, status, sent_to_group) VALUES (?, ?, ?, ?, 'taken', 0)",
                (num, user_id, username, phone)
            )
        await db.commit()

async def free_tickets(numbers):
    async with aiosqlite.connect(DB_PATH) as db:
        for num in numbers:
            await db.execute("DELETE FROM tickets WHERE number=?", (num,))
        await db.commit()

async def add_payment(user_id, username, phone, numbers, receipt_file_id, payment_method):
    async with aiosqlite.connect(DB_PATH) as db:
        numbers_str = ",".join(map(str, numbers))
        await db.execute(
            "INSERT INTO payments (user_id, username, phone, numbers, receipt_file_id, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, phone, numbers_str, receipt_file_id, payment_method)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            return (await cur.fetchone())[0]

async def get_pending_payments():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM payments WHERE status='pending' ORDER BY created_at DESC") as cur:
            return await cur.fetchall()

async def get_payment(payment_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM payments WHERE id=?", (payment_id,)) as cur:
            return await cur.fetchone()

async def get_payment_by_number(number):
    """አንድ ቁጥር የትኛው payment ጋር እንደተያያዘ ይፍልጋል (search feature)"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM payments WHERE ','||numbers||',' LIKE ? ORDER BY created_at DESC LIMIT 1",
            (f"%,{number},%",)
        ) as cur:
            return await cur.fetchone()

async def get_all_approved_payments():
    """አድሚን ሁሉንም approved ክፍያዎች ያይ"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, username, phone, numbers, receipt_file_id, payment_method, reviewed_at FROM payments WHERE status='approved' ORDER BY reviewed_at DESC"
        ) as cur:
            return await cur.fetchall()

async def update_payment_status(payment_id, status, reviewed_by):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, reviewed_by, payment_id)
        )
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT DISTINCT user_id FROM payments") as cur:
            return await cur.fetchall()

async def count_taken_tickets():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM tickets WHERE status='taken'") as cur:
            return (await cur.fetchone())[0]

async def count_pending_tickets():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM tickets WHERE status='reserved'") as cur:
            return (await cur.fetchone())[0]

async def count_tickets_today():
    async with aiosqlite.connect(DB_PATH) as db:
        today = date.today().isoformat()
        async with db.execute(
            "SELECT COUNT(*) FROM payments WHERE status='approved' AND DATE(reviewed_at)=?", (today,)
        ) as cur:
            return (await cur.fetchone())[0]

async def count_user_tickets_today(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        today = date.today().isoformat()
        async with db.execute(
            "SELECT numbers FROM payments WHERE user_id=? AND DATE(created_at)=? AND status IN ('pending','approved')",
            (user_id, today)
        ) as cur2:
            rows = await cur2.fetchall()
            return sum(len(r[0].split(",")) for r in rows)

async def reset_lottery():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tickets")
        await db.execute("DELETE FROM payments")
        await db.execute("DELETE FROM group_messages")
        await db.commit()

async def get_user_tickets(user_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT number FROM tickets WHERE user_id=? AND status=?", (user_id, status)
        ) as cur:
            return await cur.fetchall()

async def get_user_lang_from_payment(user_id):
    """ተጠቃሚው lang ምን እንደተመረጠ ለማግኘት - SQLite ላይ lang አይቀመጥም
       ስለዚህ ይህ function ምንም ጠቃሚ ነገር አይመልስም፤ bot.py ላይ ctx.user_data lang ብቻ ይታመንበት"""
    return None

async def get_newly_confirmed_tickets():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT number, phone FROM tickets WHERE status='taken' AND sent_to_group=0 ORDER BY number"
        ) as cur:
            return await cur.fetchall()

async def mark_tickets_sent():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tickets SET sent_to_group=1 WHERE status='taken' AND sent_to_group=0")
        await db.commit()

# ── Group message tracking ──
async def save_group_message_ids(chat_id, message_ids):
    """አዲስ group message IDs ያስቀምጣል"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM group_messages")
        for msg_id in message_ids:
            await db.execute(
                "INSERT INTO group_messages (message_id, chat_id) VALUES (?, ?)",
                (msg_id, chat_id)
            )
        await db.commit()

async def get_group_message_ids():
    """ቀደም ብሎ የተላኩ group message IDs ያወጣል"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT message_id, chat_id FROM group_messages") as cur:
            return await cur.fetchall()

async def clear_group_messages():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM group_messages")
        await db.commit()
