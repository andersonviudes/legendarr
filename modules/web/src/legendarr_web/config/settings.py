from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    """Runtime configuration for legendarr_web, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="LEGENDARR_", env_file=".env")

    backend_api_url: str = "http://127.0.0.1:8000/api"


@lru_cache
def get_web_settings() -> WebSettings:
    return WebSettings()
