"""Application configuration — reads from environment variables / .env file."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Required
    anthropic_api_key: str = ""
    ghl_api_key: str = ""
    ghl_location_id: str = ""
    admin_api_key: str = "dev-admin-key"

    # Vertical
    active_vertical: str = "real_estate"

    # Claude
    claude_model: str = "claude-sonnet-4-5-20250514"
    max_tokens: int = 1024
    temperature: float = 0.7

    # GHL calendar (optional — only used when vertical has booking_enabled)
    ghl_calendar_id: Optional[str] = None

    # Webhook
    ghl_webhook_secret: Optional[str] = None

    # App
    environment: str = "development"
    log_level: str = "INFO"
    base_url: str = "http://localhost:8000"


settings = Settings()
