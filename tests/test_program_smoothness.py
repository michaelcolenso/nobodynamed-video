"""Continuity regression tests for the shared-canvas hyperframe program.

These guard the *feel* of the animation rather than any single value: every
animated channel is sampled at the real frame cadence and checked for jumps.
A pop on screen is exactly a large frame-to-frame delta, so a threshold per
channel catches regressions (a hard on/off toggle, an easing whose value does
not start where its track starts) that no per-easing unit test would see.
"""

from __future__ import annotations

import pytest
from nobodynamed_video.models import VideoSpec
from nobodynamed_video.render.frame_planner import total_frame_count
from nobodynamed_video.render.programs import sample_program_frame

from tests.test_frame_planner import make_bertha_spec

FPS = 30


def _channel(
    spec: VideoSpec,
    path: tuple[str, ...],
    visible_with: tuple[str, ...] | None = None,
) -> list[float | None]:
    """Sample one prop across every frame of the video.

    *visible_with* names an alpha channel; frames where that alpha is ~0 are
    recorded as None and excluded from the delta check. A geometry channel is
    only allowed to jump while the element it belongs to is invisible — that is
    how one element hands over from, say, the landing ring to the breathing
    halo without anything showing on screen.
    """
    values: list[float | None] = []
    for idx in range(total_frame_count(FPS)):
        frame = sample_program_frame(spec, idx / FPS)
        if visible_with is not None:
            alpha: object = frame
            for key in visible_with:
                alpha = alpha[key]  # type: ignore[index]
            if float(alpha) <= 0.02:  # type: ignore[arg-type]
                values.append(None)
                continue
        node: object = frame
        for key in path:
            node = node[key]  # type: ignore[index]
        values.append(float(node))  # type: ignore[arg-type]
    return values


def _max_delta(values: list[float | None]) -> float:
    """Largest step between two *consecutive on-screen* frames."""
    deltas = [
        abs(b - a)
        for a, b in zip(values, values[1:], strict=False)
        if a is not None and b is not None
    ]
    assert deltas, "channel is never on screen for two frames running"
    return max(deltas)


# Channel → largest tolerated per-frame step. Alphas fade over ≥0.6s, so a
# smootherstep ramp moves at most ~0.11/frame; the pixel channels are sized
# against their own travel.
ALPHA_CHANNELS = [
    ("chart", "alpha"),
    ("chart", "dot_alpha"),
    ("chart", "dot_ring_alpha"),
    ("chart", "tracer_alpha"),
    ("chart", "peak_annotation_alpha"),
    ("chart", "layout_progress"),
    ("stats", "alpha"),
    ("narrative", "alpha"),
    ("narrative", "support_alpha"),
    ("comparison", "alpha"),
    ("footer", "alpha"),
    ("footer", "dot_alpha"),
    ("diagnosis", "alpha"),
    ("chart", "grid_alpha"),
]


@pytest.mark.parametrize("path", ALPHA_CHANNELS, ids=lambda p: "/".join(p))
def test_alpha_channels_never_pop(path: tuple[str, ...]) -> None:
    spec = make_bertha_spec()
    values = _channel(spec, path)
    assert all(value is not None and 0.0 <= value <= 1.0 for value in values)
    assert _max_delta(values) <= 0.15


@pytest.mark.parametrize(
    ("path", "limit", "visible_with"),
    [
        (("chart", "dot_radius"), 2.0, ("chart", "dot_alpha")),
        (("chart", "dot_ring_radius"), 3.0, ("chart", "dot_ring_alpha")),
        (("chart", "tracer_glow_radius"), 1.5, ("chart", "tracer_alpha")),
        (("footer", "dot_radius"), 0.5, None),
        (("narrative", "offset_y"), 4.0, None),
        (("narrative", "support_offset_y"), 3.0, None),
        (("diagnosis", "offset_y"), 2.0, None),
        (("chart", "entrance_offset_y"), 4.0, None),
    ],
    ids=lambda p: "/".join(p) if isinstance(p, tuple) else str(p),
)
def test_pixel_channels_never_jump(
    path: tuple[str, ...], limit: float, visible_with: tuple[str, ...] | None
) -> None:
    spec = make_bertha_spec()
    assert _max_delta(_channel(spec, path, visible_with)) <= limit


def test_stat_cards_stagger_without_popping() -> None:
    spec = make_bertha_spec()
    for index in range(3):
        alphas = [
            sample_program_frame(spec, idx / FPS)["stats"]["card_alphas"][index]
            for idx in range(total_frame_count(FPS))
        ]
        assert _max_delta(alphas) <= 0.15
        assert alphas[0] == 0.0
        assert alphas[-1] == pytest.approx(1.0)


def test_stat_cards_settle_in_as_they_stagger() -> None:
    spec = make_bertha_spec()
    for index in range(3):
        scales = [
            sample_program_frame(spec, idx / FPS)["stats"]["card_scales"][index]
            for idx in range(total_frame_count(FPS))
        ]
        assert all(0.94 <= value <= 1.0 for value in scales)
        assert scales[-1] == 1.0
        assert _max_delta(scales) <= 0.02


def test_opening_cover_moves_without_sacrificing_contrast() -> None:
    """The hook stays opaque while its position visibly settles immediately."""
    spec = make_bertha_spec()
    frames = [sample_program_frame(spec, idx / FPS) for idx in range(4)]

    assert all(frame["diagnosis"]["alpha"] == 1.0 for frame in frames)
    offsets = [frame["diagnosis"]["offset_y"] for frame in frames]
    assert offsets[0] == 0.0
    assert offsets == sorted(offsets, reverse=True)
    assert len(set(offsets)) == len(offsets)


def test_motion_beats_have_deliberate_separation() -> None:
    """Focus, journey, landing, evidence, and CTA must not arrive together."""
    spec = make_bertha_spec()

    focus = sample_program_frame(spec, 0.85)
    journey = sample_program_frame(spec, 3.0)
    landing = sample_program_frame(spec, 6.2)
    evidence = sample_program_frame(spec, 8.4)
    cta = sample_program_frame(spec, 10.2)

    assert focus["chart"]["grid_alpha"] == 1.0
    assert 0.0 < journey["chart"]["draw_progress"] < 1.0
    assert landing["chart"]["dot_alpha"] > landing["chart"]["tracer_alpha"]
    assert evidence["stats"]["card_alphas"][0] == 1.0
    assert evidence["narrative"]["alpha"] > 0.0
    assert cta["footer"]["alpha"] == 1.0


def test_tracer_hands_over_to_the_landing_dot() -> None:
    """The tracer must still be on screen while the landing dot fades up."""
    overlaps = [
        idx / FPS
        for idx in range(total_frame_count(FPS))
        if (frame := sample_program_frame(spec_cache(), idx / FPS))
        and frame["chart"]["tracer_alpha"] > 0.05
        and frame["chart"]["dot_alpha"] > 0.05
    ]
    assert overlaps, "tracer and landing dot never coexist — the handover pops"


def test_count_up_settles_at_the_real_count() -> None:
    spec = make_bertha_spec()
    values = [
        float(sample_program_frame(spec, idx / FPS)["chart"]["count_value"])
        for idx in range(total_frame_count(FPS))
    ]
    assert values[0] == 0.0
    assert values[-1] == float(spec.record.current_count)
    assert all(b >= a for a, b in zip(values, values[1:], strict=False))


_SPEC: VideoSpec | None = None


def spec_cache() -> VideoSpec:
    global _SPEC
    if _SPEC is None:
        _SPEC = make_bertha_spec()
    return _SPEC
