"""Pydantic Settings for the nobodynamed video pipeline."""

import json
import subprocess
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from nobodynamed_video.models import DataMode


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
    # 0 means derive the newest complete year from the selected data source.
    latest_year: int = Field(default=0)
    data_mode: DataMode = Field(default=DataMode.TEST)
    log_level: str = Field(default="INFO")

    # SQLite fixture path used in dev/test when d1_url is empty.
    sqlite_fixture: Path = Field(default=Path("./fixtures/ssa.sqlite"))
    release_dir: Path = Field(default=Path("./releases"))
    _resolved_d1_token: str | None = None

    @property
    def use_sqlite(self) -> bool:
        return not self.d1_url

    def get_d1_token(self) -> str:
        """Return an explicit D1 token or the current Wrangler OAuth token."""
        if self.d1_token:
            return self.d1_token
        if self._resolved_d1_token is not None:
            return self._resolved_d1_token
        self._resolved_d1_token = resolve_wrangler_auth_token()
        return self._resolved_d1_token


def resolve_wrangler_auth_token() -> str:
    """Resolve the current Cloudflare auth token from Wrangler OAuth login."""
    try:
        result = subprocess.run(
            ["wrangler", "auth", "token", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "D1_TOKEN is unset and wrangler is not installed. Run `wrangler login` "
            "or set D1_TOKEN in .env."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        raise RuntimeError(
            "D1_TOKEN is unset and `wrangler auth token` failed. Run `wrangler login` "
            f"or set D1_TOKEN in .env. Details: {stderr or exc}"
        ) from exc

    raw = json.loads(result.stdout)
    token_value = raw.get("token", "") if isinstance(raw, dict) else ""
    token = str(token_value).strip()
    if not token:
        raise RuntimeError(
            "D1_TOKEN is unset and `wrangler auth token` returned an empty token. "
            "Run `wrangler login` or set D1_TOKEN in .env."
        )
    return token


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
