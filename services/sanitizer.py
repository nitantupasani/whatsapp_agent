from __future__ import annotations

import shlex


DANGEROUS_TOKENS = {
    "rm",
    "sudo",
    "mkfs",
    "shutdown",
    "reboot",
    ":(){:|:&};:",
    "dd",
    "chmod",
    "chown",
}


def sanitize_command(command: str, allowed_commands: set[str]) -> tuple[bool, str]:
    text = command.strip()
    if not text:
        return False, "Command is empty."

    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        return False, f"Invalid command syntax: {exc}"

    if not tokens:
        return False, "Command is empty after parsing."

    binary = tokens[0]
    if binary not in allowed_commands:
        return False, f"Command '{binary}' is not in whitelist."

    lowered = {t.lower() for t in tokens}
    if lowered & DANGEROUS_TOKENS:
        return False, "Command includes blocked token."

    return True, "ok"
