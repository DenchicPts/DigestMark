import os
import time
import tempfile
import subprocess
import json
import asyncio
import gc
import ctypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import whisperx

# Принудительно возвращаем память от ctranslate2 обратно ОС после выгрузки модели
try:
    _libc = ctypes.CDLL("libc.so.6")
    def _malloc_trim():
        _libc.malloc_trim(0)
        log.info("MODEL  malloc_trim  done — memory returned to OS")
except Exception:
    def _malloc_trim():
        pass

app = FastAPI(title="WhisperX Transcription Service")

MODEL_SIZE  = os.getenv("MODEL_SIZE", "medium")
DEVICE      = os.getenv("DEVICE", "cpu")
LANGUAGE    = os.getenv("LANGUAGE", None)
CPU_THREADS = int(os.getenv("CPU_THREADS", "0"))
# На CPU int8 — единственный разумный тип: быстрее float32, без потери точности
COMPUTE_TYPE = "int8"
# Размер батча для WhisperX. На CPU > 1 не даёт выигрыша, оставляем 1
BATCH_SIZE  = int(os.getenv("BATCH_SIZE", "1"))

SUPPORTED_EXTENSIONS = {
    ".ogg", ".oga", ".opus",
    ".mp3", ".mp4", ".m4a", ".aac",
    ".wav", ".flac", ".weba", ".webm",
    ".mov", ".avi", ".mkv", ".wma",
    ".amr", ".3gp", ".3gpp"
}

HTML_PATH = Path(__file__).parent / "index.html"

import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("whisperx")

IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "300"))

_executor = ThreadPoolExecutor(max_workers=2)


class ModelManager:
    """
    Ленивая загрузка WhisperX с автовыгрузкой после IDLE_TIMEOUT секунд простоя.
    Потокобезопасен.

    WhisperX отличия от faster-whisper:
    - VAD-препроцессинг: сначала находит речь, режет на сегменты, затем батчинг
    - Word-level timestamps через форсированное выравнивание (wav2vec2)
    - На CPU: compute_type=int8, batch_size=1 — оптимально
    """

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._last_used = 0.0
        self._loaded_at = 0.0
        self._unload_timer: threading.Timer | None = None
        self._total_requests = 0

    def _load(self):
        t0 = time.time()
        log.info("MODEL  loading  size=%s device=%s compute=%s threads=%s",
                 MODEL_SIZE, DEVICE, COMPUTE_TYPE, CPU_THREADS or "auto")
        self._model = whisperx.load_model(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            threads=CPU_THREADS if CPU_THREADS > 0 else 0,
            # asr_options — отключаем condition_on_prev_text: снижает галлюцинации
            asr_options={"condition_on_previous_text": False},
        )
        self._loaded_at = time.time()
        log.info("MODEL  ready    size=%s load_time=%.1fs",
                 MODEL_SIZE, self._loaded_at - t0)

    def _schedule_unload(self):
        if self._unload_timer:
            self._unload_timer.cancel()
        self._unload_timer = threading.Timer(IDLE_TIMEOUT, self._unload)
        self._unload_timer.daemon = True
        self._unload_timer.start()

    def _unload(self):
        with self._lock:
            if self._model is None:
                return
            idle_for = time.time() - self._last_used
            if idle_for < IDLE_TIMEOUT:
                self._schedule_unload()
                return
            uptime = time.time() - self._loaded_at
            log.info("MODEL  unload   idle=%.0fs uptime=%.0fs total_requests=%d",
                     idle_for, uptime, self._total_requests)
            del self._model
            self._model = None
            gc.collect()
            _malloc_trim()
            log.info("MODEL  unloaded  RAM freed")

    def get(self):
        with self._lock:
            was_unloaded = self._model is None
            if was_unloaded:
                self._total_requests = 0
                self._load()
            self._total_requests += 1
            self._last_used = time.time()
            self._schedule_unload()
            if was_unloaded:
                log.info("MODEL  session_start  idle_timeout=%ds", IDLE_TIMEOUT)
            return self._model

    @property
    def loaded(self) -> bool:
        return self._model is not None


model_manager = ModelManager()
log.info("MODEL  lazy_mode  will load on first request, unload after %ds idle", IDLE_TIMEOUT)


def convert_to_wav(input_path: str) -> str:
    output_path = input_path + ".wav"
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-f", "wav", output_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg: {result.stderr[-300:]}")
    return output_path


def run_whisperx(wav_path: str, language: str | None, task: str) -> dict:
    """
    Транскрибация через WhisperX.

    Отличие от faster-whisper:
    1. whisperx.load_audio() — загружает как float32 numpy array (16kHz mono)
    2. model.transcribe() — VAD внутри, режет на сегменты, батчинг по ним
    3. whisperx.load_align_model() + whisperx.align() — word-level timestamps

    На CPU batch_size=1 оптимален: больше не ускоряет, только тратит RAM.
    """
    model = model_manager.get()

    audio = whisperx.load_audio(wav_path)

    # Шаг 1: транскрибация с VAD-батчингом
    result = model.transcribe(
        audio,
        batch_size=BATCH_SIZE,
        language=language or None,
        task=task,
    )

    detected_lang = result.get("language", language or "unknown")

    # Шаг 2: word-level alignment (если язык поддерживается)
    try:
        align_model, align_metadata = whisperx.load_align_model(
            language_code=detected_lang,
            device=DEVICE,
        )
        result = whisperx.align(
            result["segments"],
            align_model,
            align_metadata,
            audio,
            DEVICE,
            return_char_alignments=False,
        )
        del align_model
        gc.collect()
        log.info("ALIGN  done  lang=%s", detected_lang)
    except Exception as e:
        log.warning("ALIGN  skipped  reason=%s", str(e))

    return result, detected_lang


