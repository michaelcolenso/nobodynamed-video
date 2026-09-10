"""Deterministically fit approved narration audio inside the editorial runtime."""

from __future__ import annotations

import subprocess
import wave
from dataclasses import replace
from pathlib import Path

from nobodynamed_video.compose.narration import (
    CloudflareNarrationProvider,
    NarrationArtifact,
)
from nobodynamed_video.exceptions import NarrationError
from nobodynamed_video.models import StorySpec, WordTiming

# Keep a small margin below adaptive_duration's 13.15s audio limit so
# resampling/frame quantization cannot push a narration back over 14 seconds.
NARRATION_FIT_TARGET_S = 13.0
MAX_NARRATION_SPEEDUP = 1.5


def _wav_file_duration_s(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            frame_size = wav_file.getnchannels() * wav_file.getsampwidth()
            pcm_bytes = wav_file.readframes(wav_file.getnframes())
            frame_count = len(pcm_bytes) // frame_size if frame_size else 0
    except (EOFError, OSError, wave.Error) as exc:
        raise NarrationError("Narration pacing received an invalid WAV file") from exc
    if frame_rate <= 0 or frame_count <= 0:
        raise NarrationError("Narration pacing received empty audio")
    return frame_count / frame_rate


def _scaled_timings(
    words: list[WordTiming], *, source_duration_s: float, target_duration_s: float
) -> list[WordTiming]:
    if source_duration_s <= 0:
        raise NarrationError("Narration pacing requires a positive source duration")
    ratio = target_duration_s / source_duration_s
    return [
        WordTiming(
            word=word.word,
            start_s=min(word.start_s * ratio, target_duration_s),
            end_s=min(word.end_s * ratio, target_duration_s),
        )
        for word in words
    ]


def fit_narration_audio(
    artifact: NarrationArtifact,
    *,
    target_duration_s: float = NARRATION_FIT_TARGET_S,
    max_speedup: float = MAX_NARRATION_SPEEDUP,
) -> NarrationArtifact:
    """Time-compress narration when needed without changing approved text.

    ``atempo`` changes playback rate without changing pitch. Word timings are
    scaled by the measured output/input duration ratio, preserving alignment
    under the same uniform time transformation.
    """
    if artifact.duration_s <= target_duration_s:
        return artifact
    if target_duration_s <= 0 or max_speedup < 1.0:
        raise NarrationError("Invalid narration pacing policy")

    required_speedup = artifact.duration_s / target_duration_s
    if required_speedup > max_speedup:
        raise NarrationError(
            f"Narration needs {required_speedup:.2f}x pacing, above the "
            f"{max_speedup:.2f}x quality ceiling"
        )

    paced_path = artifact.audio_path.with_name(f"{artifact.audio_path.stem}.paced.wav")
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(artifact.audio_path),
                "-filter:a",
                f"atempo={required_speedup:.6f}",
                "-c:a",
                "pcm_s16le",
                str(paced_path),
            ],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise NarrationError("ffmpeg failed while fitting narration duration") from exc

    paced_duration_s = _wav_file_duration_s(paced_path)
    if paced_duration_s > target_duration_s + 0.1:
        raise NarrationError(
            f"Paced narration is still {paced_duration_s:.2f}s; expected about "
            f"{target_duration_s:.2f}s"
        )

    return replace(
        artifact,
        audio_path=paced_path,
        duration_s=round(paced_duration_s, 6),
        word_timings=_scaled_timings(
            artifact.word_timings,
            source_duration_s=artifact.duration_s,
            target_duration_s=paced_duration_s,
        ),
    )


class FitDurationCloudflareNarrationProvider(CloudflareNarrationProvider):
    """Cloudflare narration provider with a bounded post-generation pace fit."""

    async def generate(self, story: StorySpec) -> NarrationArtifact:
        artifact = await super().generate(story)
        return fit_narration_audio(artifact)
