from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProposedChange:
    summary: str
    files: dict[str, str]


class AICoder:
    async def propose_changes(self, prompt: str, repo_root: str) -> ProposedChange:  # pragma: no cover - interface
        raise NotImplementedError

    async def explain(self, prompt: str, repo_root: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError
