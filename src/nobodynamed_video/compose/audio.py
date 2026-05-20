"""Audio helpers — silent track generation and optional bed mixing."""

from __future__ import annotations

from pathlib import Path


def silent_audio_flags(duration_s: float) -> list[str]:
    """Return ffmpeg input flags that produce a silent stereo track."""
    return [
        "-f", "lavfi",
        "-t", str(duration_s),
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
    ]


def validate_audio_bed(path: Path) -> None:
    """Raise ValueError if the path doesn't look like a usable audio file."""
    if not path.exists():
        raise ValueError(f"Audio bed not found: {path}")
    if path.suffix.lower() not in {".wav", ".mp3", ".aac", ".flac", ".m4a"}:
        raise ValueError(
            f"Unsupported audio format: {path.suffix}. "
            "Use .wav, .mp3, .aac, .flac, or .m4a"
        )
