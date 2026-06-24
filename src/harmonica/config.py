from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_harmonica_home() -> Path:
    return Path(os.environ.get("HARMONICA_HOME", ".harmonica")).expanduser().resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HARMONICA_", env_file=".env", extra="ignore")

    app_name: str = "Harmonica"
    home: Path = Field(default_factory=default_harmonica_home)
    database_url: str | None = None
    media_root: Path | None = None
    log_dir: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8765

    beta: float = 1.25
    group_cooldown_floor: float = 0.05
    sub_group_cooldown_floor: float = 0.01
    default_playlist_length: int = 100
    song_rating_min_multiplier: float = 0.5
    song_rating_max_multiplier: float = 2.0
    group_rating_min_multiplier: float = 0.7
    group_rating_max_multiplier: float = 1.4
    enable_group_rating_multiplier: bool = False

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.home / 'harmonica.db'}"

    @property
    def logs_path(self) -> Path:
        return self.log_dir or self.home / "logs"

    def ensure_dirs(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings

