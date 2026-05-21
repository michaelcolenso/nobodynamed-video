"""Tests for settings and token resolution."""

from __future__ import annotations

import subprocess

import pytest
from nobodynamed_video.config import Settings, resolve_wrangler_auth_token


def test_settings_use_explicit_d1_token() -> None:
    settings = Settings(d1_url="https://example.com", d1_token="abc123")
    assert settings.get_d1_token() == "abc123"


def test_settings_cache_wrangler_token(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_resolve() -> str:
        nonlocal calls
        calls += 1
        return "oauth-token"

    monkeypatch.setattr("nobodynamed_video.config.resolve_wrangler_auth_token", fake_resolve)
    settings = Settings(d1_url="https://example.com", d1_token="")

    assert settings.get_d1_token() == "oauth-token"
    assert settings.get_d1_token() == "oauth-token"
    assert calls == 1


def test_resolve_wrangler_auth_token_trims_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["wrangler"],
            returncode=0,
            stdout='{"type":"oauth","token":" token "}\n',
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert resolve_wrangler_auth_token() == "token"


def test_resolve_wrangler_auth_token_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, ["wrangler"], stderr="not logged in")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="wrangler login"):
        resolve_wrangler_auth_token()
