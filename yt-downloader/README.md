# yt-downloader — Video Download Service

Микросервис для скачивания аудио из видео по ссылке (YouTube, TikTok, Instagram и др.) через yt-dlp. Возвращает токен по которому можно забрать файл.

Включает [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — обходит защиту YouTube от ботов (PO Token).

## Требования

- Docker + Docker Compose
- RAM: до 500MB
- Место на диске: временные файлы в `./video/` (очищаются автоматически)

## Запуск

```bash
docker compose up -d
```

Сервис доступен на `http://localhost:9001`

## Конфигурация

| Переменная | По умолчанию | Описание |
|---|---|---|
| `IDLE_TTL` | `300` | Секунд до удаления неактивного файла |
| `FETCH_TTL` | `180` | Секунд на скачивание одного файла |
| `MAX_WORKERS` | `3` | Максимум параллельных загрузок |
| `DOWNLOAD_DIR` | `/app/video` | Папка для временных файлов |
| `POT_HOST` | `bgutil` | Хост bgutil сервиса |
| `POT_PORT` | `4416` | Порт bgutil сервиса |

## API

### Скачать аудио по ссылке

```bash
curl -X POST http://localhost:9001/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=...", "format": "audio"}'
```

Ответ:
```json
{
  "token": "abc123"
}
```

### Получить файл по токену

```bash
curl http://localhost:9001/file/abc123 -o audio.mp3
```

### Проверка статуса

```bash
curl http://localhost:9001/health
```

## Заметки

- Файлы хранятся временно — удаляются через `IDLE_TTL` секунд после скачивания
- bgutil запускается первым (`depends_on`), ytdl ждёт его готовности
- YouTube периодически меняет защиту — обновляй образ `brainicism/bgutil-ytdlp-pot-provider` при проблемах со скачиванием