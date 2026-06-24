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
import random
from typing import Dict, List, Optional, Tuple, Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch

from ISTKHAR_MUSIC.utils.cookie_handler import COOKIE_PATH
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

# ============ 🚀 ULTRA FAST API CONFIGURATION ============
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

# ============ HTTP SESSION (Optimized for Speed) ============
_yt_session: aiohttp.ClientSession = None
_yt_session_lock = asyncio.Lock()

async def _get_yt_session() -> aiohttp.ClientSession:
    global _yt_session
    if _yt_session and not _yt_session.closed:
        return _yt_session
    async with _yt_session_lock:
        if _yt_session and not _yt_session.closed:
            return _yt_session
        
        # Connection Pool limit badha di taaki multiple APIs ek sath smoothly connect ho sakein
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, enable_cleanup_closed=True, force_close=False)
        timeout = aiohttp.ClientTimeout(total=120, sock_connect=5)
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

# ============ ⚡ SAFE CONCURRENT API RACING ENGINE ============
async def single_api_download(api_name: str, req_url: str, params: dict, final_path: str) -> str:
    temp_path = f"{final_path}_{api_name}.tmp"
    try:
        session = await _get_yt_session()
        async with session.get(req_url, params=params) as resp:
            if resp.status == 200:
                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        await f.write(chunk)
                
                # Check for fake HTML pages, file must be valid (>50KB)
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 50000:
                    if not os.path.exists(final_path):
                        os.rename(temp_path, final_path)
                        LOGGER("ISTKHAR_MUSIC.platforms.Youtube").info(f"⚡ FASTEST API WON: {api_name} safely downloaded the file!")
                        return final_path
                        
    except asyncio.CancelledError:
        # 🟢 SAFE BACKGROUND STOP: Agar yeh API har gayi, toh iski temp file delete kar do
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
        raise # Task ko properly cancel hone do
    except Exception:
        pass
    finally:
        # Safety clean-up agar kuch error aaya ho
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
            
    return None

async def race_all_apis(video_id: str, download_type: str) -> str:
    os.makedirs("downloads", exist_ok=True)
    ext = "mp4" if download_type == "video" else "webm"
    file_path = os.path.join("downloads", f"{video_id}.{ext}")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 50000:
        return file_path

    tasks = [
        asyncio.create_task(single_api_download(name, url, {"url": video_id, "type": download_type, "api_key": key}, file_path))
        for name, url, key in APIS if url and key
    ]

    if not tasks:
        return None

    # 🟢 SMART RACE: Jab tak pehla successful file nahi milta, tab tak bot wait karega. 
    # Milte hi, baaki sab ko gently background mein stop kar dega.
    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
            if result:
                # 🛑 Safely Stop remaining APIs in the background
                for t in tasks:
                    if not t.done():
                        t.cancel()
                return result
        except Exception:
            continue

    return None

