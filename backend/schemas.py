from pydantic import BaseModel


class ParsedMessage(BaseModel):
    user_id: str
    command: str
    prompt: str
    repo: str
    session_id: str


class RunnerResult(BaseModel):
    summary: str
    files_changed: list[str]
    diff: str
    requires_approval: bool = False
    branch: str


class TaskEnvelope(BaseModel):
    parsed: ParsedMessage
