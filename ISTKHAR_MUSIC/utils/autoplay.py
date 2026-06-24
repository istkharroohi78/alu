# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#   Module : Autoplay Feature Handler (Updated)
# ═══════════════════════════════════════════════════════════

from ISTKHAR_MUSIC.core.mongo import mongodb
from ISTKHAR_MUSIC.core.call import ISTKHAR

_autoplay_db = mongodb.autoplay

async def is_autoplay_on(chat_id: int) -> bool:
    data = await _autoplay_db.find_one({"chat_id": chat_id})
    return bool(data.get("status", False)) if data else False

async def toggle_autoplay(chat_id: int) -> bool:
    data = await _autoplay_db.find_one({"chat_id": chat_id})
    if not data:
        await _autoplay_db.insert_one({"chat_id": chat_id, "status": True})
        return True
    new_status = not bool(data.get("status", False))
    await _autoplay_db.update_one(
        {"chat_id": chat_id},
        {"$set": {"status": new_status}},
    )
    return new_status


async def auto_play_next(chat_id, user_id, last_title, last_vidid, is_video):
    try:
        
        await ISTKHAR.skip_stream(chat_id, user_id, last_title, last_vidid, is_video)
        return True
    except Exception:
        return False
        
