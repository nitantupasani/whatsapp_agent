# WhatsApp Code Assistant (MVP)

A modular system that converts WhatsApp messages into safe coding tasks against isolated Git workspaces.

---

## 1) Architecture Diagram (Text)

```text
+------------------------+        +-----------------------------+
| WhatsApp Cloud API     | -----> | /backend FastAPI Webhook    |
| (incoming webhook)     |        | - verify token handler      |
+------------------------+        | - message intake            |
                                  +-------------+---------------+
                                                |
                                                v
                                  +-----------------------------+
                                  | Task Queue / State          |
                                  | - Redis conversation state  |
                                  | - Async in-process queue    |
                                  +-------------+---------------+
                                                |
                                                v
                                  +-----------------------------+
                                  | /runner Local Agent         |
                                  | - repo workspace isolation  |
                                  | - git branch per session    |
                                  | - apply/diff/explain        |
                                  +-------------+---------------+
                                                |
                                                v
                                  +-----------------------------+
                                  | /services                   |
                                  | - parser                    |
                                  | - git service               |
                                  | - AI adapter abstraction    |
                                  +-------------+---------------+
                                                |
                                                v
+------------------------+        +-----------------------------+
| WhatsApp Cloud API     | <----- | Response Handler            |
| (reply send API)       |        | - summary + files + diff    |
+------------------------+        | - asks for APPLY approval   |
                                  +-----------------------------+
```

---

## 2) Folder Structure

```text
.
├── backend/
│   ├── config.py
│   ├── main.py
│   └── schemas.py
├── integrations/
│   └── whatsapp_client.py
├── repos/
│   └── .gitkeep
├── runner/
│   └── agent.py
├── services/
│   ├── ai/
│   │   ├── base.py
│   │   └── stub.py
│   ├── git_service.py
│   ├── parser.py
│   └── state.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 3) Functional Scope (MVP)

- Receive incoming WhatsApp text messages through webhook.
- Parse command + prompt + optional repo selector.
- Supported commands:
  - `explain` → explanation only
  - `diff` → generate proposed changes + show diff + wait for approval
  - `apply` → apply and commit pending changes
- Maintain conversation history per user.
- Use isolated workspace per repo.
- Create feature branch per session: `feature/whatsapp-{session_id}`.
- Never commit directly to `main`/`master`.

---

## 4) Security / Guardrails

- No arbitrary shell execution from WhatsApp prompts.
- Repo path sanitization to prevent path traversal.
- Writes happen only on explicit `APPLY` flow.
- Commits blocked on `main` and `master`.
- Responses are trimmed to WhatsApp limits.
- Prompt/action history is logged and persisted (Redis or in-memory fallback).

---

## 5) Requirements You Need

## 5.1 Infrastructure / Accounts

1. **Meta Developer account** with WhatsApp Cloud API access.
2. **WhatsApp Business App** configured in Meta dashboard.
3. **Webhook URL** reachable from internet (public HTTPS).
   - For local development use tunnel tooling (e.g. ngrok or cloudflared).
4. **Python 3.11+** (tested with Python 3.12).
5. **Git** installed on host.
6. **Redis (optional but recommended)** for state persistence.

## 5.2 Environment Variables

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Set values:

- `APP_ENV` → `dev` or `prod`
- `REDIS_URL` → e.g. `redis://localhost:6379/0` (optional)
- `WHATSAPP_VERIFY_TOKEN` → token used in Meta webhook verify step
- `WHATSAPP_ACCESS_TOKEN` → permanent/system-user token for send API
- `WHATSAPP_PHONE_NUMBER_ID` → phone number id from Meta dashboard
- `DEFAULT_REPO` → fallback workspace repo name (e.g. `sample-repo`)
- `REPOS_ROOT` → local workspace root (`./repos`)

---

## 6) End-to-End Setup Process

### Step 1: Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Run Redis (optional)

If using Docker:

```bash
docker run --name whatsapp-redis -p 6379:6379 -d redis:7
```

