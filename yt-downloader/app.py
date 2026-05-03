import os
import time
import uuid
import asyncio
import threading
import logging
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse, Response
from pydantic import BaseModel
import yt_dlp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ytdl")

app = FastAPI(title="Video Downloader Service")

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/app/video"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

IDLE_TTL  = int(os.getenv("IDLE_TTL",  "300"))
FETCH_TTL = int(os.getenv("FETCH_TTL", "180"))

HTML_PATH = Path(__file__).parent / "index.html"

_executor = ThreadPoolExecutor(max_workers=int(os.getenv("MAX_WORKERS", "3")))

# ────────────────────────────────────────────────
#  Реестр активных файлов
# ────────────────────────────────────────────────

@dataclass
class VideoEntry:
    token:      str
    path:       Path
    title:      str
    filename:   str
    size:       int
    created_at: float
    fetched_at: Optional[float] = None
    _timer:     Optional[threading.Timer] = None

    def schedule_delete(self, delay: int):
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(delay, self._delete)
        self._timer.daemon = True
        self._timer.start()
        log.info("CLEANUP  scheduled  token=%s delay=%ds", self.token, delay)

    def _delete(self):
        try:
            if self.path.exists():
                self.path.unlink()
                log.info("CLEANUP  deleted  token=%s file=%s", self.token, self.path.name)
            else:
                log.info("CLEANUP  already_gone  token=%s", self.token)
        except Exception as e:
            log.error("CLEANUP  error  token=%s err=%s", self.token, e)
        _registry.pop(self.token, None)


_registry: dict[str, VideoEntry] = {}
_reg_lock = threading.Lock()


def _cleanup_orphans():
    removed = 0
    for f in DOWNLOAD_DIR.glob("ytdl_*"):
        try:
            f.unlink()
            removed += 1
        except Exception:
            pass
    if removed:
        log.info("STARTUP  orphans_removed=%d", removed)


_cleanup_orphans()

# ────────────────────────────────────────────────
#  Форматы yt-dlp
#
#  Схема кодеков:
#  h264_Xp  — только H.264 (avc1/avc/h264), лимит высоты X.
#             Работает в стандартном проигрывателе Windows БЕЗ доп. кодеков.
#             YouTube отдаёт H.264 максимум до 1080p.
#
#  vp9_Xp   — VP9, лимит высоты X (до 4K включительно).
#             Бесплатно воспроизводится в браузере и VLC.
#             Нативный проигрыватель Windows НЕ поддерживает VP9 без расширения.
#
#  av1      — AV1, лучшее качество/размер, до 8K.
#             Требует Windows 11 + расширение AV1 (бесплатно в Microsoft Store)
#             или VLC.
#
#  audio    — только звук, MP3 192 kbps.
# ────────────────────────────────────────────────

def _h264(height: Optional[int] = None) -> str:
    """H.264 + m4a → mp4. YouTube даёт H.264 максимум до 1080p."""
    h = f"[height<={height}]" if height else ""
    return (
        f"bestvideo[vcodec^=avc1]{h}[ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[vcodec^=avc]{h}[ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[vcodec=h264]{h}[ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo[vcodec^=avc1]{h}+bestaudio"
        f"/bestvideo[vcodec^=avc]{h}+bestaudio"
        f"/bestvideo[vcodec=h264]{h}+bestaudio"
        f"/best[vcodec^=avc1]{h}"
        f"/best[vcodec^=avc]{h}"
        f"/best[vcodec=h264]{h}"
    )

def _vp9(height: Optional[int] = None) -> str:
    """VP9 + opus/m4a → mp4. До 4K на YouTube."""
    h = f"[height<={height}]" if height else ""
    return (
        f"bestvideo[vcodec^=vp9]{h}+bestaudio[ext=m4a]"
        f"/bestvideo[vcodec^=vp0]{h}+bestaudio[ext=m4a]"
        f"/bestvideo[vcodec^=vp9]{h}+bestaudio"
        f"/bestvideo[vcodec^=vp0]{h}+bestaudio"
        f"/best[vcodec^=vp9]{h}"
        f"/best[vcodec^=vp0]{h}"
    )

FORMAT_MAP = {
    # ── H.264 (Windows Media Player / стандартный проигрыватель) ──
    "h264_1080p": _h264(1080),
    "h264_720p":  _h264(720),
    "h264_480p":  _h264(480),
    "h264_360p":  _h264(360),

    # ── VP9 (VLC / браузер, до 4K) ──
    "vp9_4k":    _vp9(2160),
    "vp9_1440p": _vp9(1440),
    "vp9_1080p": _vp9(1080),
    "vp9_720p":  _vp9(720),

    # ── AV1 (VLC / Win11 + бесплатное расширение из Store) ──
    "av1": (
        "bestvideo[vcodec^=av01]+bestaudio[ext=m4a]"
        "/bestvideo[vcodec^=av01]+bestaudio"
        "/best[vcodec^=av01]"
    ),

    # ── Только звук ──
    "audio": "bestaudio/best",
}


