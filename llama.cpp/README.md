# llama.cpp — Classification Service

A microservice for text classification. Runs a local LLM (phi-3-mini) via llama.cpp server and accepts classification requests from an n8n pipeline.

## Requirements

- Docker + Docker Compose
- ~3 GB of free disk space for the model

## Setup

### 1. Download the Model

```bash
# wget
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf \
  -O models/phi-3-mini-q4.gguf

# curl
curl -L -o models/phi-3-mini-q4.gguf \
  https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
```

### 2. Start the Service

```bash
docker compose up -d
```

The service will be available at `http://localhost:9002`

## API

### Classify Text

```bash
curl -X POST http://localhost:9002/completion \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Classify: buy milk tomorrow",
    "n_predict": 200,
    "temperature": 0
  }'
```

### Health Check

```bash
curl http://localhost:9002/health
```

## Configuration

| Parameter | Value | Description |
|---|---|---|
| Port | 9002 | External service port |
| ctx-size | 2048 | Context size in tokens |
| threads | 4 | CPU threads for inference |
| n-predict | 128 | Max tokens in response |

## Notes

- The model is loaded into RAM only (`--no-mmap`)
- The service sleeps after 180 seconds of idle time (`--sleep-idle-seconds`)
- Request timeout is 300 seconds (`-to 300`)