from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from redis.asyncio import Redis


class ConversationState:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis: Redis | None = Redis.from_url(redis_url) if redis_url else None
        self._mem: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def append(self, user_id: str, item: dict[str, Any]) -> None:
        if self._redis:
            await self._redis.rpush(f"conversation:{user_id}", json.dumps(item))
            await self._redis.ltrim(f"conversation:{user_id}", -20, -1)
            return

        self._mem[user_id].append(item)
        self._mem[user_id] = self._mem[user_id][-20:]

    async def latest(self, user_id: str) -> list[dict[str, Any]]:
        if self._redis:
            rows = await self._redis.lrange(f"conversation:{user_id}", 0, -1)
            return [json.loads(r) for r in rows]

        return self._mem[user_id]
