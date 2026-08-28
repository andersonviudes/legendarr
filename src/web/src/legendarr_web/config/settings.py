from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    """Runtime configuration for legendarr_web, sourced from environment variables."""

    model_config = SettingsConfigDict(env_prefix="LEGENDARR_", env_file=".env")

    backend_api_url: str = "http://127.0.0.1:8000/api"
    # Same field name/default as `legendarr_backend.config.settings.Settings.data_dir` —
    # both processes read the same `LEGENDARR_DATA_DIR` env var in the single-container
    # `legendarr_bootstrap` deploy. Used only to find `data_dir/posters`, the local poster
    # cache `legendarr_backend` writes to (ROADMAP.md 0.20.0) and this module serves
    # directly via its own `StaticFiles` mount — `legendarr_web` otherwise never touches
    # the filesystem `legendarr_backend` owns.
    data_dir: Path = Field(default=Path("./data"))


@lru_cache
def get_web_settings() -> WebSettings:
    return WebSettings()
