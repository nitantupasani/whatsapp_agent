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

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    allowed_root: str = "."
    command_timeout_seconds: int = 20
    max_output_chars: int = 3500
    allowed_commands: str = "ls,pwd,whoami,python,python3,cat,head,tail,echo,date,uname"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("allowed_root")
    @classmethod
    def validate_root(cls, value: str) -> str:
        path = Path(value).expanduser().resolve()
        return str(path)


settings = Settings()
