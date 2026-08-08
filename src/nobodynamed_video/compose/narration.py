"""Cached Cloudflare Workers AI narration and word-level alignment."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from nobodynamed_video.exceptions import NarrationError
from nobodynamed_video.models import StorySpec, WordTiming


@dataclass(frozen=True)
class NarrationArtifact:
    audio_path: Path
    word_timings: list[WordTiming]
    duration_s: float
    provider: str
    model: str
    voice: str
    cache_hit: bool = False


class NarrationProvider(Protocol):
    async def generate(self, story: StorySpec) -> NarrationArtifact: ...


class CloudflareNarrationProvider:
    """Generate Aura WAV speech and align it with Workers AI Whisper."""

    def __init__(
        self,
        *,
        account_id: str,
        api_token: str,
        cache_dir: Path,
        base_url: str = "https://api.cloudflare.com/client/v4",
        model: str = "@cf/deepgram/aura-2-en",
        transcription_model: str = "@cf/openai/whisper-large-v3-turbo",
        default_voice: str = "luna",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not account_id.strip():
            raise NarrationError(
                "Approved stories require CLOUDFLARE_ACCOUNT_ID for Workers AI narration."
            )
        if not api_token.strip():
            raise NarrationError(
                "Approved stories require CLOUDFLARE_API_TOKEN for Workers AI narration; "
                "set it in the environment or gitignored .env."
            )
        self.account_id = account_id.strip()
        self._api_token = api_token.strip()
        self.cache_dir = cache_dir
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.transcription_model = transcription_model.strip()
        self.default_voice = default_voice.strip()
        self._client = client

    def _model_url(self, model: str) -> str:
        return f"{self.base_url}/accounts/{self.account_id}/ai/run/{model}"

    def _cache_key(self, story: StorySpec, voice: str) -> str:
        payload = json.dumps(
            {
                "provider": "cloudflare-workers-ai",
                "account_id": self.account_id,
                "model": self.model,
                "transcription_model": self.transcription_model,
                "voice": voice,
                "text": story.narration_text,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _from_cache(self, audio_path: Path, timing_path: Path) -> NarrationArtifact | None:
        if not audio_path.exists() or not timing_path.exists():
            return None
        try:
            raw = json.loads(timing_path.read_text())
            words = [WordTiming.model_validate(item) for item in raw["words"]]
            # Aura streams WAV responses with placeholder RIFF/data sizes. Older
            # cache entries may therefore contain a duration derived from the
            # placeholder instead of the bytes actually present on disk.
            duration_s = _wav_duration_s(audio_path.read_bytes())
            model = str(raw["model"])
            voice = str(raw["voice"])
        except (EOFError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return NarrationArtifact(
            audio_path=audio_path,
            word_timings=words,
            duration_s=duration_s,
            provider="cloudflare-workers-ai",
            model=model,
            voice=voice,
            cache_hit=True,
        )

    async def generate(self, story: StorySpec) -> NarrationArtifact:
        voice = story.voice or self.default_voice
        key = self._cache_key(story, voice)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        audio_path = self.cache_dir / f"{key}.wav"
        timing_path = self.cache_dir / f"{key}.words.json"
        cached = self._from_cache(audio_path, timing_path)
        if cached:
            return cached

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(90.0))
        try:
            speech = await client.post(
                self._model_url(self.model),
                headers=headers,
                json={
                    "text": story.narration_text,
                    "speaker": voice,
                    "encoding": "linear16",
                    "container": "wav",
                },
            )
            if speech.status_code >= 400:
                raise NarrationError(
                    f"Cloudflare Workers AI speech request failed ({speech.status_code})"
                )
            wav_bytes = _extract_wav_bytes(speech)
            duration_s = _wav_duration_s(wav_bytes)

            transcription = await client.post(
                self._model_url(self.transcription_model),
                headers=headers,
                json={
                    "audio": base64.b64encode(wav_bytes).decode(),
                    "task": "transcribe",
                    "language": "en",
                    "vad_filter": False,
                    "initial_prompt": story.narration_text,
                },
            )
            if transcription.status_code >= 400:
                raise NarrationError(
                    "Cloudflare Workers AI transcription request failed "
                    f"({transcription.status_code})"
                )
            payload = _unwrap_cloudflare(transcription.json())
        except httpx.HTTPError as exc:
            raise NarrationError(
                f"Cloudflare Workers AI request failed: {type(exc).__name__}"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        words = _extract_word_timings(payload, story.narration_text, duration_s)
        if not words:
            raise NarrationError("Cloudflare transcription returned no usable timing data")

        audio_path.write_bytes(wav_bytes)
        timing_path.write_text(
            json.dumps(
                {
                    "provider": "cloudflare-workers-ai",
                    "model": self.model,
                    "voice": voice,
                    "duration_s": duration_s,
                    "words": [word.model_dump() for word in words],
                },
                indent=2,
            )
            + "\n"
        )
        return NarrationArtifact(
            audio_path=audio_path,
            word_timings=words,
            duration_s=duration_s,
            provider="cloudflare-workers-ai",
            model=self.model,
            voice=voice,
        )


def _unwrap_cloudflare(payload: object) -> object:
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]
    return payload


def _extract_wav_bytes(response: httpx.Response) -> bytes:
    if response.content.startswith(b"RIFF"):
        return response.content

    try:
        payload = _unwrap_cloudflare(response.json())
    except (json.JSONDecodeError, ValueError):
        payload = None

    candidates: list[object] = [payload]
    if isinstance(payload, dict):
        candidates.extend(payload.get(key) for key in ("audio", "audio_base64", "data"))
    for candidate in candidates:
        if isinstance(candidate, list) and all(isinstance(item, int) for item in candidate):
            decoded = bytes(candidate)
        elif isinstance(candidate, str):
            encoded = candidate.split(",", 1)[-1] if candidate.startswith("data:") else candidate
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except ValueError:
                continue
        else:
            continue
        if decoded.startswith(b"RIFF"):
            return decoded
    raise NarrationError("Cloudflare speech response was not a usable WAV file")


def _wav_duration_s(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            frame_size = wav_file.getnchannels() * wav_file.getsampwidth()
            # Cloudflare/Deepgram use oversized RIFF and data chunk lengths for
            # streamed WAV output. Reading through EOF gives the real PCM byte
            # count while still working for ordinary WAV files.
            pcm_bytes = wav_file.readframes(wav_file.getnframes())
            frame_count = len(pcm_bytes) // frame_size if frame_size else 0
            duration_s = frame_count / frame_rate if frame_rate else 0.0
    except (EOFError, wave.Error) as exc:
        raise NarrationError("Cloudflare speech response contained an invalid WAV") from exc
    if duration_s <= 0:
        raise NarrationError("Cloudflare speech response contained empty audio")
    return round(duration_s, 6)


def _extract_word_timings(
    payload: object, narration_text: str, duration_s: float
) -> list[WordTiming]:
    """Normalize Workers AI words, segments, or VTT into caption timings."""
    if not isinstance(payload, dict):
        return _spread_words(narration_text, 0.0, duration_s)

    containers = [payload]
    transcription_info = payload.get("transcription_info")
    if isinstance(transcription_info, dict):
        containers.append(transcription_info)
    for container in containers:
        raw_words = container.get("words") or container.get("word_timestamps")
        direct = _parse_direct_words(raw_words)
        if direct:
            return direct

    segments = payload.get("segments")
    if isinstance(segments, list):
        timed: list[WordTiming] = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            direct = _parse_direct_words(segment.get("words"))
            if direct:
                timed.extend(direct)
                continue
            text = segment.get("text")
            start = segment.get("start", segment.get("start_s"))
            end = segment.get("end", segment.get("end_s"))
            if text and start is not None and end is not None:
                timed.extend(_spread_words(str(text), float(start), float(end)))
        if timed:
            return timed

    vtt = payload.get("vtt")
    if isinstance(vtt, str):
        timed = _parse_vtt(vtt)
        if timed:
            return timed
    return _spread_words(narration_text, 0.0, duration_s)


def _parse_direct_words(raw_words: object) -> list[WordTiming]:
    if not isinstance(raw_words, list):
        return []
    words: list[WordTiming] = []
    for item in raw_words:
        if not isinstance(item, dict):
            continue
        text = item.get("word") or item.get("text")
        start = item.get("start", item.get("start_s"))
        end = item.get("end", item.get("end_s"))
        if not text or start is None or end is None:
            continue
        words.append(WordTiming(word=str(text).strip(), start_s=float(start), end_s=float(end)))
    return words


def _spread_words(text: str, start_s: float, end_s: float) -> list[WordTiming]:
    tokens = text.split()
    if not tokens or end_s <= start_s:
        return []
    weights = [max(len(re.sub(r"[^A-Za-z0-9]", "", token)), 1) + 1 for token in tokens]
    weight_sum = sum(weights)
    cursor = start_s
    words: list[WordTiming] = []
    for index, (token, weight) in enumerate(zip(tokens, weights, strict=True)):
        word_end = (
            end_s if index == len(tokens) - 1 else cursor + (end_s - start_s) * weight / weight_sum
        )
        words.append(WordTiming(word=token, start_s=cursor, end_s=word_end))
        cursor = word_end
    return words


_VTT_CUE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+"
    r"(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})\s*\n(?P<text>[^\n]+)"
)


def _parse_vtt(vtt: str) -> list[WordTiming]:
    words: list[WordTiming] = []
    for match in _VTT_CUE.finditer(vtt.replace("\r\n", "\n")):
        words.extend(
            _spread_words(
                match.group("text").strip(),
                _vtt_seconds(match.group("start")),
                _vtt_seconds(match.group("end")),
            )
        )
    return words


def _vtt_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def adaptive_duration(story: StorySpec, narration_duration_s: float) -> float:
    """Fit narration plus a loop beat inside the editorial 9-14 second envelope."""
    required = narration_duration_s + 0.85
    duration = max(story.target_duration_s, required)
    if duration > 14.0:
        raise NarrationError(
            f"{story.id}: narration needs {duration:.2f}s, above the 14s editorial ceiling"
        )
    return round(duration, 3)
