"""Pluggable narration boundary; providers resolve a finished audio asset."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from nobodynamed_video.models import VideoSpec


class NarrationProvider(Protocol):
    async def resolve(self, spec: VideoSpec) -> Path | None:
        """Return an audio file for the spec, or None for silent AAC."""
        ...


class FileNarrationProvider:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def resolve(self, spec: VideoSpec) -> Path | None:
        del spec
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        return self.path
