from __future__ import annotations

from services.ai.base import NLUAdapter
from services.executor import LocalExecutor
from services.sanitizer import sanitize_command


class TelegramLaptopAgent:
    def __init__(self, nlu: NLUAdapter, executor: LocalExecutor, allowed_commands: set[str]) -> None:
        self.nlu = nlu
        self.executor = executor
        self.allowed_commands = allowed_commands

    async def handle_text(self, text: str) -> str:
        decision = await self.nlu.decide(text)

        if decision.action == "respond":
            return decision.argument

        if decision.action == "shell":
            ok, reason = sanitize_command(decision.argument, self.allowed_commands)
            if not ok:
                return f"❌ Blocked command: {reason}"
            output = await self.executor.run_command(decision.argument)
            return f"🧠 Executed:\n`{decision.argument}`\n\n{output}"

        if decision.action == "list_dir":
            output = self.executor.list_dir(decision.argument or ".")
            return f"📂 Directory listing ({decision.argument or '.'}):\n{output}"

        if decision.action == "read_file":
            output = self.executor.read_file(decision.argument)
            return f"📄 File content ({decision.argument}):\n{output}"

        if decision.action == "write_file":
            if ":::" not in decision.argument:
                return "❌ write_file action requires '<path>:::<content>' format."
            path, content = decision.argument.split(":::", 1)
            result = self.executor.write_file(path.strip(), content)
            return f"✍️ {result}"

        return "I could not determine an action for this request."
