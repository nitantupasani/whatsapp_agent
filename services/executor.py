from __future__ import annotations

import asyncio
from pathlib import Path
import shlex


class LocalExecutor:
    def __init__(self, allowed_root: str, timeout_seconds: int, max_output_chars: int) -> None:
        self.allowed_root = Path(allowed_root).resolve()
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def _safe_path(self, raw_path: str) -> Path:
        candidate = (self.allowed_root / raw_path).resolve()
        if self.allowed_root not in candidate.parents and candidate != self.allowed_root:
            raise ValueError("Path escapes allowed root.")
        return candidate

    async def run_command(self, command: str) -> str:
        args = shlex.split(command)
        proc = await asyncio.create_subprocess_exec(
            *args,
            cwd=str(self.allowed_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_seconds)
        except TimeoutError:
            proc.kill()
            return "Command timed out."

        output = (stdout.decode("utf-8", errors="ignore") + stderr.decode("utf-8", errors="ignore")).strip()
        if not output:
            output = f"Command completed with code {proc.returncode}."
        return self._clip(output)

    def list_dir(self, rel_path: str = ".") -> str:
        target = self._safe_path(rel_path)
        if not target.exists() or not target.is_dir():
            return "Directory not found."
        rows = sorted([p.name for p in target.iterdir()])
        return self._clip("\n".join(rows) or "(empty directory)")

    def read_file(self, rel_path: str) -> str:
        target = self._safe_path(rel_path)
        if not target.exists() or not target.is_file():
            return "File not found."
        return self._clip(target.read_text(encoding="utf-8", errors="ignore"))

    def write_file(self, rel_path: str, content: str) -> str:
        target = self._safe_path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {target.relative_to(self.allowed_root)}"

    def _clip(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + "\n... [output truncated]"
