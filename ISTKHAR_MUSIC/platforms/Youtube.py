# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#   GitHub : github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
#   Developer : @IAMIstkhar | Telegram
#   Module : YouTube Search, Download & Streaming
# ═══════════════════════════════════════════════════════════

import asyncio
import contextlib
import json
import os
import re
import time
import aiofiles
import aiohttp
import shutil
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch

from ISTKHAR_MUSIC.utils.cookie_handler import COOKIE_PATH
from ISTKHAR_MUSIC.utils.database import is_on_off
from ISTKHAR_MUSIC.utils.downloader import download_audio_concurrent, yt_dlp_download
from ISTKHAR_MUSIC.utils.errors import capture_internal_err
from ISTKHAR_MUSIC.utils.formatters import time_to_seconds
from ISTKHAR_MUSIC.utils.tuning import (
    YTDLP_TIMEOUT,
    YOUTUBE_META_MAX,
    YOUTUBE_META_TTL,
)
from ISTKHAR_MUSIC import LOGGER

_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()

# ============ API CONFIGURATION ============
# Mapping all 4 Fast APIs for Concurrent Racing
APIS = [
    ("ShrutiAPI", "https://api.shrutibots.site/download", "ShrutiBotsL0zQEKsazSrYS2LWsIQW"),
    ("XbitAPI", f"{os.getenv('YTPROXY_URL', 'https://tgapi.xbitcode.com')}/download", os.getenv("YT_API_KEY", "xbit_B4TNnBAoe6uoSM7NLFz-dk6X7GibJ6Bh")),
    ("WorkerAPI", f"{os.getenv('WORKER_FALLBACK_API_URL', 'https://youtubenewapi.skybotsdeveloper.workers.dev')}/download", os.getenv("WORKER_FALLBACK_API_KEY", "itsmesid")),
    ("InflexAPI", f"{os.getenv('INFLEX_API_URL', 'https://teaminflex.xyz')}/download", os.getenv("INFLEX_API_KEY", "INFLEX40920628D"))
]

# ============ RATE LIMITING ============
_request_timestamps = []
_RATE_LIMIT_WINDOW = 60
_MAX_REQUESTS_PER_WINDOW = 10
_rate_limit_lock = asyncio.Lock()

async def _check_rate_limit_async():
    global _request_timestamps
    async with _rate_limit_lock:
        now = time.time()
        _request_timestamps = [ts for ts in _request_timestamps if now - ts < _RATE_LIMIT_WINDOW]
        if len(_request_timestamps) >= _MAX_REQUESTS_PER_WINDOW:
            sleep_time = _RATE_LIMIT_WINDOW - (now - _request_timestamps[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            _request_timestamps = []
        _request_timestamps.append(time.time())

# ============ HTTP SESSION ============
_yt_session: aiohttp.ClientSession = None
_yt_session_lock = asyncio.Lock()

async def _get_yt_session() -> aiohttp.ClientSession:
    global _yt_session
    if _yt_session and not _yt_session.closed:
        return _yt_session
    async with _yt_session_lock:
        if _yt_session and not _yt_session.closed:
            return _yt_session
        connector = aiohttp.TCPConnector(limit=32, ttl_dns_cache=300, enable_cleanup_closed=True)
        timeout = aiohttp.ClientTimeout(total=300, sock_connect=10, sock_read=60)
        _yt_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return _yt_session

def _cookiefile_path() -> Optional[str]:
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None

def _cookies_args() -> List[str]:
    p = _cookiefile_path()
    return ["--cookies", p] if p else []

async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"

# ============ ⚡ CONCURRENT API RACING ============
async def single_api_download(api_name: str, req_url: str, params: dict, final_path: str) -> str:
    """Strict Anti-Hang & Corrupt File Guard."""
    temp_path = f"{final_path}_{api_name}.tmp"
    strict_timeout = aiohttp.ClientTimeout(total=120, connect=3, sock_read=5)
    
    try:
        session = await _get_yt_session()
        async with session.get(req_url, params=params, timeout=strict_timeout) as resp:
            if resp.status == 200:
                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        await f.write(chunk)
                
                # 🛡️ FIX FOR SILENT ASSISTANT: Ensure file is at least 50KB (Not a fake HTML error)
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 50000:
                    if not os.path.exists(final_path):
                        os.rename(temp_path, final_path)
                        LOGGER("ISTKHAR_MUSIC.platforms.Youtube").info(f"⚡ FASTEST API WON: {api_name} downloaded the file!")
                        return final_path
    except Exception:
        pass
    finally:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
    return None

async def race_all_apis(video_id: str, download_type: str) -> str:
    """Fires all 4 APIs concurrently."""
    os.makedirs("downloads", exist_ok=True)
    ext = "mp4" if download_type == "video" else "mp3"
    file_path = os.path.join("downloads", f"{video_id}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    tasks = []
    for api_name, url, key in APIS:
        if url and key:
            tasks.append(asyncio.create_task(single_api_download(
                api_name, url, {"url": video_id, "type": download_type, "api_key": key}, file_path
            )))

    if not tasks:
        return None

    for completed_task in asyncio.as_completed(tasks):
        result = await completed_task
        if result:
            for t in tasks:
                if not t.done():
                    t.cancel()
            return result

    return None

# ============ YT-DLP FALLBACK ============
async def download_video_ytdlp(link: str) -> str:
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    file_path = os.path.join("downloads", f"{video_id}.mp4")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    await _check_rate_limit_async()
    try:
        ytdlp_opts = ["yt-dlp", *(_cookies_args()), "--no-warnings", "--geo-bypass", "--force-ipv4", "-f", "best[height<=?720][width<=?1280]/best", "-o", file_path, link]
        await _exec_proc(*ytdlp_opts)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            return file_path
    except Exception:
        pass
    return None

async def download_audio_ytdlp(link: str) -> str:
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    file_path = os.path.join("downloads", f"{video_id}.webm")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    await _check_rate_limit_async()
    try:
        ytdlp_opts = ["yt-dlp", *(_cookies_args()), "--no-warnings", "--geo-bypass", "--force-ipv4", "-f", "bestaudio[ext=webm]/bestaudio", "--extract-audio", "--audio-format", "webm", "-o", file_path, link]
        await _exec_proc(*ytdlp_opts)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
            return file_path
    except Exception:
        pass
    return None

# ============ YOUTUBE API CLASS ============
@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()
    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()
    try:
        data = await VideosSearch(query, limit=1).next()
        result = data.get("result", [])
    except Exception:
        result = []
    if result:
        async with _cache_lock:
            _cache[key] = (now, result)
    return result

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    url = text[ent.offset : ent.offset + ent.length]
                    if self._url_pattern.search(url): return url
                if ent.type == MessageEntityType.TEXT_LINK:
                    url = ent.url
                    if self._url_pattern.search(url): return url
        return None

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not q.startswith("http"):
            res = await cached_youtube_search(q)
            return res[0] if res else None
        data = await VideosSearch(q, limit=1).next()
        result = data.get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info: raise ValueError("Video not found")
        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if info:
            thumb = info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")
            return thumb.split("?")[0] if thumb else ""
        return ""

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        video_id = link.split('v=')[-1].split('&')[0]
        
        # 1. Race APIs
        api_result = await race_all_apis(video_id, "video")
        if api_result: return (1, api_result)
        
        # 2. YT-DLP fallback
        ytdlp_result = await download_video_ytdlp(link)
        if ytdlp_result: return (1, ytdlp_result)
        
        return (0, "Video download failed")

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        try:
            info = await self._fetch_video_info(self._prepare_link(link, videoid))
            if not info: raise ValueError("Track not found")
        except Exception:
            await _check_rate_limit_async()
            stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", self._prepare_link(link, videoid))
            info = json.loads(stdout.decode())
        
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        _dur = info.get("duration")
        if isinstance(_dur, str) and _dur: duration_min = _dur
        elif isinstance(_dur, (int, float)) and _dur > 0:
            _secs = int(_dur)
            duration_min = f"{_secs // 60}:{_secs % 60:02d}"
        else: duration_min = None
        
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", self._prepare_link(link, videoid)),
            "vidid": info.get("id", ""),
            "duration_min": duration_min,
            "thumb": thumb,
        }
        return details, info.get("id", "")

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)
        video_id = link.split('v=')[-1].split('&')[0]

        if songvideo or video:
            # Video Download Logic
            api_result = await race_all_apis(video_id, "video")
            if api_result: return api_result, True
            
            yt_result = await download_video_ytdlp(link)
            if yt_result: return yt_result, True
            
            return None, None
        else:
            # Audio Download Logic
            api_result = await race_all_apis(video_id, "audio")
            # 🛡️ FIX FOR SILENT ASSISTANT: We simply return the actual file path. 
            # PyTgCalls can play BOTH .mp3 and .webm perfectly. No corrupt renaming!
            if api_result: return api_result, True
            
            yt_result = await download_audio_ytdlp(link)
            if yt_result: return yt_result, True

            return None, None

YouTube = YouTubeAPI()

# ═══════════════════════════════════════════════════════════
#        😎𝐈sᴛᴋʜᴀʀ 𝐌ᴜsɪᴄ  😎
#    github.com/TEAM-ISTKHAR/ISTKHAR_MUSIC
# ═══════════════════════════════════════════════════════════
