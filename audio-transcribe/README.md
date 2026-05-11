# audio-transcribe — WhisperX Transcription Service

Микросервис для транскрибации аудио и видео файлов через [WhisperX](https://github.com/m-bain/whisperX).

## Что изменилось по сравнению с faster-whisper

| | faster-whisper | WhisperX |
|---|---|---|
| Backend | CTranslate2 | CTranslate2 (тот же) |
| VAD | фильтр (post-hoc) | препроцессинг перед батчингом |
| Батчинг | нет | по VAD-сегментам |
| Таймкоды | сегмент-уровень | слово-уровень (wav2vec2) |
| Галлюцинации | `condition_on_prev_text=True` | отключено по умолчанию |
| CPU режим | `int8` | `int8`, `batch_size=1` |

На CPU прирост скромнее чем на GPU, но длинные файлы с паузами обрабатываются заметно быстрее
благодаря VAD — тишина пропускается ещё до транскрибации.

## Требования

- Docker + Docker Compose
- RAM: до 4 ГБ (зависит от модели)
- GPU: не нужна, работает на CPU

## Запуск

```bash
docker compose up -d
```

Сервис доступен на `http://localhost:9000`

### Модели и RAM

| Модель | RAM |
|---|---|
| tiny | ~1 ГБ |
| base | ~1 ГБ |
| small | ~1.5 ГБ |
| medium | ~2 ГБ |
| large-v3-turbo | ~6 ГБ |

Модели скачиваются автоматически в `./whisper-models/` при первом запросе.

## Конфигурация

| Переменная | По умолчанию | Описание |
|---|---|---|
| `MODEL_SIZE` | `medium` | Размер модели |
| `DEVICE` | `cpu` | `cpu` или `cuda` |
| `CPU_THREADS` | `0` | Потоки CPU, `0` = авто |
| `BATCH_SIZE` | `1` | На CPU оставить 1 |
| `LANGUAGE` | _(авто)_ | Язык, например `ru` или `en` |
| `IDLE_TIMEOUT` | `300` | Секунд простоя до выгрузки модели |

## API

### Транскрибация файла

```bash
curl -X POST http://localhost:9000/transcribe \
  -F "file=@audio.mp3"
```

Ответ:
```json
{
  "text": "транскрибированный текст...",
  "language": "ru",
  "elapsed_s": 12.4,
  "segments": [
    {"start": 0.0, "end": 2.5, "text": "..."}
  ]
}
```

### Health check

```bash
curl http://localhost:9000/health
```

### Стриминг (SSE)

```bash
curl -X POST http://localhost:9000/transcribe/stream \
  -F "file=@audio.mp3"
```
