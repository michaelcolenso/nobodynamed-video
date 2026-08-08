"""Cached Cloudflare Workers AI narration tests with no live API calls."""

import base64
import io
import json
import struct
import wave
from pathlib import Path

import httpx
import pytest
from nobodynamed_video.compose.narration import (
    CloudflareNarrationProvider,
    adaptive_duration,
)
from nobodynamed_video.editorial.story import load_story
from nobodynamed_video.exceptions import NarrationError


def _wav_bytes(duration_s: float = 1.0, sample_rate: int = 8_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\0\0" * int(duration_s * sample_rate))
    return buffer.getvalue()


def _streaming_wav_bytes(duration_s: float = 1.0, sample_rate: int = 8_000) -> bytes:
    wav_bytes = bytearray(_wav_bytes(duration_s, sample_rate))
    wav_bytes[4:8] = struct.pack("<I", 0x7FFF0004)
    wav_bytes[40:44] = struct.pack("<I", 0x7FFEFFC0)
    return bytes(wav_bytes)


@pytest.mark.asyncio
async def test_cloudflare_narration_generates_wav_and_word_cache(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["authorization"] == "Bearer test-token"
        request_payload = json.loads(request.content)
        if request.url.path.endswith("/aura-2-en"):
            assert request_payload == {
                "text": load_story(Path("stories/bertha-2024.yaml")).narration_text,
                "speaker": "luna",
                "encoding": "linear16",
                "container": "wav",
            }
            return httpx.Response(200, content=_wav_bytes())
        assert base64.b64decode(request_payload["audio"]).startswith(b"RIFF")
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "words": [
                        {"word": "One", "start": 0.0, "end": 0.3},
                        {"word": "curve", "start": 0.3, "end": 0.8},
                    ]
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CloudflareNarrationProvider(
        account_id="test-account",
        api_token="test-token",
        cache_dir=tmp_path,
        client=client,
    )
    story = load_story(Path("stories/bertha-2024.yaml"))
    first = await provider.generate(story)
    second = await provider.generate(story)
    await client.aclose()

    assert first.audio_path.exists()
    assert first.provider == "cloudflare-workers-ai"
    assert first.duration_s == 1.0
    assert not first.cache_hit
    assert second.cache_hit
    assert calls == [
        "/client/v4/accounts/test-account/ai/run/@cf/deepgram/aura-2-en",
        "/client/v4/accounts/test-account/ai/run/@cf/openai/whisper-large-v3-turbo",
    ]


@pytest.mark.asyncio
async def test_cloudflare_json_audio_and_vtt_alignment(tmp_path: Path) -> None:
    wav_bytes = _wav_bytes(0.7)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/aura-2-en"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {"audio": base64.b64encode(wav_bytes).decode()},
                },
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"vtt": ("WEBVTT\n\n00:00:00.000 --> 00:00:00.700\n" "This decline\n")},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CloudflareNarrationProvider(
        account_id="test-account",
        api_token="test-token",
        cache_dir=tmp_path,
        client=client,
    )
    artifact = await provider.generate(load_story(Path("stories/bertha-2024.yaml")))
    await client.aclose()

    assert artifact.duration_s == 0.7
    assert [word.word for word in artifact.word_timings] == ["This", "decline"]
    assert artifact.model == "@cf/deepgram/aura-2-en"
    assert artifact.voice == "luna"


@pytest.mark.asyncio
async def test_cloudflare_streaming_wav_uses_actual_pcm_duration(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/aura-2-en"):
            return httpx.Response(200, content=_streaming_wav_bytes(0.75))
        return httpx.Response(200, json={"success": True, "result": {}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CloudflareNarrationProvider(
        account_id="test-account",
        api_token="test-token",
        cache_dir=tmp_path,
        client=client,
    )
    artifact = await provider.generate(load_story(Path("stories/bertha-2024.yaml")))
    await client.aclose()

    assert artifact.duration_s == 0.75


@pytest.mark.asyncio
async def test_cloudflare_cache_recalculates_audio_duration(tmp_path: Path) -> None:
    audio_path = tmp_path / "cached.wav"
    timing_path = tmp_path / "cached.words.json"
    audio_path.write_bytes(_streaming_wav_bytes(0.5))
    timing_path.write_text(
        json.dumps(
            {
                "duration_s": 44_738.0,
                "model": "@cf/deepgram/aura-2-en",
                "voice": "luna",
                "words": [{"word": "test", "start_s": 0.0, "end_s": 0.5}],
            }
        )
    )

    provider = CloudflareNarrationProvider(
        account_id="test-account", api_token="test-token", cache_dir=tmp_path
    )
    artifact = provider._from_cache(audio_path, timing_path)

    assert artifact is not None
    assert artifact.duration_s == 0.5


def test_narration_provider_rejects_missing_cloudflare_credentials(tmp_path: Path) -> None:
    with pytest.raises(NarrationError, match="CLOUDFLARE_ACCOUNT_ID"):
        CloudflareNarrationProvider(account_id="", api_token="token", cache_dir=tmp_path)
    with pytest.raises(NarrationError, match="CLOUDFLARE_API_TOKEN"):
        CloudflareNarrationProvider(account_id="account", api_token="", cache_dir=tmp_path)


def test_adaptive_duration_preserves_target_and_reserves_loop() -> None:
    story = load_story(Path("stories/kunta-2024.yaml"))
    assert adaptive_duration(story, 8.0) == 10.0
    assert adaptive_duration(story, 10.0) == 10.85
    with pytest.raises(NarrationError, match="14s"):
        adaptive_duration(story, 13.5)
