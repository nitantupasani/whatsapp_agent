from __future__ import annotations

import json

import httpx

from services.ai.base import AgentDecision, NLUAdapter


class OpenAINLUAdapter(NLUAdapter):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def decide(self, text: str) -> AgentDecision:
        prompt = (
            "Classify the user request for a local laptop assistant. "
            "Return strict JSON with keys action and argument. "
            "Allowed action: respond, shell, read_file, write_file, list_dir. "
            "For write_file use argument format '<path>:::<content>'."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": text}]},
            ],
            "text": {"format": {"type": "json_object"}},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        raw_text = body.get("output", [{}])[0].get("content", [{}])[0].get("text", "{}")
        data = json.loads(raw_text)
        action = data.get("action", "respond")
        argument = data.get("argument", text)
        return AgentDecision(action=action, argument=argument)
