from __future__ import annotations

from collections import deque
from datetime import datetime, timezone


class MessageLogStore:
    def __init__(self, max_items: int = 200) -> None:
        self._items: deque[str] = deque(maxlen=max_items)

    def add(self, direction: str, chat_id: int, text: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        clipped = text.replace("\n", " ")[:500]
        self._items.appendleft(f"[{timestamp}] {direction} chat={chat_id} text={clipped}")

    def tail(self, limit: int = 20) -> str:
        if not self._items:
            return "No logs yet."
        return "\n".join(list(self._items)[:limit])
