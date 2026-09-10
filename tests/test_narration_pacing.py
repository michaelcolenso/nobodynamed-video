"""Narration pacing tests; ffmpeg is provided by local/CI prerequisites."""

from __future__ import annotations

import io
import wave
from pathlib import Path

import pytest
from nobodynamed_video.compose.narration import NarrationArtifact
from nobodynamed_video.compose.narration_pacing import fit_narration_audio
from nobodynamed_video.exceptions import NarrationError
from nobodynamed_video.models import WordTiming


def _write_wav(path: Path, duration_s: float, sample_rate: int = 8_000) -> None:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\0\0" * int(duration_s * sample_rate))
    path.write_bytes(buffer.getvalue())


def _artifact(path: Path, duration_s: float) -> NarrationArtifact:
    return NarrationArtifact(
        audio_path=path,
        word_timings=[WordTiming(word="test", start_s=0.0, end_s=duration_s)],
        duration_s=duration_s,
        provider="cloudflare-workers-ai",
        model="test-model",
        voice="luna",
    )


def test_short_narration_is_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "short.wav"
    _write_wav(path, 10.0)
    original = _artifact(path, 10.0)

    assert fit_narration_audio(original) is original


def test_long_narration_is_fit_without_changing_words(tmp_path: Path) -> None:
    path = tmp_path / "long.wav"
    _write_wav(path, 18.0)

    paced = fit_narration_audio(_artifact(path, 18.0))

    assert paced.audio_path != path
    assert paced.audio_path.exists()
    assert 12.8 <= paced.duration_s <= 13.1
    assert [word.word for word in paced.word_timings] == ["test"]
    assert paced.word_timings[-1].end_s == pytest.approx(paced.duration_s)


def test_excessive_speedup_is_rejected_before_ffmpeg(tmp_path: Path) -> None:
    path = tmp_path / "too-long.wav"
    _write_wav(path, 20.0)

    with pytest.raises(NarrationError, match="quality ceiling"):
        fit_narration_audio(_artifact(path, 20.0))
