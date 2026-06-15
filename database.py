import aiosqlite
import os

import os
DB_PATH = "data/equb.db"
os.makedirs("data", exist_ok=True)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                number INTEGER PRIMARY KEY,
                user_id INTEGER,
                username TEXT,
                phone TEXT,
                status TEXT DEFAULT 'free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                phone TEXT,
                numbers TEXT,
                receipt_file_id TEXT,
                payment_method TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                start_number INTEGER,
                end_number INTEGER
            )
        """)
        # Default settings
        defaults = {
            "total_tickets": "1000",
            "ticket_price": "400",
            "prize_1": "1ኛ ሽልማት",
            "prize_2": "2ኛ ሽልማት",
            "prize_3": "3ኛ ሽልማት",
            "lottery_active": "true",
            "lottery_title": "GETU DURESA - EQUB",
        }
        for key, value in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        await db.commit()

async def get_setting(key):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def set_setting(key, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        await db.commit()

async def get_ticket(number):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM tickets WHERE number=?", (number,)) as cur:
            return await cur.fetchone()

async def get_tickets_range(start, end):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT number, status FROM tickets WHERE number BETWEEN ? AND ?",
            (start, end)
        ) as cur:
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
                "INSERT OR REPLACE INTO tickets (number, user_id, username, phone, status) VALUES (?, ?, ?, ?, 'taken')",
                (num, user_id, username, phone)
            )
        await db.commit()

async def free_tickets(numbers):
    async with aiosqlite.connect(DB_PATH) as db:
        for num in numbers:
            await db.execute(
                "UPDATE tickets SET status='free', user_id=NULL, username=NULL, phone=NULL WHERE number=?",
                (num,)
            )
        await db.commit()

async def add_payment(user_id, username, phone, numbers, receipt_file_id, payment_method):
    async with aiosqlite.connect(DB_PATH) as db:
        numbers_str = ",".join(map(str, numbers))
        await db.execute(
            """INSERT INTO payments 
               (user_id, username, phone, numbers, receipt_file_id, payment_method, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (user_id, username, phone, numbers_str, receipt_file_id, payment_method)
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cur:
            row = await cur.fetchone()
            return row[0]

async def get_pending_payments():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM payments WHERE status='pending' ORDER BY created_at DESC"
        ) as cur:
            return await cur.fetchall()

async def get_payment(payment_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM payments WHERE id=?", (payment_id,)) as cur:
            return await cur.fetchone()

async def update_payment_status(payment_id, status, reviewed_by):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE payments SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP 
               WHERE id=?""",
            (status, reviewed_by, payment_id)
        )
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT user_id FROM payments"
        ) as cur:
            return await cur.fetchall()

async def count_taken_tickets():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM tickets WHERE status='taken'") as cur:
            row = await cur.fetchone()
            return row[0]

async def reset_lottery():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tickets")
        await db.execute("DELETE FROM payments")
        await db.execute("DELETE FROM group_messages")
        await db.commit()

async def save_group_message(message_id, start_num, end_num):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO group_messages (message_id, start_number, end_number) VALUES (?, ?, ?)",
            (message_id, start_num, end_num)
        )
        await db.commit()

async def get_group_messages():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM group_messages ORDER BY start_number") as cur:
            return await cur.fetchall()

async def get_user_tickets(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT number FROM tickets WHERE user_id=? AND status='taken'",
            (user_id,)
        ) as cur:
            return await cur.fetchall()
