"""Scene protocol — every scene must implement this interface."""

from collections.abc import Iterator
from typing import Any, Protocol


class SceneProtocol(Protocol):
    """A scene knows its duration and how to produce per-frame props."""

    @property
    def kind(self) -> str: ...

    @property
    def duration_s(self) -> float: ...

    @property
    def template_name(self) -> str: ...

    def props_at(self, t: float) -> dict[str, Any]:
        """Return the interpolated props dict for time *t* within the scene."""
        ...

    def frames(self, fps: int = 30) -> Iterator[tuple[int, dict[str, Any]]]:
        """Yield (frame_index, props_dict) for every frame of this scene."""
        ...
