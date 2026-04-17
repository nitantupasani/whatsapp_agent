# Telegram Laptop Agent (FastAPI + Local Execution)

Control your laptop from Telegram (phone/iPad) with a secure webhook-based bot.

Architecture:

```text
Telegram -> FastAPI /webhook on your laptop -> AI/Execution layer -> Telegram response
```

---

## Features

- Telegram Bot API integration with **webhook** (not polling).
- FastAPI backend with modular routing:
  - command handler: `/run`, `/status`, `/logs`
  - natural language handler: free text -> AI/heuristic action decision
- Local execution layer that can:
  - run whitelisted shell commands
  - list directories
  - read files
  - write files
- Security guardrails:
  - allowlist of shell commands
  - blocked dangerous tokens
  - allowed filesystem root
  - only one authorized Telegram `chat_id`
  - optional webhook secret validation
- Async processing queue for incoming messages.
- In-memory incoming/outgoing message logs.

---

## Project Structure

```text
.
├── backend/
│   ├── config.py            # .env config loader
│   ├── main.py              # FastAPI app + /webhook
│   └── schemas.py           # response/message schemas
├── integrations/
│   └── telegram_client.py   # Telegram sendMessage + setWebhook
├── runner/
│   └── agent.py             # Agent decision execution logic
├── services/
│   ├── ai/
│   │   ├── base.py
│   │   ├── openai_adapter.py
│   │   └── stub.py
│   ├── executor.py          # local shell/file executor
│   ├── log_store.py         # recent message logs
│   └── sanitizer.py         # command safety checks
├── scripts/
│   └── register_webhook.py  # refresh Telegram webhook after ngrok URL changes
├── .env.example
├── requirements.txt
└── README.md
```

---

## 1) Telegram Bot Setup

1. Open Telegram and message **@BotFather**.
2. Run `/newbot` and copy your bot token.
3. Set this token in `.env` as `TELEGRAM_BOT_TOKEN`.
4. Find your chat ID (send a message to bot first, then inspect incoming payload logs or use Telegram getUpdates temporarily).
5. Put your chat ID in `.env` as `TELEGRAM_CHAT_ID`.

---

## 2) Configuration (.env)

```bash
cp .env.example .env
```

Required values:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY` (optional, fallback heuristic works without it)

Also configurable:

- `ALLOWED_COMMANDS`
- `ALLOWED_ROOT`
- `COMMAND_TIMEOUT_SECONDS`
- `MAX_OUTPUT_CHARS`
- `TELEGRAM_WEBHOOK_SECRET` (optional recommended)

---

## 3) Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

---

## 4) Networking with ngrok + Webhook Registration

Start ngrok:

```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL, then register webhook:

```bash
python scripts/register_webhook.py --base-url https://<your-ngrok-url>
```

This calls Telegram `setWebhook` for:

```text
https://<your-ngrok-url>/webhook
```

### Refresh webhook when ngrok URL changes

Re-run the same command with the new URL:

```bash
python scripts/register_webhook.py --base-url https://<new-ngrok-url>
```

Optional direct curl (Telegram setWebhook):

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://<your-ngrok-url>/webhook"}'
```

---

## 5) Supported Commands in Telegram

- `/status` -> returns server status
- `/logs` -> returns recent incoming/outgoing message logs
- `/run <command>` -> execute whitelisted shell command

Natural language examples:

- `list .`
- `read README.md`
- `write notes/todo.txt:::buy milk`
- `run ls -la`

If `OPENAI_API_KEY` is configured, free text is routed through OpenAI decision logic.
Otherwise, heuristic parser handles common actions.

---

## 6) Safety Model

- Unknown chat IDs are ignored.
- Non-text/malformed updates are ignored without crashing.
- Commands are allowed only if first token is in `ALLOWED_COMMANDS`.
- Dangerous tokens are blocked (`rm`, `sudo`, etc.).
- File operations are restricted to `ALLOWED_ROOT`.
- Long outputs are truncated.

---

## 7) Example Telegram Interactions

### /status

User:

```text
/status
```

Bot:

```text
✅ Server is running and webhook is active.
```

### /run

User:

```text
/run pwd
```

Bot (example):

```text
🧠 Executed:
`pwd`

/Users/you/projects/telegram-laptop-agent
```

### read file

User:

```text
read README.md
```

Bot:

```text
📄 File content (README.md):
<file contents...>
```

---

## 8) Notes for VS Code / Local Machine Integration

- This system executes directly on your host where FastAPI runs.
- You can start/monitor it in VS Code terminal.
- Keep `ALLOWED_COMMANDS` minimal and explicit for safety.