# ────────────────────────────────────────────────
#  Endpoint для получения доступных форматов видео
# ────────────────────────────────────────────────
@app.get("/api/formats")
def api_formats(url: str = Query(...)):
    """
    Возвращает список форматов, реально доступных для данного URL.
    Фронтенд вызывает это чтобы показать только кнопки которые сработают.
    """
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get("formats", [])
        heights = set()
        codecs  = set()
        for f in formats:
            h = f.get("height")
            if h:
                heights.add(h)
            vc = (f.get("vcodec") or "").lower()
            if vc and vc != "none":
                if vc.startswith("avc") or vc.startswith("h264"):
                    codecs.add("h264")
                elif vc.startswith("vp9") or vc.startswith("vp0"):
                    codecs.add("vp9")
                elif vc.startswith("av01") or vc.startswith("av1"):
                    codecs.add("av1")

        available = []
        for key in FORMAT_MAP:
            if key == "audio":
                available.append(key)
                continue
            codec, *rest = key.split("_")
            res = rest[0] if rest else ""
            h_limit = int(res.replace("p","").replace("k","000").replace("4000","2160")) if res else 99999
            if codec in codecs and any(h <= h_limit for h in heights):
                available.append(key)

        return {"available": available, "heights": sorted(heights, reverse=True), "codecs": list(codecs)}
    except Exception as e:
        return {"available": list(FORMAT_MAP.keys()), "error": str(e)}


# ────────────────────────────────────────────────
#  Ядро скачивания (в thread pool)
# ────────────────────────────────────────────────
def _run_download(
    url: str,
    fmt: str,
    token: str,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
):
    def _push(data: dict):
        loop.call_soon_threadsafe(queue.put_nowait, json.dumps(data, ensure_ascii=False))

    def _end():
        loop.call_soon_threadsafe(queue.put_nowait, None)

    output_tpl = str(DOWNLOAD_DIR / f"ytdl_{token}.%(ext)s")

    # Флаг: метаданные уже отправлены клиенту
    info_sent = threading.Event()

    def progress_hook(d):
        # При первом прогрессе отправляем метаданные из info_dict — без лишнего запроса к YT
        if not info_sent.is_set():
            inf = d.get("info_dict") or {}
            _push({
                "type":     "info",
                "title":    inf.get("title") or "video",
                "duration": inf.get("duration") or 0,
                "uploader": inf.get("uploader") or "",
                "platform": inf.get("extractor_key") or "",
            })
            info_sent.set()

        if d["status"] == "downloading":
            total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            speed      = d.get("speed") or 0
            eta        = d.get("eta") or 0
            percent    = int(downloaded / total * 100) if total else 0
            _push({
                "type":          "progress",
                "percent":       percent,
                "speed_mb":      round(speed / 1024 / 1024, 2),
                "eta":           eta,
                "downloaded_mb": round(downloaded / 1024 / 1024, 2),
                "total_mb":      round(total / 1024 / 1024, 2),
            })
        elif d["status"] == "finished":
            _push({"type": "processing", "message": "Обработка файла…"})

    is_audio = fmt == "audio"

    base_opts = {
        "outtmpl":             output_tpl,
        "progress_hooks":      [progress_hook],
        "quiet":               True,
        "no_warnings":         True,
        "noplaylist":          True,
        "format":              FORMAT_MAP.get(fmt, FORMAT_MAP["h264_1080p"]),
        "merge_output_format": None if is_audio else "mp4",
        # ── Оптимизация скорости скачивания ──
        "concurrent_fragment_downloads": 4,        # параллельные фрагменты
        "http_chunk_size":               10 * 1024 * 1024,  # чанк 10 MB
        "buffersize":                    1024 * 16,          # буфер записи
        "check_formats":                 False,              # не перепроверять форматы
        # ── POT провайдер ──
        "extractor_args": {
            "youtubepot-bgutilhttp": {
                "base_url": [f"http://{os.getenv('POT_HOST', 'bgutil')}:{os.getenv('POT_PORT', '4416')}"]
            }
        },
    }

    if is_audio:
        base_opts["postprocessors"] = [{
            "key":              "FFmpegExtractAudio",
            "preferredcodec":   "mp3",
            "preferredquality": "192",
        }]
    else:
        base_opts["postprocessors"] = [{
            "key":            "FFmpegVideoRemuxer",
            "preferedformat": "mp4",
        }]

    t0 = time.time()
    log.info("DOWNLOAD  start  token=%s fmt=%s url=%.70s", token, fmt, url)

    try:
        # Один вызов вместо двух — метаданные берём из info_dict в progress_hook
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # На случай если хук не сработал (очень короткое видео / аудио)
        if not info_sent.is_set() and info:
            _push({
                "type":     "info",
                "title":    info.get("title") or "video",
                "duration": info.get("duration") or 0,
                "uploader": info.get("uploader") or "",
                "platform": info.get("extractor_key") or "",
            })

        title = (info or {}).get("title") or "video"

        ext = "mp3" if fmt == "audio" else "mp4"
        out_path = DOWNLOAD_DIR / f"ytdl_{token}.{ext}"
        if not out_path.exists():
            candidates = list(DOWNLOAD_DIR.glob(f"ytdl_{token}.*"))
            if not candidates:
                raise FileNotFoundError("Выходной файл не найден после скачивания")
            out_path = max(candidates, key=lambda p: p.stat().st_size)

        size = out_path.stat().st_size
        safe_title = "".join(c if c.isalnum() or c in " -_." else "_" for c in title)[:80].strip("_")
        filename = f"{safe_title}.{out_path.suffix.lstrip('.')}"

        elapsed = round(time.time() - t0, 1)
        log.info("DOWNLOAD  done  token=%s elapsed=%.1fs size=%.1fMB", token, elapsed, size / 1024 / 1024)

        entry = VideoEntry(
            token=token, path=out_path, title=title,
            filename=filename, size=size, created_at=time.time(),
        )
        entry.schedule_delete(IDLE_TTL)
        with _reg_lock:
            _registry[token] = entry

        _push({
            "type":         "done",
            "token":        token,
            "title":        title,
            "filename":     filename,
            "size_mb":      round(size / 1024 / 1024, 2),
            "elapsed_s":    elapsed,
            "download_url": f"/file/{token}",
            "expires_in":   IDLE_TTL,
        })

    except Exception as e:
        log.error("DOWNLOAD  error  token=%s err=%s", token, str(e))
        _push({"type": "error", "message": str(e)})
        for f in DOWNLOAD_DIR.glob(f"ytdl_{token}.*"):
            try:
                f.unlink()
            except Exception:
                pass
    finally:
        _end()


