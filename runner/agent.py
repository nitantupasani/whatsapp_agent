from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid

logger = logging.getLogger("agent")


class ClaudeCodeAgent:
    """Invokes Claude Code CLI with session persistence for multi-turn conversations."""

    SYSTEM_PROMPT = (
        "You are being accessed through a Telegram bot. The user is chatting with you from their phone. "
        "You have full access to their computer and file system.\n\n"
        "SENDING FILES: When the user asks you to send, share, or show them a file, "
        "include the marker [[SEND_FILE:/absolute/path/to/file]] in your response "
        "(one marker per file, on its own line). The bot wrapper will automatically "
        "deliver those files to the user via Telegram. You can send any file from the system. "
        "Do NOT say you cannot send files — you CAN via this marker.\n\n"
        "CREATING FILES: If you create or modify a file that the user should receive, "
        "include the [[SEND_FILE:...]] marker for it too.\n\n"
        "Keep responses concise — Telegram messages have limited screen space."
    )

    # Regex to extract [[SEND_FILE:/path]] markers
    _SEND_FILE_RE = re.compile(r"\[\[SEND_FILE:(.+?)\]\]")

    def __init__(self, project_dir: str, max_turns: int = 50, timeout: int = 600) -> None:
        self.project_dir = project_dir
        self.max_turns = max_turns
        self.timeout = timeout
        # session_key → session UUID for conversation continuity
        self._sessions: dict[str, str] = {}

    def new_session(self, session_key: str) -> None:
        """Start a fresh conversation for this session."""
        self._sessions.pop(session_key, None)

    async def run(self, prompt: str, session_key: str) -> tuple[str, list[str]]:
        """Run a prompt. Returns (text_response, list_of_created_or_modified_file_paths)."""

        session_id = self._sessions.get(session_key)
        is_continuation = session_id is not None

        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--max-turns", str(self.max_turns),
            "--dangerously-skip-permissions",
            "--append-system-prompt", self.SYSTEM_PROMPT,
        ]

        if is_continuation:
            cmd.extend(["--resume", session_id])

        logger.info(
            "Claude Code: session=%s  resume=%s  cwd=%s",
            session_id, is_continuation, self.project_dir,
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )
        except TimeoutError:
            proc.kill()
            return f"⚠️ Claude Code timed out after {self.timeout // 60} minutes.", []

        raw = stdout.decode("utf-8", errors="ignore").strip()
        errors = stderr.decode("utf-8", errors="ignore").strip()

        if proc.returncode != 0 and not raw:
            return f"❌ Claude Code exited with code {proc.returncode}\n{errors}", []

        if not raw:
            return "(Claude Code returned no output)", []

        # Parse JSON output to extract text and file operations
        text, files = self._parse_output(raw)

        # Extract [[SEND_FILE:path]] markers from text
        send_files = self._SEND_FILE_RE.findall(text)
        # Remove markers from the user-facing text
        text = self._SEND_FILE_RE.sub("", text).strip()
        files.extend(send_files)

        # Capture session_id from first response for future resumption
        if not is_continuation:
            try:
                data = json.loads(raw)
                sid = data.get("session_id") if isinstance(data, dict) else None
                if sid:
                    self._sessions[session_key] = sid
            except json.JSONDecodeError:
                pass

        # If text is empty but we have files to send, use a short confirmation
        if not text and files:
            text = f"📎 Sending {len(files)} file(s)"

        return text or "(no output)", files

    def _parse_output(self, raw: str) -> tuple[str, list[str]]:
        """Parse JSON output from Claude Code. Returns (text, modified_files)."""
        files: list[str] = []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: treat as plain text, try to extract file paths
            return raw, self._extract_paths_from_text(raw)

        # JSON output is a single result object
        text = ""
        if isinstance(data, dict):
            # result field contains the assistant's final text
            text = data.get("result", "")

            # cost_usd for logging
            cost = data.get("cost_usd")
            if cost:
                logger.info("Claude Code cost: $%.4f", cost)

            # Extract file paths from the session messages if available
            for msg in data.get("messages", []):
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})
                            if tool_name in ("Write", "Edit", "MultiEdit", "write_file"):
                                path = tool_input.get("file_path") or tool_input.get("path", "")
                                if path:
                                    files.append(path)

        if not text and isinstance(data, str):
            text = data

        return text, files

    @staticmethod
    def _extract_paths_from_text(text: str) -> list[str]:
        """Best-effort extraction of file paths from plain text output."""
        # Match patterns like "Created file.py", "Wrote to src/x.py", "Modified config.yaml"
        patterns = [
            r"(?:Created|Wrote|Modified|Updated|Saved)\s+[`'\"]?([^\s`'\"]+\.\w+)",
            r"(?:wrote|created|saved)\s+(?:to\s+)?[`'\"]?([^\s`'\"]+\.\w+)",
        ]
        paths: list[str] = []
        for pat in patterns:
            paths.extend(re.findall(pat, text, re.IGNORECASE))
        return list(dict.fromkeys(paths))  # dedupe preserving order
