# Setup: Telegram → Claude Code Agent

One-shot instructions to get this service running on a fresh machine.

## Prerequisites

- Python 3.11+
- Git
- ffmpeg (for voice messages): https://ffmpeg.org/download.html
- ngrok account (free): https://dashboard.ngrok.com/signup
- A Telegram bot token from @BotFather
- Claude Code CLI installed and authenticated

## 1. Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
claude auth login
```

Verify it works:

```bash
claude -p "say hello" --output-format json
```

## 2. Clone and install

```bash
git clone <your-repo-url>
cd whatsapp_agent
pip install -r requirements.txt
```

## 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:

- `TELEGRAM_BOT_TOKEN` — get from @BotFather on Telegram
- `TELEGRAM_CHAT_ID` — your personal chat ID (see step 4)
- `ALLOWED_ROOT` — set to `~` for system-wide access, or a specific directory

Everything else can stay at defaults.

## 4. Find your Telegram Chat ID

1. Message your bot on Telegram (just send "hi")
2. Run:

```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates" | python -m json.tool
```

3. Look for `"chat": {"id": 1234567890}` — that's your chat ID
4. Put it in `.env` as `TELEGRAM_CHAT_ID`

## 5. Install and configure ngrok

```bash
# Install ngrok (or download from https://ngrok.com/download)
# Windows: winget install ngrok.ngrok
# macOS:   brew install ngrok
# Linux:   snap install ngrok

# Set your authtoken (from https://dashboard.ngrok.com/get-started/your-authtoken)
ngrok config add-authtoken <YOUR_AUTHTOKEN>
```

## 6. Start everything

You need three terminals:

**Terminal 1 — FastAPI server:**

```bash
cd whatsapp_agent
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — ngrok tunnel:**

```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.dev` URL from the output.

**Terminal 3 — Register webhook:**

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://xxxx.ngrok-free.dev/webhook"}'
```

You should get `{"ok":true,"result":true,"description":"Webhook was set"}`.

## 7. Test

Send a message to your bot on Telegram. You should see:

1. "Got it ✓" — immediate acknowledgment
2. "typing..." indicator while Claude works
3. The actual response

## Available commands

- `/new [name]` — start a fresh conversation (optionally with a topic name)
- `/file <path>` — request a file from the system
- `/run <command>` — execute a shell command
- `/status` — check bot status
- `/logs` — view recent message log
- Send a voice message — it will be transcribed and processed

## File sending

Ask Claude to send you any file and it will deliver it via Telegram.
Example: "send me the requirements.txt file"

## Notes

- The ngrok URL changes every time you restart ngrok (free tier). Re-register the webhook after each restart.
- Claude runs with `--dangerously-skip-permissions` — it has full system access. Only run this on machines you trust.
- Sessions persist in memory. Restarting the server clears all conversation history.
- Long responses (>3800 chars) are automatically sent as PDF attachments.
