from __future__ import annotations

import httpx


class GitHubModelsClient:
    """Thin client for the GitHub Models inference API (OpenAI-compatible).

    Included with GitHub Copilot Pro / Pro+ / Business subscriptions.
    Authenticates with a GitHub Personal Access Token.
    """

    ENDPOINT = "https://models.github.ai/inference/chat/completions"

    def __init__(self, token: str, model: str) -> None:
        self.token = token
        self.model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.ENDPOINT, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
