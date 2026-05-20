"""Pydantic Settings for the nobodynamed video pipeline."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    satori_url: str = Field(default="http://localhost:3001")
    d1_url: str = Field(default="")
    d1_token: str = Field(default="")
    out_dir: Path = Field(default=Path("./out"))
    font_dir: Path = Field(default=Path("./satori-service/fonts"))
    latest_year: int = Field(default=2024)
    log_level: str = Field(default="INFO")

    # SQLite fixture path used in dev/test when d1_url is empty.
    sqlite_fixture: Path = Field(default=Path("./fixtures/ssa.sqlite"))

    @property
    def use_sqlite(self) -> bool:
        return not self.d1_url


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
