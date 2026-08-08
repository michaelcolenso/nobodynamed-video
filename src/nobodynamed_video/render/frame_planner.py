"""Frame planner — sample one shared-canvas program over an adaptive timeline."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from nobodynamed_video.models import StoryKind, VideoSpec
from nobodynamed_video.render.programs import sample_program_frame

# Fixed 11.0s runtime for every video: completion rate is the metric that
# matters for this format, and a fixed length makes the series legible.
# Names with better stories earn a second video, not a longer one.
SCENE_DURATIONS: dict[str, float] = {
    "hook": 1.0,
    "reveal": 3.5,
    "narrative": 5.0,
    "cta": 1.5,
}
SCENE_ORDER = ["hook", "reveal", "narrative", "cta"]
TOTAL_DURATION_S: float = sum(SCENE_DURATIONS[kind] for kind in SCENE_ORDER)


def frame_count(scene_kind: str, fps: int = 30) -> int:
    return round(SCENE_DURATIONS[scene_kind] * fps)


def total_frame_count(fps: int = 30, duration_s: float = TOTAL_DURATION_S) -> int:
    return round(duration_s * fps)


def scene_frame_counts(spec: VideoSpec, fps: int = 30) -> dict[str, int]:
    """Allocate frames by story shape while preserving the exact total."""
    if spec.story is None and spec.duration_s == TOTAL_DURATION_S:
        return {kind: frame_count(kind, fps) for kind in SCENE_ORDER}

    total = total_frame_count(fps, spec.duration_s)
    hook = max(1, round(min(0.8, spec.duration_s * 0.08) * fps))
    cta = max(1, round(min(1.4, spec.duration_s * 0.13) * fps))
    middle = total - hook - cta
    reveal_share = (
        {
            StoryKind.ONE_HIT: 0.64,
            StoryKind.CULTURAL_RUPTURE: 0.55,
            StoryKind.LONG_DECLINE: 0.61,
            StoryKind.COMEBACK: 0.57,
        }[spec.story.story_kind]
        if spec.story
        else 0.55
    )
    reveal = round(middle * reveal_share)
    narrative = middle - reveal
    return {"hook": hook, "reveal": reveal, "narrative": narrative, "cta": cta}


def _scene_for_global_frame(global_idx: int, counts: dict[str, int]) -> tuple[str, int]:
    elapsed = 0
    for kind in SCENE_ORDER:
        count = counts[kind]
        if global_idx < elapsed + count:
            return kind, global_idx - elapsed
        elapsed += count
    return SCENE_ORDER[-1], counts[SCENE_ORDER[-1]] - 1


def plan_frames(
    spec: VideoSpec,
    fps: int = 30,
    debug_safe: bool = False,
) -> Iterator[tuple[str, int, str, dict[str, Any]]]:
    """Yield scene bucket, frame index within bucket, template name, and props.

    The video is rendered as one shared-canvas hyperframe program, but scene
    buckets are preserved for frame naming and ffmpeg composition.
    """
    counts = scene_frame_counts(spec, fps)
    for global_idx in range(sum(counts.values())):
        t = global_idx / fps
        scene_kind, frame_idx = _scene_for_global_frame(global_idx, counts)
        props = sample_program_frame(spec, t, debug_safe)
        yield scene_kind, frame_idx, "canvas", props
