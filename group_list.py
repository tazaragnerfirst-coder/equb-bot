# ══════════════════════════════════════════
# group_list.py
# ግሩፕ ውስጥ የትኬት ዝርዝርን edit-in-place ማሳየት + "ተሽጧል" ማስታወቂያ (sliding window)።
# ══════════════════════════════════════════
import asyncio
import logging

from telegram.error import BadRequest

import database as db
from config import GROUP_ID
from translations import T

logger = logging.getLogger(__name__)

_group_update_lock = asyncio.Lock()
_group_update_pending = False


def _build_chunks(ticket_map, total, chunk_size=150):
    chunks = []
    for chunk_start in range(1, total + 1, chunk_size):
        chunk_end = min(chunk_start + chunk_size - 1, total)
        lines = []
        for n in range(chunk_start, chunk_end + 1):
            info = ticket_map.get(n)
            if info and info[1] == "taken":
                from helpers import mask_phone
                lines.append(f"{n} 👉 {mask_phone(info[0])} ✅")
            else:
                lines.append(f"{n} 👉")
        chunks.append("\n".join(lines))
    return chunks


async def send_full_list_to_group(bot, total):
    old_msgs = await db.get_group_message_ids()
    ticket_map = await db.get_all_tickets_full(total)
    new_chunks = _build_chunks(ticket_map, total)

    if old_msgs and len(old_msgs) == len(new_chunks):
        edited_ids = []
        is_any_message_missing = False

        for (msg_id, chat_id), text in zip(old_msgs, new_chunks):
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
                edited_ids.append(msg_id)
            except BadRequest as e:
                if "message to edit not found" in str(e).lower() or "chat not found" in str(e).lower():
                    is_any_message_missing = True
                    break
                elif "not modified" not in str(e).lower():
                    logger.warning(f"Edit chunk error (msg_id={msg_id}): {e}")
            except Exception as e:
                logger.warning(f"Edit chunk error (msg_id={msg_id}): {e}")
            await asyncio.sleep(0.4)

        if not is_any_message_missing and len(edited_ids) == len(new_chunks):
            return len(edited_ids)

    for msg_id, chat_id in old_msgs:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Delete old group msg error: {e}")
    await db.clear_group_messages()

    new_msg_ids = []
    for text in new_chunks:
        try:
            msg = await bot.send_message(chat_id=GROUP_ID, text=text)
            new_msg_ids.append(msg.message_id)
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Chunk send error: {e}")

    await db.save_group_message_ids(GROUP_ID, new_msg_ids)
    return len(new_msg_ids)


async def schedule_group_list_update(bot, total, min_interval=12):
    global _group_update_pending
    async with _group_update_lock:
        if _group_update_pending:
            return
        _group_update_pending = True

    async def _runner():
        global _group_update_pending
        try:
            await asyncio.sleep(min_interval)
            await send_full_list_to_group(bot, total)
        except Exception as e:
            logger.error(f"schedule_group_list_update error: {e}")
        finally:
            async with _group_update_lock:
                _group_update_pending = False

    asyncio.create_task(_runner())


# ══════════════════════════════════════════
# GROUP "SOLD" ANNOUNCEMENTS — sliding window of max 10
# ለእያንዳንዱ አዲስ የተሸጠ ቁጥር 1 መልክት ብቻ ግሩፕ ላይ ይላካል (duplicate guard)።
# ከ10 ካለፈ፣ ሁሉንም ከማጥፋት ይልቅ በጣም አሮጌውን 1 ብቻ አጥፍቶ አዲሱን ይተካል (ቋሚ sliding window)።
# ══════════════════════════════════════════
async def announce_sold_numbers(bot, numbers):
    for num in numbers:
        try:
            if await db.has_sold_announcement(num):
                continue
            msg = await bot.send_message(
                chat_id=GROUP_ID,
                text=T["am"]["sold_announce"].format(num=num),
                parse_mode="Markdown"
            )
            await db.add_sold_announcement(num, msg.message_id, GROUP_ID)

            all_announcements = await db.get_sold_announcements()
            if len(all_announcements) > 10:
                oldest_num, oldest_mid, oldest_cid, _ = all_announcements[0]
                try:
                    await bot.delete_message(chat_id=oldest_cid, message_id=oldest_mid)
                except Exception as e:
                    logger.warning(f"Delete oldest sold announce error: {e}")
                await db.remove_sold_announcement(oldest_num)
        except Exception as e:
            logger.error(f"Sold announce error num={num}: {e}")
        await asyncio.sleep(0.3)
