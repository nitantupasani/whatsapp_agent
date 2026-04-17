from __future__ import annotations

from services.ai.base import AgentDecision, NLUAdapter


class HeuristicNLUAdapter(NLUAdapter):
    async def decide(self, text: str) -> AgentDecision:
        lowered = text.strip().lower()

        if lowered.startswith("run "):
            return AgentDecision(action="shell", argument=text[4:].strip())

        if lowered.startswith("list"):
            argument = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else "."
            return AgentDecision(action="list_dir", argument=argument)

        if lowered.startswith("read "):
            return AgentDecision(action="read_file", argument=text[5:].strip())

        if lowered.startswith("write ") and ":::" in text:
            return AgentDecision(action="write_file", argument=text[6:].strip())

        return AgentDecision(action="respond", argument=f"I received: {text}")
