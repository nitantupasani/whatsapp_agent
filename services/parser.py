from __future__ import annotations

import re
import uuid

from backend.schemas import ParsedMessage

COMMANDS = {"apply", "diff", "explain"}


def parse_user_message(user_id: str, raw_text: str, default_repo: str) -> ParsedMessage:
    text = (raw_text or "").strip()
    if not text:
        text = "explain"

    command = "explain"
    prompt = text

    first_token = text.split(maxsplit=1)[0].lower()
    if first_token in COMMANDS:
        command = first_token
        prompt = text[len(first_token) :].strip()

    repo = default_repo
    repo_match = re.search(r"repo=([a-zA-Z0-9_./-]+)", text)
    if repo_match:
        repo = repo_match.group(1)
        prompt = re.sub(r"repo=[a-zA-Z0-9_./-]+", "", prompt).strip()

    session_id = f"{user_id}-{uuid.uuid4().hex[:10]}"
    if command == "apply":
        prompt = prompt or "Apply pending changes"

    return ParsedMessage(
        user_id=user_id,
        command=command,
        prompt=prompt or "No prompt provided",
        repo=repo,
        session_id=session_id,
    )
