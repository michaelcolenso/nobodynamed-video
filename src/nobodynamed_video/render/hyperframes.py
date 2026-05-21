"""Declarative scalar keyframes for deterministic per-frame animation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from nobodynamed_video.render.motion import linear

EasingFn = Callable[[float], float]


@dataclass(frozen=True)
class Hyperframe:
    """A scalar keyframe sampled over scene-local time."""

    time_s: float
    value: float
    ease_to_next: EasingFn = linear


def sample_scalar_track(frames: Sequence[Hyperframe], t: float) -> float:
    """Sample a scalar hyperframe track at scene-local time *t*.

    The track clamps before the first keyframe and after the last one.
    Between keyframes, interpolation uses the starting keyframe's easing
    function for the interval.
    """
    if not frames:
        raise ValueError("sample_scalar_track() requires at least one hyperframe")

    if len(frames) == 1 or t <= frames[0].time_s:
        return frames[0].value

    for idx in range(len(frames) - 1):
        start = frames[idx]
        end = frames[idx + 1]
        if t <= end.time_s:
            duration = end.time_s - start.time_s
            if duration <= 0:
                return end.value
            progress = max(0.0, min(1.0, (t - start.time_s) / duration))
            eased = start.ease_to_next(progress)
            return start.value + (end.value - start.value) * eased

    return frames[-1].value
