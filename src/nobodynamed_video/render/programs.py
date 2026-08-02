"""Shared-canvas hyperframe programs for nobodynamed videos."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from nobodynamed_video.models import ProgramType, VideoContext, VideoSpec, YearCount
from nobodynamed_video.render.hyperframes import Hyperframe, sample_scalar_track
from nobodynamed_video.render.motion import (
    ease_out_back,
    ease_out_cubic,
    lerp,
    sine_wave,
    smootherstep,
    smoothstep,
)

TOTAL_DURATION_S = 11.0
SSA_FIRST_YEAR = 1880
DOT_LAND_T = 4.5
RECOMPOSE_START_T = 4.6
RECOMPOSE_END_T = 5.4

ONE_HIT_RISE_RATIO = 0.60
ONE_HIT_RISE_STEPS = 12
ONE_HIT_HOLD_STEPS = 6
ONE_HIT_HOLD_YEAR_SPAN = 0.20


@dataclass(frozen=True)
class RenderPoint:
    year: float
    count: float


HEADER_ALPHA = (Hyperframe(0.0, 1.0),)
DIAGNOSIS_ALPHA = (Hyperframe(0.0, 1.0),)
CHART_ALPHA = (Hyperframe(0.0, 0.0, smootherstep), Hyperframe(0.6, 1.0))
CHART_DRAW = (Hyperframe(0.3, 0.0), Hyperframe(DOT_LAND_T, 1.0))
DOT_FADE_LEAD = 0.15
DOT_ALPHA = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 0.0, smootherstep),
    Hyperframe(DOT_LAND_T + 0.45, 1.0),
)
TRACER_IN = (Hyperframe(0.3, 0.0, smootherstep), Hyperframe(0.75, 1.0))
TRACER_OUT = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 1.0, smootherstep),
    Hyperframe(DOT_LAND_T + 0.3, 0.0),
)
TRACER_YEAR_OUT = (
    Hyperframe(DOT_LAND_T - 0.6, 1.0, smootherstep),
    Hyperframe(DOT_LAND_T - 0.2, 0.0),
)
DOT_RADIUS = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 18.0, ease_out_back),
    Hyperframe(DOT_LAND_T + 0.5, 12.0),
)
DOT_RING_ALPHA = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 0.0, smootherstep),
    Hyperframe(DOT_LAND_T + 0.2, 0.6, ease_out_cubic),
    Hyperframe(DOT_LAND_T + 0.8, 0.0),
)
DOT_RING_RADIUS = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 10.0, ease_out_cubic),
    Hyperframe(DOT_LAND_T + 0.8, 30.0),
)
LAYOUT_PROGRESS = (
    Hyperframe(RECOMPOSE_START_T, 0.0, smootherstep),
    Hyperframe(RECOMPOSE_END_T, 1.0),
)
NARRATIVE_ALPHA = (
    Hyperframe(RECOMPOSE_END_T + 1.1, 0.0, smootherstep),
    Hyperframe(RECOMPOSE_END_T + 1.8, 1.0),
)
SUPPORT_ALPHA = (
    Hyperframe(RECOMPOSE_END_T + 1.6, 0.0, smootherstep),
    Hyperframe(RECOMPOSE_END_T + 2.4, 1.0),
)
FOOTER_ALPHA = (Hyperframe(9.5, 0.0, smootherstep), Hyperframe(10.1, 1.0))
SUPPORT_OUT = (Hyperframe(8.8, 0.0, smootherstep), Hyperframe(9.5, 1.0))
EVENT_ALPHA = (
    Hyperframe(RECOMPOSE_END_T + 1.3, 0.0, smootherstep),
    Hyperframe(RECOMPOSE_END_T + 1.9, 1.0),
)
STAT_ALPHA = (Hyperframe(5.2, 0.0, smootherstep), Hyperframe(6.0, 1.0))


def _status_label(ctx: VideoContext) -> str:
    if ctx.program == ProgramType.RETURN_NOTICE:
        return "RETURN NOTICE"
    if ctx.program == ProgramType.CULTURAL_EVENT:
        return "CULTURAL EVENT"
    return "CASE FILE"


def _stats_cards(ctx: VideoContext) -> list[dict[str, str]]:
    cards = [
        {"label": "Peak year", "value": str(ctx.peak_year), "tone": "fade"},
        {"label": "Peak births", "value": f"{ctx.peak_count:,}", "tone": "ink"},
        {"label": "Current", "value": f"{ctx.current_count:,}", "tone": "crimson"},
    ]
    if ctx.program == ProgramType.RETURN_NOTICE:
        cards[2] = {
            "label": "5y growth",
            "value": f"{ctx.rise_pct}%",
            "tone": "emerald",
        }
    elif ctx.program == ProgramType.CULTURAL_EVENT and ctx.killing_event:
        cards[2] = {"label": "Trigger", "value": ctx.killing_event, "tone": "crimson"}
    return cards


def _prepare_render_series(
    source: Sequence[YearCount],
    peak_year: int,
    peak_count: int,
) -> list[RenderPoint]:
    """Add render-only temporal resolution around extreme one-year spikes."""
    if not source:
        return []

    points = [
        RenderPoint(float(point.year), float(point.count)) for point in source
    ]
    if points[0].year > SSA_FIRST_YEAR:
        points = [
            RenderPoint(float(year), 0.0)
            for year in range(SSA_FIRST_YEAR, int(points[0].year))
        ] + points

    peak_index = next(
        (index for index, point in enumerate(points) if point.year == peak_year),
        -1,
    )
    if peak_index <= 0 or peak_count <= 0:
        return points

    previous = points[peak_index - 1]
    peak = points[peak_index]
    year_gap = peak.year - previous.year
    rise_ratio = (peak.count - previous.count) / max(peak.count, 1.0)
    if year_gap <= 0 or year_gap > 1.01 or rise_ratio < ONE_HIT_RISE_RATIO:
        return points

    expanded = points[:peak_index]
    for step in range(1, ONE_HIT_RISE_STEPS + 1):
        progress = step / ONE_HIT_RISE_STEPS
        expanded.append(
            RenderPoint(
                lerp(previous.year, peak.year, progress),
                lerp(previous.count, peak.count, smootherstep(progress)),
            )
        )
    for step in range(1, ONE_HIT_HOLD_STEPS + 1):
        expanded.append(
            RenderPoint(
                peak.year + ONE_HIT_HOLD_YEAR_SPAN * step / ONE_HIT_HOLD_STEPS,
                peak.count,
            )
        )
    expanded.extend(points[peak_index + 1 :])
    return expanded


def sample_program_frame(
    spec: VideoSpec,
    t: float,
    debug_safe: bool = False,
) -> dict[str, Any]:
    if spec.context is None or spec.hook is None or spec.program is None:
        raise RuntimeError("VideoSpec must have context, hook, and program before rendering")

    ctx = spec.context
    dot_visible = t >= DOT_LAND_T - DOT_FADE_LEAD
    layout_progress = sample_scalar_track(LAYOUT_PROGRESS, t)
    tracer_wave = sine_wave(t, 0.9)
    chart_draw_progress = sample_scalar_track(CHART_DRAW, t)
    tracer_in = sample_scalar_track(TRACER_IN, t)
    tracer_alpha = tracer_in * sample_scalar_track(TRACER_OUT, t)
    tracer_year_alpha = tracer_in * sample_scalar_track(TRACER_YEAR_OUT, t)

    halo_t = t - (DOT_LAND_T + 0.8)
    halo_ramp = smoothstep(halo_t / 0.6)
    halo_wave = sine_wave(t, 2.4)
    halo_alpha = halo_ramp * lerp(0.10, 0.22, halo_wave)
    halo_radius = lerp(14.0, 22.0, halo_wave)
    count_progress = (
        smootherstep((t - (DOT_LAND_T - DOT_FADE_LEAD)) / 1.3)
        if dot_visible
        else 0.0
    )

    series = _prepare_render_series(spec.record.series, ctx.peak_year, ctx.peak_count)
    if series:
        s_min = series[0].year
        s_max = series[-1].year
        peak_frac = (ctx.peak_year - s_min) / max(s_max - s_min, 1.0)
    else:
        peak_frac = 0.5

    peak_raw = smoothstep((chart_draw_progress - peak_frac) / 0.14)
    peak_annotation_alpha = peak_raw * (1.0 - layout_progress)

    chart_cards = _stats_cards(ctx)
    card_stagger_s = 0.15
    card_alphas = [
        round(sample_scalar_track(STAT_ALPHA, t - card_stagger_s * index), 6)
        for index in range(len(chart_cards))
    ]
    card_offsets = [round((1.0 - alpha) * 22.0, 6) for alpha in card_alphas]
    narrative_alpha = sample_scalar_track(NARRATIVE_ALPHA, t)
    support_alpha = sample_scalar_track(SUPPORT_ALPHA, t) * (
        1.0 - sample_scalar_track(SUPPORT_OUT, t)
    )
    footer_wave = sine_wave(t, 2.4, phase=0.5)

    return {
        "program": spec.program.value,
        "register": spec.hook.voice_register,
        "tier": spec.tier.value,
        "header": {
            "alpha": round(sample_scalar_track(HEADER_ALPHA, t), 6),
            "label": _status_label(ctx),
            "name": ctx.name,
            "status": ctx.tier.value.upper(),
        },
        "diagnosis": {
            "alpha": round(
                sample_scalar_track(DIAGNOSIS_ALPHA, t) * (1.0 - 0.38 * layout_progress),
                6,
            ),
            "headline": spec.hook.headline,
            "subhead": spec.hook.subhead,
        },
        "chart": {
            "alpha": round(sample_scalar_track(CHART_ALPHA, t), 6),
            "draw_progress": round(chart_draw_progress, 6),
            "draw_duration_s": round(DOT_LAND_T - 0.3, 3),
            "tracer_alpha": round(tracer_alpha, 6),
            "tracer_year_alpha": round(tracer_year_alpha, 6),
            "tracer_glow_alpha": round(lerp(0.14, 0.38, tracer_wave), 6),
            "tracer_glow_radius": round(lerp(10.0, 18.0, tracer_wave), 6),
            "dot_visible": dot_visible,
            "dot_alpha": round(sample_scalar_track(DOT_ALPHA, t), 6),
            "dot_radius": round(sample_scalar_track(DOT_RADIUS, t), 6),
            "dot_ring_alpha": round(
                halo_alpha if halo_t >= 0.0 else sample_scalar_track(DOT_RING_ALPHA, t),
                6,
            ),
            "dot_ring_radius": round(
                halo_radius if halo_t >= 0.0 else sample_scalar_track(DOT_RING_RADIUS, t),
                6,
            ),
            "layout_progress": round(layout_progress, 6),
            "event_alpha": round(sample_scalar_track(EVENT_ALPHA, t), 6)
            if ctx.program == ProgramType.CULTURAL_EVENT and ctx.event_year is not None
            else 0.0,
            "event_year": ctx.event_year,
            "event_label": ctx.killing_event,
            "series": [{"year": point.year, "count": point.count} for point in series],
            "current_year": ctx.current_year,
            "peak_year": ctx.peak_year,
            "peak_count": ctx.peak_count,
            "count_value": round(spec.record.current_count * count_progress),
            "peak_annotation_alpha": round(peak_annotation_alpha, 6),
        },
        "stats": {
            "alpha": round(sample_scalar_track(STAT_ALPHA, t), 6),
            "cards": chart_cards,
            "card_alphas": card_alphas,
            "card_offsets": card_offsets,
        },
        "narrative": {
            "alpha": round(narrative_alpha, 6),
            "support_alpha": round(support_alpha, 6),
            "offset_y": round((1.0 - narrative_alpha) * 28.0, 6),
            "support_offset_y": round((1.0 - support_alpha) * 20.0, 6),
            "text": ctx.narrative_text,
            "supporting_text": ctx.supporting_text,
        },
        "comparison": {
            "alpha": round(support_alpha, 6),
            "offset_y": round((1.0 - support_alpha) * 20.0, 6),
            "label": "Reference",
            "name": ctx.comparison_name,
        },
        "footer": {
            "alpha": round(sample_scalar_track(FOOTER_ALPHA, t), 6),
            "site": "nobodynamed.com",
            "cta": "Run your name",
            "dot_alpha": round(lerp(0.5, 1.0, footer_wave), 6),
            "dot_radius": round(lerp(9.0, 11.5, footer_wave), 6),
        },
        "debug_safe": debug_safe,
    }
