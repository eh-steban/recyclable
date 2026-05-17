"""Application configuration loaded from environment variables."""

from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env", extra="ignore"
    )

    database_url: str = ""
    log_level: str = "INFO"
    anthropic_api_key: str = ""


settings = Settings()
