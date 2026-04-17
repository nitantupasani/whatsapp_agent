from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentDecision:
    action: str
    argument: str


class NLUAdapter:
    async def decide(self, text: str) -> AgentDecision:  # pragma: no cover - interface
        raise NotImplementedError
