# DigestMark

Turn any voice message, video or text into a structured Obsidian note — automatically.

Send a YouTube link, a voice message or just type something to your Telegram bot. DigestMark transcribes it, classifies it with a local LLM, and saves a clean markdown note to your Obsidian vault. Or answers your question directly in Telegram.

Runs mostly locally. Transcription and classification happen entirely on your hardware.
By default, note formatting and question answering use [OpenRouter](https://openrouter.ai) (cloud API) — 
free models are available. If you want a fully local setup, replace the OpenRouter nodes in n8n 
with your own local LLM endpoint (e.g. another llama.cpp instance or Ollama).

## How it works

```
Telegram → transcribe → classify → note in Obsidian
                                 → answer in Telegram
```

- **Voice / audio / video** → Whisper transcribes → classified → saved as note
- **YouTube / TikTok / Vimeo link** → yt-dlp downloads audio → Whisper → saved as note  
- **Text message** → classified → saved as note or answered directly

## Hardware Requirements

Tested on **Lenovo ThinkCentre M720q** (i7-8700T, 8GB RAM) — runs comfortably with all services active.

Minimum recommended: 4-core CPU, 8GB RAM.

| Service | RAM usage |
|---|---|
| n8n | up to 1GB |
| audio-transcribe (Whisper medium) | up to 2GB |
| llama.cpp (phi-3-mini) | up to 3GB |
| yt-downloader | up to 500MB |
| **Total** | **~6.5GB** |

GPU не требуется — всё работает на CPU.

## Services

### 🎙️ audio-transcribe
Транскрибация аудио и видео файлов через [faster-whisper](https://github.com/SYSTRAN/faster-whisper).  
По умолчанию используется модель **Whisper medium** — хороший баланс скорости и точности для русского и английского языков. Модель скачивается автоматически при первом запуске.  
Доступна замена на `tiny` / `base` / `small` / `large-v3-turbo` через переменную `MODEL_SIZE`.  
→ [README](audio-transcribe/README)

### 🧠 llama.cpp
Локальная классификация текста через [llama.cpp server](https://github.com/ggml-org/llama.cpp).  
Используется модель **phi-3-mini-q4** (Microsoft) — 3.8B параметров, работает полностью на CPU, занимает ~2GB RAM.  
Определяет тип входящего текста (`note`, `question`, `task`, `plain`) и категорию (`tech`, `docker`, `linux`, `personal` и др.).  
→ [README](llama.cpp/README)

### 📥 yt-downloader
Скачивание аудио из видео по ссылке через [yt-dlp](https://github.com/yt-dlp/yt-dlp).  
Поддерживает YouTube, TikTok, Vimeo. Включает [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) для обхода защиты YouTube.  
Возвращает токен — по нему n8n забирает файл и передаёт в Whisper.  
→ [README](yt-downloader/README)

### ⚙️ n8n
Оркестратор всего pipeline. Связывает Telegram, все сервисы и Obsidian в единый поток.  
Воркфлоу хранится в `workflows/Telegram AI Pipeline.json`.  
→ [README](n8n/README)

## Quick Start

### 1. Склонируй репозиторий

```bash
git clone https://github.com/YOUR_USERNAME/DigestMark
cd DigestMark
```

### 2. Скачай модель для llama.cpp

```bash
mkdir -p llama.cpp/models
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf \
  -O llama.cpp/models/phi-3-mini-q4.gguf
```

### 3. Настрой n8n

Отредактируй `n8n/docker-compose.yml` — замени IP на свой:

```yaml
- N8N_HOST=YOUR_SERVER_IP
- WEBHOOK_URL=http://YOUR_SERVER_IP:5678/
```

### 4. Запусти все сервисы

```bash
docker compose up -d
```

### 5. Настрой воркфлоу

Подробная инструкция → [n8n/README](n8n/README)

## API

Три сервиса можно использовать независимо от n8n pipeline — для своих проектов или интеграций.

### Транскрибация аудио
```bash
curl -X POST http://YOUR_SERVER_IP:9000/transcribe \
  -F "file=@audio.mp3"
```

### Скачивание аудио из видео
```bash
# Запросить скачивание
curl -X POST http://YOUR_SERVER_IP:9001/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=...", "format": "audio"}'

# Забрать файл по токену
curl http://YOUR_SERVER_IP:9001/file/TOKEN -o audio.mp3
```

### Классификация текста
```bash
curl -X POST http://YOUR_SERVER_IP:9002/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "твой текст здесь", "n_predict": 200, "temperature": 0}'
```

## Credits

Built with [Claude](https://claude.ai) by Anthropic.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE)