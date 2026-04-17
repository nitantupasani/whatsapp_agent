from __future__ import annotations

import argparse
import asyncio
import os

from dotenv import load_dotenv

from integrations.telegram_client import TelegramClient


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Register Telegram webhook URL")
    parser.add_argument("--base-url", required=True, help="Public HTTPS URL, e.g. https://abc123.ngrok-free.app")
    args = parser.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not token:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN in .env")

    webhook_url = args.base_url.rstrip("/") + "/webhook"
    client = TelegramClient(token)
    result = await client.set_webhook(webhook_url, secret_token=secret)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
