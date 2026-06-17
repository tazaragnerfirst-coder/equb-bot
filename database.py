import aiosqlite
import os
from datetime import datetime

DB_PATH = "data/equb.db"
os.makedirs("data", exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS tickets (
            number INTEGER PRIMARY KEY, user_id INTEGER, username TEXT,
            phone TEXT, status TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            username TEXT, phone TEXT, numbers TEXT,
            receipt_file_id TEXT, payment_method TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER
        )""")
        defaults = {
            "total_tickets": "100", "ticket_price": "400",
            "prize_1": "1ኛ ሽልማት", "prize_2": "2ኛ ሽልማት", "prize_3": "3ኛ ሽልማት",
            "lottery_title": "GETU DURESA - EQUB",
            "last_group_msg_id": "0"
        }
        for key, value in defaults.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
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

async def get_all_tickets_status():
    async with aiosqlite.connect(DB_PATH) as db:
        # ሁሉንም ቁጥሮች ከነገዢው ስልክ ጋር ያወጣል
        async with db.execute("SELECT number, phone, username, status FROM tickets ORDER BY number") as cur:
            return await cur.fetchall()

async def reserve_tickets(numbers, user_id, username, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        for num in numbers:
            await db.execute(
                "INSERT OR REPLACE INTO tickets (number, user_id, username, phone, status) VALUES (?, ?, ?, ?, 'reserved')",
                (num, user_id, username, phone)
            )
        await db.commit()

async def confirm_tickets(numbers, user_id, username, phone):
    async with aiosqlite.connect(DB_PATH) as db:
        for num in numbers:
            await db.execute(
                "UPDATE tickets SET status='taken', user_id=?, username=?, phone=? WHERE number=?",
                (user_id, username, phone, num)
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

async def get_payment(payment_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM payments WHERE id=?", (payment_id,)) as cur:
            return await cur.fetchone()

async def update_payment_status(payment_id, status, reviewed_by):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status=?, reviewed_by=? WHERE id=?", (status, reviewed_by, payment_id)
        )
        await db.commit()

async def get_pending_payments():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM payments WHERE status='pending'") as cur:
            return await cur.fetchall()