# ────────────────────────────────────────────────
#  Роуты
# ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    if HTML_PATH.exists():
        return HTMLResponse(HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html not found</h1>", 500)


@app.get("/health")
def health():
    with _reg_lock:
        active = len(_registry)
        total_mb = sum(e.size for e in _registry.values()) / 1024 / 1024
    return {
        "status":        "ok",
        "active_files":  active,
        "total_size_mb": round(total_mb, 2),
        "idle_ttl":      IDLE_TTL,
        "fetch_ttl":     FETCH_TTL,
        "download_dir":  str(DOWNLOAD_DIR),
        "formats":       list(FORMAT_MAP.keys()),
    }


@app.post("/download/stream")
async def download_stream(
    url: str = Query(...),
    fmt: str = Query("h264_1080p"),
):
    if fmt not in FORMAT_MAP:
        raise HTTPException(400, f"Неизвестный формат. Доступно: {list(FORMAT_MAP)}")

    token = uuid.uuid4().hex
    queue: asyncio.Queue = asyncio.Queue()
    loop  = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_download, url, fmt, token, queue, loop)

    async def generate():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


class DownloadRequest(BaseModel):
    url: str
    fmt: str = "h264_1080p"


@app.post("/api/download")
async def api_download(req: DownloadRequest):
    if req.fmt not in FORMAT_MAP:
        raise HTTPException(400, f"Неизвестный формат. Доступно: {list(FORMAT_MAP)}")

    token = uuid.uuid4().hex
    queue: asyncio.Queue = asyncio.Queue()
    loop  = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_download, req.url, req.fmt, token, queue, loop)

    while True:
        item = await queue.get()
        if item is None:
            raise HTTPException(500, "Скачивание завершилось без результата")
        evt = json.loads(item)
        if evt["type"] == "done":
            return JSONResponse(evt)
        if evt["type"] == "error":
            raise HTTPException(500, evt["message"])


@app.get("/file/{token}")
def get_file(token: str):
    with _reg_lock:
        entry = _registry.get(token)

    if not entry:
        raise HTTPException(404, "Файл не найден или истёк срок хранения")
    if not entry.path.exists():
        with _reg_lock:
            _registry.pop(token, None)
        raise HTTPException(404, "Файл не найден на диске")

    if entry.fetched_at is None:
        entry.fetched_at = time.time()
        entry.schedule_delete(FETCH_TTL)
        log.info("FILE  first_fetch  token=%s new_ttl=%ds", token, FETCH_TTL)

    return FileResponse(
        path=str(entry.path),
        filename=entry.filename,
        media_type="application/octet-stream",
        headers={
            "Content-Length":    str(entry.size),   # браузер видит размер → точный прогресс
            "Accept-Ranges":     "bytes",            # поддержка докачки
            "Cache-Control":     "no-store",
            "X-Accel-Buffering": "no",               # отключить буферизацию nginx если он есть
        },
    )


@app.get("/api/status/{token}")
def api_status(token: str):
    with _reg_lock:
        entry = _registry.get(token)
    if not entry:
        return JSONResponse({"status": "not_found"}, status_code=404)

    base_time  = entry.fetched_at or entry.created_at
    ttl        = FETCH_TTL if entry.fetched_at else IDLE_TTL
    expires_in = max(0, round(base_time + ttl - time.time()))

    return {
        "status":       "ready",
        "token":        token,
        "title":        entry.title,
        "filename":     entry.filename,
        "size_mb":      round(entry.size / 1024 / 1024, 2),
        "download_url": f"/file/{token}",
        "expires_in":   expires_in,
        "fetched":      entry.fetched_at is not None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001, timeout_keep_alive=600)