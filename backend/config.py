from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000

    telegram_bot_token: str = ""
    telegram_chat_id: int
    telegram_webhook_secret: str = ""

    max_agent_turns: int = 50

    # Working directory for Claude – defaults to home dir (system-wide access)
    allowed_root: str = "~"
    command_timeout_seconds: int = 120
    max_output_chars: int = 50_000
    allowed_commands: str = "ls,pwd,whoami,python,python3,cat,head,tail,echo,date,uname,dir,type,where"

    # Telegram message length before converting to PDF
    pdf_threshold: int = 3800

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        path = Path(value).expanduser().resolve()
        return str(path)


settings = Settings()
