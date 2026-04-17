from __future__ import annotations

import httpx


class TelegramClient:
    def __init__(self, bot_token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(self, chat_id: int, text: str) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )

    async def set_webhook(self, webhook_url: str, secret_token: str = "") -> dict:
        payload: dict[str, str] = {"url": webhook_url}
        if secret_token:
            payload["secret_token"] = secret_token

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/setWebhook", json=payload)
            response.raise_for_status()
            return response.json()
