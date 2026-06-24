# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#   GitHub : github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
#   Developer : @IAMIstkhar | Telegram
#   Module : MongoDB Database Connection
# ═══════════════════════════════════════════════════════════

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI
from ..logging import LOGGER

LOGGER(__name__).info("Connecting to your Mongo Database...")

try:
    _mongo_async_ = AsyncIOMotorClient(MONGO_DB_URI, serverSelectionTimeoutMS=5000)
    mongodb = _mongo_async_.Anon
    LOGGER(__name__).info("Connected to your Mongo Database.")
except Exception as e:
    LOGGER(__name__).error(f"Failed to connect to your Mongo Database: {e}")
    exit()

# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#   github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
# ═══════════════════════════════════════════════════════════
