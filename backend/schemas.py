from __future__ import annotations

from pydantic import BaseModel


class TelegramMessage(BaseModel):
    update_id: int
    chat_id: int
    from_id: int
    text: str


class ActionResult(BaseModel):
    ok: bool
    response_text: str


class HealthResponse(BaseModel):
    status: str
