# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#   GitHub : github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
#   Developer : @IAMIstkhar | Telegram
#   Module : Autoplay Feature Handler
# ═══════════════════════════════════════════════════════════

from ISTKHAR_MUSIC.core.mongo import mongodb

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

# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#   github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
# ═══════════════════════════════════════════════════════════
