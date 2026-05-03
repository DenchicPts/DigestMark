# DigestMark

Turn any voice message, video or text into a structured Obsidian note — automatically.

Send a YouTube link, a voice message or just type something to your Telegram bot. DigestMark transcribes it, classifies it with a local LLM, and saves a clean markdown note to your Obsidian vault. Or answers your question directly in Telegram.

Runs mostly locally. Transcription and classification happen entirely on your hardware.

By default, note formatting and question answering use [OpenRouter](https://openrouter.ai) (cloud API) —
free models are available. If you want a fully local setup, replace the OpenRouter nodes in n8n
with your own local LLM endpoint (e.g. another llama.cpp instance or Ollama).

## How It Works

```
Telegram → transcribe → classify → note in Obsidian
                                 → answer in Telegram
```

- **Voice / audio / video** → Whisper transcribes → classified → saved as note
- **YouTube / TikTok / Vimeo link** → yt-dlp downloads audio → Whisper → saved as note
- **Text message** → classified → saved as note or answered directly

## Hardware Requirements

Tested on a **Lenovo ThinkCentre M720q** (i7-8700T, 8 GB RAM) — runs comfortably with all services active.

Minimum recommended: 4-core CPU, 8 GB RAM.

| Service | RAM usage |
|---|---|
| n8n | up to 1 GB |
| audio-transcribe (Whisper medium) | up to 2 GB |
| llama.cpp (phi-3-mini) | up to 3 GB |
| yt-downloader | up to 500 MB |
| **Total** | **~6.5 GB** |

No GPU required — everything runs on CPU.

## Services

### 🎙️ audio-transcribe

Audio and video transcription via [faster-whisper](https://github.com/SYSTRAN/faster-whisper).  
Uses **Whisper medium** by default — a good balance of speed and accuracy for English and Russian. The model is downloaded automatically on first run.  
Can be swapped for `tiny` / `base` / `small` / `large-v3-turbo` via the `MODEL_SIZE` environment variable.  
→ [README](audio-transcribe/README.md)

### 🧠 llama.cpp

Local text classification via [llama.cpp server](https://github.com/ggml-org/llama.cpp).  
Uses **phi-3-mini-q4** (Microsoft) — 3.8B parameters, runs entirely on CPU, uses ~2 GB RAM.  
Determines the type of incoming text (`note`, `question`, `task`, `plain`) and its category (`tech`, `docker`, `linux`, `personal`, etc.).  
→ [README](llama.cpp/README.md)

### 📥 yt-downloader

Audio extraction from video URLs via [yt-dlp](https://github.com/yt-dlp/yt-dlp).  
Supports YouTube, TikTok, Vimeo. Includes [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) to bypass YouTube bot protection.  
Returns a token — n8n uses it to fetch the file and pass it to Whisper.  
→ [README](yt-downloader/README.md)

### ⚙️ n8n

The orchestrator for the entire pipeline. Connects Telegram, all services, and Obsidian into a single workflow.  
The workflow is stored in `workflows/Telegram AI Pipeline.json`.  
→ [README](n8n/README.md)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/DigestMark
cd DigestMark
```

### 2. Download the llama.cpp Model

```bash
mkdir -p llama.cpp/models
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf \
  -O llama.cpp/models/phi-3-mini-q4.gguf
```

### 3. Configure n8n

Edit `n8n/docker-compose.yml` and replace the IP with your own:

```yaml
- N8N_HOST=YOUR_SERVER_IP
- WEBHOOK_URL=http://YOUR_SERVER_IP:5678/
```

### 4. Start All Services

```bash
docker compose up -d
```

### 5. Set Up the Workflow

Full instructions → [n8n/README](n8n/README.md)

## API

All three services can be used independently of the n8n pipeline — for your own projects or integrations.

### Transcribe Audio

```bash
curl -X POST http://YOUR_SERVER_IP:9000/transcribe \
  -F "file=@audio.mp3"
```

### Download Audio from Video

```bash
# Request a download
curl -X POST http://YOUR_SERVER_IP:9001/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=...", "format": "audio"}'

# Retrieve the file by token
curl http://YOUR_SERVER_IP:9001/file/TOKEN -o audio.mp3
```

### Classify Text

```bash
curl -X POST http://YOUR_SERVER_IP:9002/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "your text here", "n_predict": 200, "temperature": 0}'
```

## Credits

Built with [Claude](https://claude.ai) by Anthropic.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE)