# llama.cpp — Classification Service

Микросервис для классификации текста. Запускает локальную LLM (phi-3-mini) через llama.cpp server и принимает запросы на классификацию от n8n pipeline.

## Требования

- Docker + Docker Compose
- ~3GB свободного места для модели

## Установка

### 1. Скачать модель

```bash
# wget
wget https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf \
  -O models/phi-3-mini-q4.gguf

# curl
curl -L -o models/phi-3-mini-q4.gguf \
  https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
```

### 2. Запустить сервис

```bash
docker compose up -d
```

Сервис будет доступен на `http://localhost:9002`

## API

### Классификация текста

```bash
curl -X POST http://localhost:9002/completion \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Classify: купить молоко завтра",
    "n_predict": 200,
    "temperature": 0
  }'
```

### Проверка статуса

```bash
curl http://localhost:9002/health
```

## Конфигурация

| Параметр | Значение | Описание |
|---|---|---|
| Port | 9002 | Внешний порт сервиса |
| ctx-size | 2048 | Размер контекста в токенах |
| threads | 4 | CPU потоков для инференса |
| n-predict | 128 | Макс токенов в ответе |

## Заметки

- Модель загружается только в RAM (`--no-mmap`)
- Сервис засыпает через 180 секунд простоя (`--sleep-idle-seconds`)
- Таймаут запроса 300 секунд (`-to 300`)