async def save_upload(file: UploadFile) -> tuple[str, str]:
    filename = file.filename or "upload"
    ext = os.path.splitext(filename)[-1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            415,
            f"Unsupported format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    data = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
    return tmp.name, ext


def segments_to_output(segments: list, full_text_fallback: str = "") -> tuple[list, str]:
    """Преобразует сегменты WhisperX в формат ответа."""
    result_segments = []
    full_text = ""
    for seg in segments:
        text = seg.get("text", "").strip()
        result_segments.append({
            "start": round(seg.get("start", 0), 2),
            "end":   round(seg.get("end", 0), 2),
            "text":  text,
        })
        full_text += " " + text
    return result_segments, full_text.strip() or full_text_fallback


# ─────────────────────────────────────────────
#  GET /
# ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    if HTML_PATH.exists():
        return HTMLResponse(content=HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html not found</h1>", status_code=500)


# ─────────────────────────────────────────────
#  GET /health
# ─────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":       "ok",
        "backend":      "whisperx",
        "model":        MODEL_SIZE,
        "device":       DEVICE,
        "compute_type": COMPUTE_TYPE,
        "batch_size":   BATCH_SIZE,
        "cpu_threads":  CPU_THREADS or "auto",
        "model_loaded": model_manager.loaded,
        "idle_timeout": IDLE_TIMEOUT,
    }


# ─────────────────────────────────────────────
#  POST /transcribe  →  полный JSON (для n8n и curl)
# ─────────────────────────────────────────────
@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = None,
    task: str = "transcribe"
):
    """
    Возвращает полный JSON после завершения транскрибации.
    Используй для интеграций (n8n, curl, API).

    Ответ:
    {
        "text": "полный текст",
        "language": "ru",
        "elapsed_s": 12.4,
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "..."},
            ...
        ]
    }
    """
    tmp_path, _ = await save_upload(file)
    wav_path = None
    try:
        wav_path = convert_to_wav(tmp_path)
        lang = language or LANGUAGE or None
        t0 = time.time()
        log.info("TRANSCRIBE  start  file=%s size=%.2fMB lang=%s task=%s",
                 file.filename, os.path.getsize(wav_path) / 1024 / 1024,
                 lang or "auto", task)

        loop = asyncio.get_event_loop()
        wx_result, detected_lang = await loop.run_in_executor(
            _executor, lambda: run_whisperx(wav_path, lang, task)
        )

        segments = wx_result.get("segments", [])
        result_segments, full_text = segments_to_output(segments)

        elapsed = round(time.time() - t0, 1)
        log.info("TRANSCRIBE  done   elapsed=%.1fs lang=%s segments=%d words=%d",
                 elapsed, detected_lang, len(result_segments), len(full_text.split()))

        return JSONResponse({
            "text":      full_text,
            "language":  detected_lang,
            "elapsed_s": elapsed,
            "segments":  result_segments,
        })

    except RuntimeError as e:
        raise HTTPException(400, str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


# ─────────────────────────────────────────────
#  POST /transcribe/stream  →  SSE стриминг (для браузера)
# ─────────────────────────────────────────────
@app.post("/transcribe/stream")
async def transcribe_stream(
    file: UploadFile = File(...),
    language: str = None,
    task: str = "transcribe"
):
    """
    Стриминг результата через Server-Sent Events.
    Используется веб-интерфейсом — текст появляется по мере обработки.

    WhisperX не даёт true-streaming (сначала VAD, потом всё сразу),
    поэтому шлём сегменты пачкой после завершения транскрибации.

    События:
      data: {"type": "info",    "language": "ru"}
      data: {"type": "segment", "start": 0.0, "end": 2.5, "text": "..."}
      data: {"type": "done",    "full_text": "...", "elapsed_s": 12.4}
    """
    tmp_path, _ = await save_upload(file)

    try:
        wav_path = await asyncio.get_event_loop().run_in_executor(
            _executor, convert_to_wav, tmp_path
        )
    except RuntimeError as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(400, str(e))

    lang = language or LANGUAGE or None
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def run_transcription():
        t0 = time.time()
        try:
            log.info("STREAM  start  file=%s size=%.2fMB lang=%s task=%s",
                     file.filename, os.path.getsize(wav_path) / 1024 / 1024,
                     lang or "auto", task)

            wx_result, detected_lang = run_whisperx(wav_path, lang, task)

            loop.call_soon_threadsafe(
                queue.put_nowait,
                json.dumps({"type": "info", "language": detected_lang})
            )

            segments = wx_result.get("segments", [])
            result_segments, full_text = segments_to_output(segments)

            for seg in result_segments:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    json.dumps({"type": "segment", **seg}, ensure_ascii=False)
                )

            elapsed = round(time.time() - t0, 1)
            log.info("STREAM  done   elapsed=%.1fs lang=%s segments=%d words=%d",
                     elapsed, detected_lang, len(result_segments), len(full_text.split()))

            loop.call_soon_threadsafe(
                queue.put_nowait,
                json.dumps({"type": "done", "full_text": full_text,
                            "elapsed_s": elapsed}, ensure_ascii=False)
            )
        except Exception as e:
            log.error("STREAM  error  file=%s error=%s", file.filename, str(e))
            loop.call_soon_threadsafe(
                queue.put_nowait,
                json.dumps({"type": "error", "message": str(e)})
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)
            for p in (tmp_path, wav_path):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except OSError:
                    pass

    asyncio.get_event_loop().run_in_executor(_executor, run_transcription)

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
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000, timeout_keep_alive=600)
