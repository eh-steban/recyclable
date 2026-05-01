"""Application configuration loaded from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://recyclable:recyclable_dev@localhost:5432/recyclable"
    log_level: str = "INFO"
    anthropic_api_key: str = ""


settings = Settings()
