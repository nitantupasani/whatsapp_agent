from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, Header, Request

from backend.config import settings
from integrations.telegram_client import TelegramClient
from runner.agent import TelegramLaptopAgent
from services.ai.openai_adapter import OpenAINLUAdapter
from services.ai.stub import HeuristicNLUAdapter
from services.executor import LocalExecutor
from services.log_store import MessageLogStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-laptop-agent")

app = FastAPI(title="Telegram Laptop Agent")
incoming_queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
logs = MessageLogStore()

telegram = TelegramClient(bot_token=settings.telegram_bot_token)
nlu = OpenAINLUAdapter(settings.openai_api_key, settings.openai_model) if settings.openai_api_key else HeuristicNLUAdapter()
agent = TelegramLaptopAgent(
    nlu=nlu,
    executor=LocalExecutor(
        allowed_root=settings.allowed_root,
        timeout_seconds=settings.command_timeout_seconds,
        max_output_chars=settings.max_output_chars,
    ),
    allowed_commands={cmd.strip() for cmd in settings.allowed_commands.split(",") if cmd.strip()},
)


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(worker())


async def worker() -> None:
    while True:
        chat_id, text = await incoming_queue.get()
        try:
            response = await dispatch_message(chat_id, text)
            logs.add("out", chat_id, response)
            await telegram.send_message(chat_id, response)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process message")
            error_message = f"❌ Internal error: {exc}"
            logs.add("out", chat_id, error_message)
            await telegram.send_message(chat_id, error_message)
        finally:
            incoming_queue.task_done()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)) -> dict[str, bool]:
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("Rejected webhook request: invalid secret token")
        return {"ok": True}

    payload = await request.json()
    extracted = extract_message(payload)
    if not extracted:
        return {"ok": True}

    chat_id, from_id, text = extracted
    logs.add("in", chat_id, text)

    if chat_id != settings.telegram_chat_id:
        logger.info("Ignoring unauthorized chat_id=%s", chat_id)
        return {"ok": True}

    await incoming_queue.put((chat_id, text))
    return {"ok": True}


def extract_message(payload: dict[str, Any]) -> tuple[int, int, str] | None:
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return None

    text = message.get("text")
    chat = message.get("chat", {})
    sender = message.get("from", {})
    if not isinstance(text, str) or "id" not in chat or "id" not in sender:
        return None

    return int(chat["id"]), int(sender["id"]), text.strip()


async def dispatch_message(chat_id: int, text: str) -> str:
    if text.startswith("/status"):
        return "✅ Server is running and webhook is active."

    if text.startswith("/logs"):
        return logs.tail(15)

    if text.startswith("/run"):
        command = text[4:].strip()
        if not command:
            return "Usage: /run <command>"
        return await agent.handle_text(f"run {command}")

    return await agent.handle_text(text)
