from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request

from backend.config import settings
from backend.schemas import ParsedMessage
from integrations.whatsapp_client import WhatsAppClient
from runner.agent import RunnerAgent
from services.ai.stub import StubAICoder
from services.git_service import WorkspaceManager
from services.parser import parse_user_message
from services.state import ConversationState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp-agent")

app = FastAPI(title="WhatsApp Code Assistant")
queue: asyncio.Queue[ParsedMessage] = asyncio.Queue()

state = ConversationState(redis_url=settings.redis_url)
whatsapp = WhatsAppClient(
    access_token=settings.whatsapp_access_token,
    phone_number_id=settings.whatsapp_phone_number_id,
)
agent = RunnerAgent(WorkspaceManager(settings.repos_root), StubAICoder())


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(worker())


async def worker() -> None:
    while True:
        parsed = await queue.get()
        try:
            logger.info("Processing session=%s user=%s", parsed.session_id, parsed.user_id)
            result = await agent.run(parsed)
            await state.append(
                parsed.user_id,
                {
                    "session_id": parsed.session_id,
                    "command": parsed.command,
                    "prompt": parsed.prompt,
                    "summary": result.summary,
                    "files_changed": result.files_changed,
                },
            )
            await whatsapp.send_text(parsed.user_id, format_response(result.summary, result.files_changed, result.diff, result.requires_approval))
        except Exception as exc:  # noqa: BLE001
            logger.exception("task failed")
            await whatsapp.send_text(parsed.user_id, f"Task failed: {exc}")
        finally:
            queue.task_done()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return hub_challenge
    raise HTTPException(status_code=403, detail="verification failed")


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request) -> dict[str, bool]:
    payload = await request.json()
    for incoming in extract_incoming_messages(payload):
        parsed = parse_user_message(incoming["from"], incoming["text"], settings.default_repo)
        await queue.put(parsed)
    return {"ok": True}


def extract_incoming_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    entries = payload.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                text = message.get("text", {}).get("body", "")
                sender = message.get("from")
                if sender and text:
                    messages.append({"from": sender, "text": text})
    return messages


def format_response(summary: str, files_changed: list[str], diff_text: str, requires_approval: bool) -> str:
    lines = [f"Summary: {summary}"]
    if files_changed:
        lines.append("Files changed:")
        lines.extend([f"- {f}" for f in files_changed])

    if diff_text:
        clipped = diff_text[:1500]
        lines.append("Diff preview:")
        lines.append(clipped)

    if requires_approval:
        lines.append("Reply APPLY to commit changes.")

    return "\n".join(lines)
