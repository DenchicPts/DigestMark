# n8n — Automation Pipeline

The DigestMark orchestrator. Receives messages from Telegram, routes them by content type, transcribes audio, classifies text via a local LLM, and saves notes to Obsidian.

## Requirements

- Docker + Docker Compose
- Telegram Bot Token — get one from [@BotFather](https://t.me/BotFather)
- OpenRouter API Key — [openrouter.ai](https://openrouter.ai)
- All other DigestMark services running

## Installing the Telegram Polling Plugin

The pipeline uses polling instead of webhooks to receive Telegram messages. This requires an additional plugin in n8n.

After starting the container, install the plugin:

```bash
docker exec -it n8n \
  n8n community-nodes install n8n-nodes-telegram-polling
```

*This may not work from the CLI — installing via the n8n UI is more reliable.*

Then restart the container:

```bash
docker compose restart
```

## Setup

### 1. Edit docker-compose.yml

Replace with your own values:

```yaml
environment:
  - N8N_HOST=YOUR_SERVER_IP
  - WEBHOOK_URL=http://YOUR_SERVER_IP:5678/
  - GENERIC_TIMEZONE=Europe/Riga  # change to your timezone
```

### 2. Configure the Obsidian Folder

Notes are saved to `/obsidian` inside the container. Mount your vault folder there.

**Option A — local folder on the server:**

Just specify the path in `docker-compose.yml`:

```yaml
volumes:
  - /path/to/your/obsidian/vault:/obsidian
```

**Option B — Samba/CIFS network share:**

First mount the network share on the host:

```bash
apt install cifs-utils

mount -t cifs //192.168.1.x/obsidian /mnt/obsidian \
  -o username=user,password=pass,uid=1000,gid=1000

# Auto-mount on boot — add to /etc/fstab:
//192.168.1.x/obsidian /mnt/obsidian cifs username=user,password=pass,uid=1000,gid=1000 0 0
```

Then point `docker-compose.yml` at the mounted host folder:

```yaml
volumes:
  - /mnt/obsidian:/obsidian
```

**Option C — Syncthing (recommended):**

Install [Syncthing](https://syncthing.net/) on the server and on the device running Obsidian — the folder will sync automatically in both directions and new notes will appear within seconds.

### 3. How and Where Notes Are Saved

By default notes are saved to `/obsidian/{category}/{title}.md`, where the category is determined automatically by the classifier (`tech`, `docker`, `personal`, etc.).

The folder structure and note format are fully customizable — edit the system prompt in the `Agent: Format Note` node and the path in the `Build File Path` node. The system is flexible: flat structure with no subfolders, a different frontmatter format — just update the prompt.

### 4. Start the Service

```bash
docker compose up -d
```

n8n will be available at `http://YOUR_SERVER_IP:5678`

### 5. Import the Workflow

1. Open n8n → **Settings → Import workflow**
2. Upload the file `./Telegram AI Pipeline.json`
3. Configure credentials:
   - **Telegram** → add your Bot Token
   - **OpenRouter** → add your API Key
4. In the `Detect Content Type` node, replace `ALLOWED_USER_ID` with your Telegram user ID
   (find it via [@userinfobot](https://t.me/userinfobot))
5. In the HTTP Request nodes, replace `YOUR_SERVER_IP` with your server's IP address
6. Click **Publish** to activate the workflow

## How the Pipeline Works

```
Telegram message
       │
       ▼
Detect Content Type
  ┌────┴────┬──────────┐
media      url        text
  │         │           │
Whisper   yt-dlp     direct
  │       + Whisper     │
  └────┬────┘           │
       ▼                │
  llama.cpp             │
  classification ◄──────┘
       │
  ┌────┴──────┬──────────┐
note/task  question    plain
  │           │           │
Format      Agent       Agent
Note        Answer      Answer
  │           │           │
Obsidian   Telegram   Telegram
```

| Input type | Processing |
|---|---|
| 🎤 Voice / audio / video | Whisper transcription → classification |
| 🔗 YouTube / TikTok / Vimeo | yt-dlp download → Whisper → classification |
| 💬 Text | Sent directly to classification |

| Classification | Result |
|---|---|
| `note` / `task` | Formatted as Obsidian markdown, saved by category |
| `question` / `plain` | OpenRouter LLM replies in Telegram |

## Obsidian Note Structure

```
/obsidian/
  tech/
    llm-optimization-tips.md
  docker/
    docker-compose-networks.md
  personal/
    ...
```

Each note includes frontmatter: `title`, `date`, `category`, `tags`.