"""Satori client tests using respx to mock HTTP calls."""

from __future__ import annotations

import pytest
import respx
import httpx

from nobodynamed_video.exceptions import FrameRenderFailed, SatoriUnavailable
from nobodynamed_video.render.satori_client import SatoriClient


FAKE_URL = "http://localhost:3001"
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@respx.mock
@pytest.mark.asyncio
async def test_render_success() -> None:
    respx.get(f"{FAKE_URL}/health").mock(return_value=httpx.Response(200, json={"status": "ok", "satori": "0.10.13", "fonts": ["Source Serif 4 Black"]}))
    respx.post(f"{FAKE_URL}/render").mock(
        return_value=httpx.Response(200, content=FAKE_PNG, headers={"Content-Type": "image/png"})
    )

    async with SatoriClient(FAKE_URL) as client:
        result = await client.render("hook", {"name": "Bertha", "tier": "critical"})

    assert result == FAKE_PNG


@respx.mock
@pytest.mark.asyncio
async def test_render_500_raises_frame_render_failed() -> None:
    respx.get(f"{FAKE_URL}/health").mock(return_value=httpx.Response(200, json={"status": "ok", "satori": "0.10.13", "fonts": []}))
    respx.post(f"{FAKE_URL}/render").mock(
        return_value=httpx.Response(500, json={"error": "Satori crashed"})
    )

    async with SatoriClient(FAKE_URL) as client:
        with pytest.raises(FrameRenderFailed, match="500"):
            await client.render("hook", {})


@respx.mock
@pytest.mark.asyncio
async def test_health_check_failure_raises_satori_unavailable() -> None:
    respx.get(f"{FAKE_URL}/health").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(SatoriUnavailable):
        async with SatoriClient(FAKE_URL):
            pass


@respx.mock
@pytest.mark.asyncio
async def test_get_version() -> None:
    respx.get(f"{FAKE_URL}/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "satori": "0.10.13", "fonts": []})
    )

    async with SatoriClient(FAKE_URL) as client:
        version = await client.get_version()

    assert version == "0.10.13"


@respx.mock
@pytest.mark.asyncio
async def test_unknown_template_raises_frame_render_failed() -> None:
    respx.get(f"{FAKE_URL}/health").mock(return_value=httpx.Response(200, json={"status": "ok", "satori": "0.10.13", "fonts": []}))
    respx.post(f"{FAKE_URL}/render").mock(
        return_value=httpx.Response(400, json={"error": "Unknown template 'bogus'"})
    )

    async with SatoriClient(FAKE_URL) as client:
        with pytest.raises(FrameRenderFailed):
            await client.render("bogus", {})
