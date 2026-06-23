# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#   GitHub : github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
#   Developer : @IAMIstkhar | Telegram
#   Module : Skip, Seek & Stream Control
# ═══════════════════════════════════════════════════════════

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from ISTKHAR_MUSIC import YouTube, app
from ISTKHAR_MUSIC.core.call import ISTKHAR
from ISTKHAR_MUSIC.misc import db
from ISTKHAR_MUSIC.utils.database import get_loop, group_assistant
from ISTKHAR_MUSIC.utils.autoplay_utils import is_autoplay_on
from ISTKHAR_MUSIC.utils.decorators import AdminRightsCheck
from ISTKHAR_MUSIC.utils.inline import close_markup, stream_markup
from ISTKHAR_MUSIC.utils.stream.autoclear import auto_clean
from ISTKHAR_MUSIC.utils.thumbnails import get_thumb
from config import BANNED_USERS


@app.on_message(
    filters.command(["skip", "cskip", "next", "cnext"], prefixes=["/", "!"]) & filters.group & ~BANNED_USERS
)
@AdminRightsCheck
async def skip(cli, message: Message, _, chat_id):
    check = db.get(chat_id)
    if not check:
        return await message.reply_text(_["queue_2"])
        
    loop = await get_loop(chat_id)
    if loop != 0:
        return await message.reply_text(_["admin_8"])

    popped = None

    if len(message.command) >= 2:
        state = message.text.split(None, 1)[1].strip()
        if state.isnumeric():
            state = int(state)
            count = len(check)
            if count > 2:
                count = int(count - 1)
                if 1 <= state <= count:
                    for x in range(state):
                        try:
                            popped = check.pop(0)
                            if popped:
                                await auto_clean(popped)
                        except:
                            return await message.reply_text(_["admin_12"])
                else:
                    return await message.reply_text(_["admin_11"].format(count))
            else:
                return await message.reply_text(_["admin_10"])
        else:
            return await message.reply_text(_["admin_9"])
    else:
        try:
            popped = check.pop(0)
            if popped:
                await auto_clean(popped)
        except:
            pass

    # 🟢 MASTER FIX: Re-inserting the popped item so `ISTKHAR.play()` can use it for Autoplay context!
    if popped:
        check.insert(0, popped)

    await message.reply_text(
        text=_["admin_6"].format(message.from_user.mention, message.chat.title),
        reply_markup=close_markup(_)
    )

    try:
        # Handing over the control directly to our Smart Play function
        assistant = await group_assistant(ISTKHAR, chat_id)
        await ISTKHAR.play(assistant, chat_id)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#    github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
# ═══════════════════════════════════════════════════════════
