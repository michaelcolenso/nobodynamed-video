"""Frame planner — converts a VideoSpec into a flat sequence of (frame, props) pairs.

Scene layout at 30 fps:
  hook      : 90 frames  (0.0 – 3.0 s)
  reveal    : 180 frames (0.0 – 6.0 s)
  narrative : 180 frames (0.0 – 6.0 s)
  cta       : 90 frames  (0.0 – 3.0 s)
  ──────────────────────────────────────
  Total     : 540 frames (18.0 s)

Each scene's props_at(t) is called for t = frame / fps.
"""

from __future__ import annotations

import random
from typing import Any, Iterator

from nobodynamed_video.models import NameRecord, Tier, VideoSpec
from nobodynamed_video.render.motion import (
    cta_dot_alpha,
    ease_in_out_cubic,
    ease_out_quart,
    lerp,
    lerp_int,
    progress_in_window,
)

# ── Per-scene durations ───────────────────────────────────────────────────────

SCENE_DURATIONS: dict[str, float] = {
    "hook":      3.0,
    "reveal":    6.0,
    "narrative": 6.0,
    "cta":       3.0,
}
SCENE_ORDER = ["hook", "reveal", "narrative", "cta"]
TOTAL_DURATION_S: float = sum(SCENE_DURATIONS[k] for k in SCENE_ORDER)  # 18.0


def frame_count(scene_kind: str, fps: int = 30) -> int:
    return round(SCENE_DURATIONS[scene_kind] * fps)


def total_frame_count(fps: int = 30) -> int:
    return sum(frame_count(k, fps) for k in SCENE_ORDER)


# ── Story generator ───────────────────────────────────────────────────────────

_STORY_TEMPLATES: dict[Tier, str] = {
    Tier.EXTINCT: (
        "By {year}, not a single parent in America chose the name {name}."
    ),
    Tier.CRITICAL: (
        "Once beloved by thousands, {name} now teeters on the edge of extinction."
    ),
    Tier.DECLINING: (
        "{name} peaked at {peak_count:,} in {peak_year} — and hasn't stopped falling since."
    ),
    Tier.STABLE: (
        "{name} quietly holds its ground, year after year, unbothered by trends."
    ),
    Tier.RISING: (
        "{name} is having a moment — up sharply in the last five years."
    ),
    Tier.RESURRECTED: (
        "Written off for dead, {name} is back — and parents are choosing it again."
    ),
}


def _make_story(record: NameRecord, tier: Tier) -> str:
    template = _STORY_TEMPLATES[tier]
    return template.format(
        name=record.name,
        year=record.current_year,
        peak_count=record.peak_count,
        peak_year=record.peak_year,
    )


def _make_subhead(record: NameRecord, tier: Tier) -> str:
    if tier in (Tier.EXTINCT, Tier.CRITICAL):
        return f"Nobody named their baby {record.name} in {record.current_year}."
    if tier == Tier.RESURRECTED:
        return f"{record.name} came back from the dead."
    if tier == Tier.RISING:
        return f"{record.name} is rising fast."
    return f"The story of {record.name}."


# ── Per-scene props builders ──────────────────────────────────────────────────


def _hook_props(t: float, spec: VideoSpec, debug_safe: bool = False) -> dict[str, Any]:
    name = spec.record.name
    # Type-on: full name revealed by t=1.0s using ease_out_quart.
    type_progress = ease_out_quart(progress_in_window(t, 0.0, 1.0))
    chars = lerp_int(0, len(name), type_progress)
    # Subhead fades in at t=1.5s over 0.4s.
    subhead_alpha = ease_out_quart(progress_in_window(t, 1.5, 1.9))
    return {
        "name": name,
        "tier": spec.tier.value,
        "headline_chars_visible": chars,
        "subhead_alpha": subhead_alpha,
        "subhead_text": _make_subhead(spec.record, spec.tier),
        "debug_safe": debug_safe,
    }


def _reveal_props(t: float, spec: VideoSpec, debug_safe: bool = False) -> dict[str, Any]:
    record = spec.record
    # Chart line draws left→right 0.0–4.0s linear.
    chart_progress = progress_in_window(t, 0.0, 4.0)
    # Dot appears at t=4.0s.
    dot_visible = t >= 4.0
    # Count-up 4.0–5.5s ease_out_quart.
    count_progress = ease_out_quart(progress_in_window(t, 4.0, 5.5))
    count_value = lerp_int(0, record.current_count, count_progress) if dot_visible else 0
    series = [{"year": yc.year, "count": yc.count} for yc in record.series]
    return {
        "name": record.name,
        "tier": spec.tier.value,
        "series": series,
        "chart_draw_progress": chart_progress,
        "dot_visible": dot_visible,
        "count_value": count_value,
        "current_year": record.current_year,
        "peak_year": record.peak_year,
        "peak_count": record.peak_count,
        "debug_safe": debug_safe,
    }


def _narrative_props(
    t: float, spec: VideoSpec, rng: random.Random, debug_safe: bool = False
) -> dict[str, Any]:
    record = spec.record
    # Ken Burns scale 1.00 → 1.04 over 6.0s ease_in_out_cubic.
    kb_progress = ease_in_out_cubic(t / SCENE_DURATIONS["narrative"])
    kb_scale = lerp(1.00, 1.04, kb_progress)
    # Crossfade in 0.0–0.5s.
    scene_alpha = ease_out_quart(progress_in_window(t, 0.0, 0.5))
    # Ken Burns offsets are seeded (deterministic per spec).
    kb_x = rng.uniform(0.3, 0.7)
    kb_y = rng.uniform(0.3, 0.7)
    return {
        "name": record.name,
        "tier": spec.tier.value,
        "story": _make_story(record, spec.tier),
        "kb_scale": round(kb_scale, 6),
        "kb_x": round(kb_x, 6),
        "kb_y": round(kb_y, 6),
        "scene_alpha": round(scene_alpha, 6),
        "peak_year": record.peak_year,
        "peak_count": record.peak_count,
        "debug_safe": debug_safe,
    }


def _cta_props(t: float, spec: VideoSpec, debug_safe: bool = False) -> dict[str, Any]:
    # Logo fades in 0.0–0.6s.
    logo_alpha = ease_out_quart(progress_in_window(t, 0.0, 0.6))
    # Dot pulses at 1.5s, 2.0s, 2.5s.
    dot_alpha = cta_dot_alpha(t)
    return {
        "tier": spec.tier.value,
        "logo_alpha": round(logo_alpha, 6),
        "dot_alpha": round(dot_alpha, 6),
        "debug_safe": debug_safe,
    }


# ── Main planner ──────────────────────────────────────────────────────────────


def plan_frames(
    spec: VideoSpec,
    fps: int = 30,
    debug_safe: bool = False,
) -> Iterator[tuple[str, int, str, dict[str, Any]]]:
    """Yield (scene_kind, frame_index, template_name, props) for all frames.

    The Ken Burns RNG is seeded from spec.seed so identical specs produce
    identical motion.
    """
    rng = random.Random(spec.seed)

    for scene_kind in SCENE_ORDER:
        n_frames = frame_count(scene_kind, fps)
        template_name = scene_kind
        for i in range(n_frames):
            t = i / fps
            if scene_kind == "hook":
                props = _hook_props(t, spec, debug_safe)
            elif scene_kind == "reveal":
                props = _reveal_props(t, spec, debug_safe)
            elif scene_kind == "narrative":
                props = _narrative_props(t, spec, rng, debug_safe)
            else:  # cta
                props = _cta_props(t, spec, debug_safe)
            yield scene_kind, i, template_name, props
