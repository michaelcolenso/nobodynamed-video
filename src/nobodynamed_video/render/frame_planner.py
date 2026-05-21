"""Frame planner — sample one shared-canvas hyperframe program over 18 seconds."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from nobodynamed_video.models import VideoSpec
from nobodynamed_video.render.programs import sample_program_frame

SCENE_DURATIONS: dict[str, float] = {
    "hook": 3.0,
    "reveal": 6.0,
    "narrative": 6.0,
    "cta": 3.0,
}
SCENE_ORDER = ["hook", "reveal", "narrative", "cta"]
TOTAL_DURATION_S: float = sum(SCENE_DURATIONS[kind] for kind in SCENE_ORDER)


def frame_count(scene_kind: str, fps: int = 30) -> int:
    return round(SCENE_DURATIONS[scene_kind] * fps)


def total_frame_count(fps: int = 30) -> int:
    return sum(frame_count(kind, fps) for kind in SCENE_ORDER)


def _scene_for_global_time(t: float) -> tuple[str, float]:
    elapsed = 0.0
    for kind in SCENE_ORDER:
        duration = SCENE_DURATIONS[kind]
        if t < elapsed + duration:
            return kind, t - elapsed
        elapsed += duration
    return SCENE_ORDER[-1], SCENE_DURATIONS[SCENE_ORDER[-1]]


def plan_frames(
    spec: VideoSpec,
    fps: int = 30,
    debug_safe: bool = False,
) -> Iterator[tuple[str, int, str, dict[str, Any]]]:
    """Yield scene bucket, frame index within bucket, template name, and props.

    The video is rendered as one shared-canvas hyperframe program, but scene
    buckets are preserved for frame naming and ffmpeg composition.
    """
    bucket_indices = {kind: 0 for kind in SCENE_ORDER}
    for global_idx in range(total_frame_count(fps)):
        t = global_idx / fps
        scene_kind, _scene_t = _scene_for_global_time(t)
        frame_idx = bucket_indices[scene_kind]
        bucket_indices[scene_kind] += 1
        props = sample_program_frame(spec, t, debug_safe)
        yield scene_kind, frame_idx, "canvas", props
