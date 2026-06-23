from datetime import datetime

from pyrogram import filters
from pyrogram.types import Message
from config import *
from ISTKHAR_MUSIC import app
from ISTKHAR_MUSIC.core.call import ISTKHAR
from ISTKHAR_MUSIC.utils import bot_sys_stats
from ISTKHAR_MUSIC.utils.decorators.language import language
from ISTKHAR_MUSIC.utils.inline import supp_markup
from config import BANNED_USERS, PING_VID_URL


@app.on_message(filters.command("ping", prefixes=["/"]) & ~BANNED_USERS)
@language
async def ping_com(client, message: Message, _):
    start = datetime.now()
    response = await message.reply_video(
        video=PING_VID_URL,
        caption=_["ping_1"].format(app.mention),
    )
    pytgping = await ISTKHAR.ping()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    resp = (datetime.now() - start).microseconds / 1000
    await response.edit_text(
        _["ping_2"].format(resp, app.mention, UP, RAM, CPU, DISK, pytgping),
        reply_markup=supp_markup(_),
    )
