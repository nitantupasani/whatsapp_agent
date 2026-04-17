from __future__ import annotations

import httpx


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self.access_token = access_token
        self.phone_number_id = phone_number_id

    async def send_text(self, to: str, body: str) -> None:
        if not self.access_token or not self.phone_number_id:
            # Dev mode fallback
            print(f"[WHATSAPP MOCK] To {to}:\n{body}")
            return

        url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body[:4096]},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
