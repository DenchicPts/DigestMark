# yt-downloader — Video Download Service

A microservice for downloading audio and video by URL (YouTube, TikTok, Instagram, and more) via yt-dlp. Returns a token that can be used to retrieve the file.

Includes [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — bypasses YouTube's bot protection (PO Token).

## Requirements

- Docker + Docker Compose
- RAM: up to 500 MB
- Disk space: temporary files in `./video/` (cleaned up automatically)

## Getting Started

```bash
docker compose up -d
```

The service will be available at `http://localhost:9001`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `IDLE_TTL` | `300` | Seconds before an inactive file is deleted |
| `FETCH_TTL` | `180` | Seconds allowed to download a single file |
| `MAX_WORKERS` | `3` | Maximum number of parallel downloads |
| `DOWNLOAD_DIR` | `/app/video` | Directory for temporary files |
| `POT_HOST` | `bgutil` | bgutil service host |
| `POT_PORT` | `4416` | bgutil service port |

## API

### Download by URL

```bash
curl -X POST http://localhost:9001/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=...", "format": "audio"}'
```

Response:
```json
{
  "token": "abc123"
}
```

### Retrieve the File by Token

```bash
curl http://localhost:9001/file/abc123 -o audio.mp3
```

### Health Check

```bash
curl http://localhost:9001/health
```

## Notes

- Files are stored temporarily — deleted after `IDLE_TTL` seconds from the time of download
- bgutil starts first (`depends_on`), ytdl waits for it to be ready
- YouTube periodically changes its bot protection — update the `brainicism/bgutil-ytdlp-pot-provider` image if downloads start failing