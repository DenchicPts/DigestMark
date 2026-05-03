# n8n — Automation Pipeline

Оркестратор DigestMark. Получает сообщения из Telegram, маршрутизирует по типу контента, транскрибирует, классифицирует через локальную LLM и сохраняет заметки в Obsidian.

## Требования

- Docker + Docker Compose
- Telegram Bot Token — получить у [@BotFather](https://t.me/BotFather)
- OpenRouter API Key — [openrouter.ai](https://openrouter.ai)
- Все остальные сервисы DigestMark запущены

## Установка Telegram Polling плагина

Pipeline использует polling вместо webhook для получения сообщений из Telegram. Для этого нужен дополнительный плагин в n8n.

После запуска контейнера установи плагин:

```bash
docker exec -it n8n \
  n8n community-nodes install n8n-nodes-telegram-polling
``` 
*Не факт что так сработает, лучше через интерфейс в n8n установить*

Перезапусти контейнер:

```bash
docker compose restart
```

## Настройка

### 1. Поправь docker-compose.yml

Замени на свои значения:

```yaml
environment:
  - N8N_HOST=YOUR_SERVER_IP
  - WEBHOOK_URL=http://YOUR_SERVER_IP:5678/
  - GENERIC_TIMEZONE=Europe/Riga  # поменяй на свой часовой пояс
```

### 2. Настрой папку Obsidian

Заметки сохраняются в `/obsidian` внутри контейнера. Смонтируй туда свою папку.

**Вариант A — локальная папка на сервере:**

Просто укажи путь в `docker-compose.yml`:

```yaml
volumes:
  - /path/to/your/obsidian/vault:/obsidian
```

**Вариант B — Samba/CIFS сетевая папка:**

Сначала примонтируй сетевую папку на хосте:

```bash
apt install cifs-utils

mount -t cifs //192.168.1.x/obsidian /mnt/obsidian \
  -o username=user,password=pass,uid=1000,gid=1000

# Автомонтирование при старте — добавь в /etc/fstab
//192.168.1.x/obsidian /mnt/obsidian cifs username=user,password=pass,uid=1000,gid=1000 0 0
```

Затем в `docker-compose.yml` пропиши смонтированную папку хоста:

```yaml
volumes:
  - /mnt/obsidian:/obsidian
```

**Вариант C — Syncthing (рекомендую):**

Установи [Syncthing](https://syncthing.net/) на сервер и на устройство с Obsidian — папка будет автоматически синхронизироваться в обе стороны. Новые заметки появятся через секунды.

### 3. Куда и как сохраняются заметки

По умолчанию заметки сохраняются в `/obsidian/{category}/{title}.md` где категория определяется классификатором автоматически (`tech`, `docker`, `personal` и т.д.).

Структуру папок и формат заметок можно полностью изменить под себя — отредактируй system prompt в ноде `Agent: Format Note` и путь в ноде `Build File Path`. Система гибкая: хочешь плоскую структуру без папок, хочешь другой формат frontmatter — просто поправь промпт.

### 4. Запусти сервис

```bash
docker compose up -d
```

n8n доступен на `http://YOUR_SERVER_IP:5678`

### 5. Импортируй воркфлоу

1. Открой n8n → **Settings → Import workflow**
2. Загрузи файл `./Telegram AI Pipeline.json`
3. Настрой credentials:
   - **Telegram** → добавь Bot Token
   - **OpenRouter** → добавь API Key
4. В ноде `Detect Content Type` замени `ALLOWED_USER_ID` на свой Telegram ID
   (узнать: [@userinfobot](https://t.me/userinfobot))
5. В нодах HTTP Request замени `YOUR_SERVER_IP` на IP своего сервера
6. Нажми **Publish** чтобы активировать воркфлоу

## Как работает pipeline

```
Telegram сообщение
       │
       ▼
Detect Content Type
  ┌────┴────┬──────────┐
media      url        text
  │         │           │
Whisper   yt-dlp     напрямую
  │       + Whisper     │
  └────┬────┘           │
       ▼                │
  llama.cpp             │
  классификация ◄───────┘
       │
  ┌────┴──────┬──────────┐
note/task  question    plain
  │           │           │
Format      Agent       Agent
Note        Answer      Answer
  │           │           │
Obsidian   Telegram   Telegram
```

| Тип входа | Обработка |
|---|---|
| 🎤 Голосовое / аудио / видео | Whisper транскрипция → классификация |
| 🔗 YouTube / TikTok / Vimeo | yt-dlp скачивание → Whisper → классификация |
| 💬 Текст | Напрямую на классификацию |

| Классификация | Результат |
|---|---|
| `note` / `task` | Форматируется в Obsidian markdown, сохраняется по категории |
| `question` / `plain` | OpenRouter LLM отвечает в Telegram |

## Структура заметок в Obsidian

```
/obsidian/
  tech/
    llm-optimization-tips.md
  docker/
    docker-compose-networks.md
  personal/
    ...
```

Каждая заметка содержит frontmatter: `title`, `date`, `category`, `tags`.