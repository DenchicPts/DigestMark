# audio-transcribe — Transcription Service

Микросервис для транскрибации аудио и видео файлов через [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Принимает аудиофайл, возвращает текст.

## Требования

- Docker + Docker Compose
- RAM: до 2GB (зависит от размера модели)

## Запуск

```bash
docker compose up -d
```

Сервис доступен на `http://localhost:9000`

### Модель

По умолчанию модель **скачивается автоматически при первом запуске** контейнера в `./whisper-models/`. Размер зависит от `MODEL_SIZE`.

Если хочешь скачать модель заранее — укажи путь напрямую вместо размера:

```yaml
environment:
  - MODEL_SIZE=medium         # автоскачивание по размеру
  # ИЛИ
  - MODEL_PATH=/models/my-custom-model  # путь к заранее скачанной модели
```

## Конфигурация

| Переменная | По умолчанию | Описание |
|---|---|---|
| `MODEL_SIZE` | `medium` | Размер модели: `tiny` / `base` / `small` / `medium` / `large-v3-turbo` |
| `DEVICE` | `cpu` | `cpu` или `cuda` |
| `LANGUAGE` | _(авто)_ | Язык транскрибации, например `ru` или `en` |
| `BEAM_SIZE` | `5` | Точность: `1` = быстро, `5` = максимум |
| `IDLE_TIMEOUT` | `300` | Секунд простоя до выгрузки модели из RAM |
| `CPU_THREADS` | `0` | Потоков CPU, `0` = авто |

### Размеры моделей и требования к RAM

| Модель | RAM |
|---|---|
| tiny | ~1GB |
| base | ~1GB |
| small | ~1.5GB |
| medium | ~2GB |
| large-v3-turbo | ~6GB |

## API

### Транскрибация файла

```bash
curl -X POST http://localhost:9000/transcribe \
  -F "file=@audio.mp3"
```

Ответ:
```json
{
  "text": "транскрибированный текст..."
}
```

### Проверка статуса

```bash
curl http://localhost:9000/health
```