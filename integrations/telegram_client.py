from __future__ import annotations

import logging
from pathlib import Path

import httpx

_MAX_TG_LENGTH = 4000  # Telegram limit is 4096; leave margin
logger = logging.getLogger("telegram-client")


class TelegramClient:
    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    # ── sending ──────────────────────────────────────────────────────

    async def send_message(
        self, chat_id: int, text: str, *, thread_id: int | None = None,
    ) -> int | None:
        """Send a message (auto-split if too long). Returns first message_id."""
        chunks = self._split(text)
        first_id: int | None = None
        async with httpx.AsyncClient(timeout=20) as client:
            for chunk in chunks:
                body: dict = {"chat_id": chat_id, "text": chunk}
                if thread_id is not None:
                    body["message_thread_id"] = thread_id
                resp = await client.post(f"{self.base_url}/sendMessage", json=body)
                if first_id is None:
                    data = resp.json()
                    first_id = data.get("result", {}).get("message_id")
        return first_id

    async def send_document(
        self, chat_id: int, file_path: Path, caption: str = "", *, thread_id: int | None = None,
    ) -> None:
        """Send a file as a Telegram document."""
        if not file_path.exists() or not file_path.is_file():
            await self.send_message(chat_id, f"❌ File not found: {file_path.name}", thread_id=thread_id)
            return

        if file_path.stat().st_size > 50 * 1024 * 1024:
            await self.send_message(chat_id, f"❌ File too large (>50 MB): {file_path.name}", thread_id=thread_id)
            return

        data: dict[str, str] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption[:1024]
        if thread_id is not None:
            data["message_thread_id"] = str(thread_id)

        async with httpx.AsyncClient(timeout=120) as client:
            with open(file_path, "rb") as f:
                await client.post(
                    f"{self.base_url}/sendDocument",
                    data=data,
                    files={"document": (file_path.name, f)},
                )

    async def send_chat_action(self, chat_id: int, action: str = "typing", *, thread_id: int | None = None) -> None:
        """Send a chat action (e.g. 'typing') to show the bot is working."""
        body: dict = {"chat_id": chat_id, "action": action}
        if thread_id is not None:
            body["message_thread_id"] = thread_id
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{self.base_url}/sendChatAction", json=body)

    async def edit_message(self, chat_id: int, message_id: int, text: str) -> None:
        text = text[:_MAX_TG_LENGTH]
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(
                f"{self.base_url}/editMessageText",
                json={"chat_id": chat_id, "message_id": message_id, "text": text},
            )

    # ── file downloads ───────────────────────────────────────────────

    async def download_file(self, file_id: str, dest: Path) -> bool:
        """Download a Telegram file to *dest*. Returns True on success."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/getFile", json={"file_id": file_id},
            )
            info = resp.json()
            file_path = info.get("result", {}).get("file_path")
            if not file_path:
                logger.error("getFile failed: %s", info)
                return False

            url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            dl = await client.get(url)
            if dl.status_code != 200:
                logger.error("download failed: %s", dl.status_code)
                return False

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(dl.content)
            return True

    # ── forum topics ─────────────────────────────────────────────────

    async def create_forum_topic(self, chat_id: int, name: str) -> int | None:
        """Create a forum topic. Returns the message_thread_id or None."""
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/createForumTopic",
                json={"chat_id": chat_id, "name": name[:128]},
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error("createForumTopic failed: %s", data)
                return None
            return data["result"]["message_thread_id"]

    # ── webhook ──────────────────────────────────────────────────────

    async def set_webhook(self, webhook_url: str, secret_token: str = "") -> dict:
        payload: dict[str, str] = {"url": webhook_url}
        if secret_token:
            payload["secret_token"] = secret_token

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/setWebhook", json=payload)
            response.raise_for_status()
            return response.json()

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _split(text: str, limit: int = _MAX_TG_LENGTH) -> list[str]:
        if len(text) <= limit:
            return [text]
        chunks: list[str] = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            idx = text.rfind("\n", 0, limit)
            if idx == -1:
                idx = limit
            chunks.append(text[:idx])
            text = text[idx:].lstrip("\n")
        return chunks