If Redis is unavailable, app will fallback to in-memory state.

### Step 3: Start backend API

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 4: Expose webhook publicly

Example ngrok:

```bash
ngrok http 8000
```

Use HTTPS URL from ngrok as webhook base.

### Step 5: Configure WhatsApp webhook in Meta

Set callback URL:

```text
https://<public-url>/webhook/whatsapp
```

Set verify token:

```text
<WHATSAPP_VERIFY_TOKEN>
```

Subscribe to `messages` webhook field.

### Step 6: Send a test message

To your configured WhatsApp number, send:

```text
diff repo=my-api Add a health endpoint to my FastAPI app
```

Expected behavior:

1. System responds with summary + file list + diff preview.
2. System asks: `Reply APPLY to commit changes.`
3. Send `apply` to commit on feature branch.

---

## 7) How Message Parsing Works

Accepted patterns:

- `explain <prompt>`
- `diff <prompt>`
- `apply`
- `diff repo=my-repo <prompt>`
- `explain repo=platform-api <prompt>`

Rules:

- If command missing, default is `explain`.
- If `repo=` missing, `DEFAULT_REPO` is used.

---

## 8) Runner Behavior

For `diff`:

1. Ensure workspace exists under `REPOS_ROOT`.
2. Ensure branch `feature/whatsapp-{session_id}` exists and checkout.
3. Request proposed changes from AI adapter.
4. Build unified diff without writing files.
5. Cache pending change for the user.
6. Return structured response to WhatsApp.

For `apply`:

1. Load pending change for user.
2. Write files to workspace.
3. Commit changes with generated message.
4. Return commit summary.

---

## 9) AI Layer (Pluggable)

Current MVP uses deterministic stub adapter in `services/ai/stub.py`.

To integrate a real LLM/Copilot-like backend:

1. Implement `AICoder` interface in `services/ai/base.py`.
2. Replace `StubAICoder()` wiring in `backend/main.py`.
3. Keep output contract: summary + file map content.

---

## 10) API Endpoints

- `GET /health` → service health check
- `GET /webhook/whatsapp` → Meta verification
- `POST /webhook/whatsapp` → inbound WhatsApp events

### Verification Example

```bash
curl "http://localhost:8000/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=change-me&hub.challenge=12345"
```

Returns `12345` when token matches.

---

## 11) Operational Process for Production

1. Run API behind reverse proxy (Nginx/Caddy) with HTTPS.
2. Use Redis (not in-memory) for durable conversation history.
3. Use persistent storage for `REPOS_ROOT`.
4. Run service as non-root user.
5. Rotate WhatsApp access token securely (vault/secrets manager).
6. Add monitoring:
   - request logs
   - task failures
   - webhook delivery latency
7. Backup repositories and logs.
8. Add branch cleanup policy for old sessions.

---

## 12) Troubleshooting

### Webhook verify fails (403)

- Ensure `WHATSAPP_VERIFY_TOKEN` in `.env` exactly matches Meta setting.

### Messages received but no replies

- Check `WHATSAPP_ACCESS_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID`.
- Check app logs for `Task failed` output.

### No persistent context

- Ensure Redis is running and `REDIS_URL` is valid.

### APPLY says no pending change

- You must first run `diff ...` from same sender number.

---

## 13) Quick Local Validation Commands

```bash
python -m compileall backend integrations runner services
python - <<'PY'
from backend.main import app
print(app.title)
PY
```

---

## 14) Current Limitations (MVP)

- Pending changes cached in-process; restart clears pending approval state.
- AI provider is deterministic stub (not semantic coding model yet).
- Single API process queue (no distributed worker yet).

---

## 15) Next Improvements

- Replace in-process queue with Celery/RQ/Arq.
- Persist pending changes in Redis/postgres.
- Add user auth + repo ACL (read vs write).
- Multi-repo registry with git clone from remote origins.
- Add Docker Compose and deployment scripts.
