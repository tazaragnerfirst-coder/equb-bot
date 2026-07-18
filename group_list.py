# ══════════════════════════════════════════
# group_list.py
# ግሩፕ ውስጥ የትኬት ዝርዝርን edit-in-place ማሳየት + "ተሽጧል" ማስታወቂያ (sliding window)።
# Per-chunk granular repair: የጠፋ/የተበላሸ chunk ብቻ በአዲስ ይተካል፣ ደህና ያሉት አይነኩም።
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
    """
    Per-chunk granular repair:
    - ነባር chunk-ች (msg_id አላቸው) ቅድሚያ edit ይደረግላቸዋል።
    - Edit ሲሳካ ወይም "not modified" ሲሆን endeded ናቸው ይባላል።
    - Edit "message to edit not found" / "chat not found" ካልሆነ ብቻ ያ specific
      chunk በአዲስ መልክት ይተካል (ሌሎቹ አይነኩም)።
    - Total ቢጨምር ተጨማሪ chunks አዲስ ይላካሉ።
    - Total ቢቀንስ የተረፉ (ከአዲሱ chunk ብዛት በላይ ያሉ) ነባር መልክቶች ይሰረዛሉ።
    - old_msgs ባዶ ከሆነ (የመጀመሪያ ጊዜ) ሁሉም chunks በአዲስ ይላካሉ።
    """
    old_msgs = await db.get_group_message_ids()
    ticket_map = await db.get_all_tickets_full(total)
    new_chunks = _build_chunks(ticket_map, total)

    final_msg_ids = []  # (msg_id, chat_id) per chunk position, in order
    repaired_count = 0
    edited_count = 0

    for idx, text in enumerate(new_chunks):
        if idx < len(old_msgs):
            msg_id, chat_id = old_msgs[idx]
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text)
                final_msg_ids.append((msg_id, chat_id))
                edited_count += 1
            except BadRequest as e:
                err = str(e).lower()
                if "not modified" in err:
                    # ይዘቱ ካልተቀየረ - እንደ ስኬታማ ይቆጠራል
                    final_msg_ids.append((msg_id, chat_id))
                    edited_count += 1
                elif "message to edit not found" in err or "chat not found" in err:
                    # ይሄ specific chunk ብቻ ጠፍቷል/ተደልጧል -> በአዲስ ይተካል
                    try:
                        new_msg = await bot.send_message(chat_id=GROUP_ID, text=text)
                        final_msg_ids.append((new_msg.message_id, GROUP_ID))
                        repaired_count += 1
                    except Exception as e2:
                        logger.error(f"Repair-send chunk {idx} error: {e2}")
                        final_msg_ids.append((msg_id, chat_id))  # fallback: keep old ref
                else:
                    logger.warning(f"Edit chunk error (msg_id={msg_id}): {e}")
                    final_msg_ids.append((msg_id, chat_id))
            except Exception as e:
                logger.warning(f"Edit chunk error (msg_id={msg_id}): {e}")
                final_msg_ids.append((msg_id, chat_id))
            await asyncio.sleep(0.4)
        else:
            # Total አድጎ አዲስ chunk ያስፈልጋል
            try:
                new_msg = await bot.send_message(chat_id=GROUP_ID, text=text)
                final_msg_ids.append((new_msg.message_id, GROUP_ID))
                await asyncio.sleep(0.8)
            except Exception as e:
                logger.error(f"New chunk send error (idx={idx}): {e}")

    # Total ቢቀንስ የተረፉ ነባር መልክቶች ይሰረዛሉ
    if len(old_msgs) > len(new_chunks):
        for msg_id, chat_id in old_msgs[len(new_chunks):]:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                logger.warning(f"Delete extra old group msg error: {e}")

    await db.save_group_message_ids(GROUP_ID, [mid for mid, _ in final_msg_ids])

    if repaired_count:
        logger.info(f"Group list: {edited_count} edited, {repaired_count} chunk(s) repaired (resent).")

    return len(final_msg_ids)


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
