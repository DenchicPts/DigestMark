# audio-transcribe — Transcription Service

A microservice for transcribing audio and video files via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Accepts an audio file, returns the transcribed text.

## Requirements

- Docker + Docker Compose
- RAM: up to 2 GB (depends on model size)

## Getting Started

```bash
docker compose up -d
```

The service will be available at `http://localhost:9000`

### Model

By default the model is **downloaded automatically on first run** into `./whisper-models/`. The size depends on `MODEL_SIZE`.

If you want to download the model in advance, specify the path directly instead of the size:

```yaml
environment:
  - MODEL_SIZE=medium         # auto-download by size name
  # OR
  - MODEL_PATH=/models/my-custom-model  # path to a pre-downloaded model
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MODEL_SIZE` | `medium` | Model size: `tiny` / `base` / `small` / `medium` / `large-v3-turbo` |
| `DEVICE` | `cpu` | `cpu` or `cuda` |
| `LANGUAGE` | _(auto)_ | Transcription language, e.g. `ru` or `en` |
| `BEAM_SIZE` | `5` | Accuracy: `1` = fastest, `5` = best |
| `IDLE_TIMEOUT` | `300` | Seconds of idle time before the model is unloaded from RAM |
| `CPU_THREADS` | `0` | CPU threads, `0` = auto |

### Model Sizes and RAM Requirements

| Model | RAM |
|---|---|
| tiny | ~1 GB |
| base | ~1 GB |
| small | ~1.5 GB |
| medium | ~2 GB |
| large-v3-turbo | ~6 GB |

## API

### Transcribe a File

```bash
curl -X POST http://localhost:9000/transcribe \
  -F "file=@audio.mp3"
```

Response:
```json
{
  "text": "transcribed text..."
}
```

### Health Check

```bash
curl http://localhost:9000/health
```