# ============ YT-DLP FALLBACK (LAST RESORT) ============
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
        link = self._prepare_link(link, videoid)
        try:
            results = VideosSearch(link, limit=1)
            response = await results.next()
            if response and response.get("result"):
                res = response["result"][0]
                title = res.get("title", "Unknown Title")
                dur_min = res.get("duration", "0:00")
                dur_sec = int(time_to_seconds(dur_min)) if dur_min else 0
                thumb = res.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
                return title, dur_min, dur_sec, thumb, res.get("id", "")
        except Exception:
            pass

        try:
            ydl_opts = {"quiet": True, "extract_flat": True, "noplaylist": True, "cookiefile": "cookies.txt"}
            def extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: return ydl.extract_info(link, download=False)
            info = await asyncio.get_event_loop().run_in_executor(None, extract)
            
            if info:
                if "entries" in info and len(info["entries"]) > 0: info = info["entries"][0]
                vidid = info.get("id", "")
                dur_sec = int(info.get("duration", 0) or 0)
                m, s = divmod(dur_sec, 60)
                h, m = divmod(m, 60)
                dur_min = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                return info.get("title", "Unknown"), dur_min, dur_sec, f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg", vidid
        except Exception:
            pass
        raise ValueError("Failed to fetch details")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        t, _, _, _, _ = await self.details(link, videoid)
        return t

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        _, d, _, _, _ = await self.details(link, videoid)
        return d

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        _, _, _, thumb, _ = await self.details(link, videoid)
        return thumb

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        video_id = link.split('v=')[-1].split('&')[0]
        
        api_result = await race_all_apis(video_id, "video")
        if api_result: return (1, api_result)
        
        ytdlp_result = await download_video_ytdlp(link)
        if ytdlp_result: return (1, ytdlp_result)
        
        return (0, "Video download failed")

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        await _check_rate_limit_async()
        playlist = await shell_cmd(f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}")
        try:
            items = [key for key in playlist.split("\n") if key]
        except:
            items = []
        return items

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        link = self._prepare_link(link, videoid)
        
        try:
            results = VideosSearch(link, limit=1)
            response = await results.next()
            if response and response.get("result"):
                res = response["result"][0]
                details = {
                    "title": res.get("title", "Unknown Title"),
                    "link": res.get("link", link),
                    "vidid": res.get("id", ""),
                    "duration_min": res.get("duration", "0:00"),
                    "thumb": res.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
                }
                return details, res.get("id", "")
        except Exception:
            pass

        try:
            ydl_opts = {"quiet": True, "extract_flat": True, "noplaylist": True, "cookiefile": "cookies.txt"}
            def extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl: return ydl.extract_info(link, download=False)
            info = await asyncio.get_event_loop().run_in_executor(None, extract)
            
            if info:
                if "entries" in info and len(info["entries"]) > 0: info = info["entries"][0]
                vidid = info.get("id", "")
                dur_sec = int(info.get("duration", 0) or 0)
                m, s = divmod(dur_sec, 60)
                h, m = divmod(m, 60)
                duration_min = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                
                details = {
                    "title": info.get("title", "Unknown Title"),
                    "link": f"https://www.youtube.com/watch?v={vidid}",
                    "vidid": vidid,
                    "duration_min": duration_min,
                    "thumb": f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg",
                }
                return details, vidid
        except Exception as e:
            LOGGER("ISTKHAR_MUSIC").error(f"yt-dlp fallback failed: {e}")
            
        return None, None

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()
        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        await _check_rate_limit_async()
        opts = {"quiet": True}
        cf = _cookiefile_path()
        if cf: opts["cookiefile"] = cf
        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower(): continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")): continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")): continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size: continue
                    out.append({
                        "format": fmt["format"],
                        "filesize": size,
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt["format_note"],
                        "yturl": link,
                    })
        except Exception:
            pass

        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX: _formats_cache.clear()
            _formats_cache[key] = (now, out, link)

        return out, link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
        r = results[query_type]
        return (r.get("title", ""), r.get("duration"), r.get("thumbnails", [{}])[0].get("url", "").split("?")[0], r.get("id", ""))

    @capture_internal_err
    async def download(
        self, link: str, mystic, *, video: Union[bool, str, None] = None, videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None, songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None, title: Union[bool, str, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)
        video_id = link.split('v=')[-1].split('&')[0]

        if songvideo or video:
            api_result = await race_all_apis(video_id, "video")
            if api_result: return api_result, True
            yt_result = await download_video_ytdlp(link)
            if yt_result: return yt_result, True
            return None, None
        else:
            api_result = await race_all_apis(video_id, "audio")
            if api_result: return api_result, True
            yt_result = await download_audio_ytdlp(link)
            if yt_result: return yt_result, True
            return None, None

    @capture_internal_err
    async def autoplay(self, last_vidid: str, title: str, max_duration: int = None):
        try:
            search_query = f"{title} official audio"
            valid_choices = []
            
            try:
                search = VideosSearch(search_query, limit=15)
                result = await search.next()
                if result and result.get("result"):
                    for res in result["result"]:
                        vidid = str(res.get("id") or "")
                        if not vidid or vidid == "None" or vidid == last_vidid: continue
                            
                        dur_str = str(res.get("duration", "0:00"))
                        dur_sec = 0
                        if dur_str and ":" in dur_str:
                            parts = dur_str.split(":")
                            try:
                                if len(parts) == 2: dur_sec = int(parts[0]) * 60 + int(parts[1])
                                elif len(parts) == 3: dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                            except ValueError: pass
                                
                        if dur_sec < 30: continue
                        if max_duration and dur_sec > max_duration: continue
                            
                        valid_choices.append({
                            "vidid": vidid,
                            "title": str(res.get("title", "Unknown Title")).title(),
                            "duration_min": dur_str,
                            "duration_sec": dur_sec
                        })
            except Exception: pass 

            if not valid_choices:
                ytdl_opts = {"quiet": True, "extract_flat": True, "noplaylist": True, "cookiefile": "cookies.txt"} 
                
                def extract():
                    with yt_dlp.YoutubeDL(ytdl_opts) as ydl: return ydl.extract_info(f"ytsearch10:{search_query}", download=False)
                r = await asyncio.get_event_loop().run_in_executor(None, extract)
                
                if r and "entries" in r:
                    for entry in r["entries"]:
                        vidid = entry.get("id")
                        if not vidid or vidid == last_vidid: continue
                        
                        raw_dur = entry.get("duration", 0)
                        try: dur_sec = int(float(raw_dur)) if raw_dur else 0
                        except (ValueError, TypeError): dur_sec = 0
                            
                        if not dur_sec or dur_sec < 30: continue
                        if max_duration and dur_sec > max_duration: continue
                            
                        m, s = divmod(dur_sec, 60)
                        h, m = divmod(m, 60)
                        dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                        
                        valid_choices.append({
                            "vidid": vidid,
                            "title": str(entry.get("title", "Unknown Title")).title(),
                            "duration_min": dur_str,
                            "duration_sec": dur_sec
                        })

            if valid_choices: 
                pool_size = min(len(valid_choices), 5)
                return random.choice(valid_choices[:pool_size])
            return None
            
        except Exception as e:
            LOGGER("ISTKHAR_MUSIC").error(f"YouTube Autoplay Function Error: {e}")
            return None

YouTube = YouTubeAPI()
