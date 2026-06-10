"""Shared-canvas hyperframe programs for nobodynamed videos."""

from __future__ import annotations

from typing import Any

from nobodynamed_video.models import ProgramType, VideoContext, VideoSpec
from nobodynamed_video.render.hyperframes import Hyperframe, sample_scalar_track
from nobodynamed_video.render.motion import (
    ease_in_out_cubic,
    ease_in_out_sine,
    ease_out_back,
    ease_out_quart,
    lerp,
    triangle_wave,
)

TOTAL_DURATION_S = 18.0
DOT_LAND_T = 8.0
# Collapse starts a beat AFTER the dot lands (not simultaneously) so the landing and
# count-up read clearly in the still-expanded chart before the layout recomposes.
RECOMPOSE_START_T = 9.2
RECOMPOSE_END_T = 10.2

# Frame 0 is the default TikTok cover and the loop-seam landing frame: the
# header and hook headline must be fully readable on it, never faded up from a
# black canvas. The chart fading in from t=0 keeps the opening frames animating
# (distinct hashes, no FROZEN_FRAMES) while the type carries the cover.
HEADER_ALPHA = (Hyperframe(0.0, 1.0),)
DIAGNOSIS_ALPHA = (Hyperframe(0.0, 1.0),)
CHART_ALPHA = (Hyperframe(0.0, 0.0, ease_out_quart), Hyperframe(0.8, 1.0))
CHART_DRAW = (Hyperframe(1.2, 0.0, ease_out_quart), Hyperframe(DOT_LAND_T, 1.0))
DOT_ALPHA = (Hyperframe(DOT_LAND_T, 0.0, ease_out_quart), Hyperframe(DOT_LAND_T + 0.45, 1.0))
DOT_RADIUS = (Hyperframe(DOT_LAND_T, 18.0, ease_out_back), Hyperframe(DOT_LAND_T + 0.45, 12.0))
DOT_RING_ALPHA = (Hyperframe(DOT_LAND_T, 0.7), Hyperframe(DOT_LAND_T + 0.6, 0.0))
DOT_RING_RADIUS = (
    Hyperframe(DOT_LAND_T, 10.0, ease_out_quart),
    Hyperframe(DOT_LAND_T + 0.6, 30.0),
)
LAYOUT_PROGRESS = (
    Hyperframe(RECOMPOSE_START_T, 0.0, ease_in_out_cubic),
    Hyperframe(RECOMPOSE_END_T, 1.0),
)
NARRATIVE_ALPHA = (
    Hyperframe(RECOMPOSE_END_T, 0.0, ease_out_quart),
    Hyperframe(RECOMPOSE_END_T + 0.8, 1.0),
)
SUPPORT_ALPHA = (
    Hyperframe(RECOMPOSE_END_T + 0.5, 0.0, ease_out_quart),
    Hyperframe(RECOMPOSE_END_T + 1.4, 1.0),
)
# Footer fades in linearly over 13.8–15.6s, straddling the start of the CTA window
# (frame 450 = t=15.0s). At t=15.0 it is ~0.67 opacity — clearly present, so the CTA beat
# reads distinctly from the narrative tail — yet still animating through the first CTA
# frames, which keeps them from being byte-identical (avoids FROZEN_FRAMES). Previously it
# began at 15.0s, so the opening CTA frames matched the narrative tail exactly.
FOOTER_ALPHA = (Hyperframe(13.8, 0.0), Hyperframe(15.6, 1.0))
EVENT_ALPHA = (
    Hyperframe(RECOMPOSE_END_T + 0.2, 0.0, ease_out_quart),
    Hyperframe(RECOMPOSE_END_T + 0.8, 1.0),
)
STAT_ALPHA = (Hyperframe(0.8, 0.0, ease_out_quart), Hyperframe(1.6, 1.0))


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
        cards[2] = {"label": "5y growth", "value": f"{ctx.rise_pct}%", "tone": "emerald"}
    elif ctx.program == ProgramType.CULTURAL_EVENT and ctx.killing_event:
        cards[2] = {"label": "Trigger", "value": ctx.killing_event, "tone": "crimson"}
    return cards


def sample_program_frame(
    spec: VideoSpec,
    t: float,
    debug_safe: bool = False,
) -> dict[str, Any]:
    if spec.context is None or spec.hook is None or spec.program is None:
        raise RuntimeError("VideoSpec must have context, hook, and program before rendering")

    ctx = spec.context
    dot_visible = t >= DOT_LAND_T
    layout_progress = sample_scalar_track(LAYOUT_PROGRESS, t) if dot_visible else 0.0
    tracer_wave = triangle_wave(t, 0.7)
    chart_draw_progress = sample_scalar_track(CHART_DRAW, t)
    # Once the landing flash fades, the dot keeps a slow breathing halo — the
    # "barely alive" focal point reads as a faint vital sign, and the 8 px
    # radius swing keeps every frame byte-distinct through the otherwise
    # static narrative beats (no FROZEN_FRAMES).
    halo_t = t - (DOT_LAND_T + 0.7)
    halo_ramp = min(1.0, max(0.0, halo_t / 0.6))
    halo_wave = ease_in_out_sine(triangle_wave(t, 1.6))
    halo_alpha = halo_ramp * lerp(0.10, 0.22, halo_wave)
    halo_radius = lerp(14.0, 22.0, halo_wave)
    count_progress = (
        # Count finishes as the collapse begins, so the hero number lands in the expanded chart.
        ease_out_quart(min(1.0, max(0.0, (t - DOT_LAND_T) / 1.2))) if dot_visible else 0.0
    )

    series = spec.record.series
    if series:
        s_min = series[0].year
        s_max = series[-1].year
        peak_frac = (ctx.peak_year - s_min) / max(s_max - s_min, 1)
    else:
        peak_frac = 0.5
    peak_raw = max(0.0, (chart_draw_progress - peak_frac) / 0.04)
    peak_annotation_alpha = ease_out_quart(min(1.0, peak_raw)) * (1.0 - layout_progress)

    chart_cards = _stats_cards(ctx)
    card_stagger_s = 0.15
    card_alphas = [
        round(sample_scalar_track(STAT_ALPHA, t - card_stagger_s * i), 6)
        for i in range(len(chart_cards))
    ]
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
            "alpha": round(sample_scalar_track(DIAGNOSIS_ALPHA, t), 6),
            "headline": spec.hook.headline,
            "subhead": spec.hook.subhead,
        },
        "chart": {
            "alpha": round(sample_scalar_track(CHART_ALPHA, t), 6),
            "draw_progress": round(chart_draw_progress, 6),
            "tracer_glow_alpha": round(
                lerp(0.14, 0.38, ease_in_out_cubic(tracer_wave)),
                6,
            ),
            "tracer_glow_radius": round(lerp(10.0, 18.0, ease_out_quart(tracer_wave)), 6),
            "dot_visible": dot_visible,
            "dot_alpha": round(sample_scalar_track(DOT_ALPHA, t) if dot_visible else 0.0, 6),
            "dot_radius": round(sample_scalar_track(DOT_RADIUS, t) if dot_visible else 0.0, 6),
            "dot_ring_alpha": round(
                (halo_alpha if halo_t >= 0.0 else sample_scalar_track(DOT_RING_ALPHA, t))
                if dot_visible
                else 0.0,
                6,
            ),
            "dot_ring_radius": round(
                (halo_radius if halo_t >= 0.0 else sample_scalar_track(DOT_RING_RADIUS, t))
                if dot_visible
                else 0.0,
                6,
            ),
            "layout_progress": round(layout_progress, 6),
            "event_alpha": round(sample_scalar_track(EVENT_ALPHA, t), 6)
            if ctx.program == ProgramType.CULTURAL_EVENT and ctx.event_year is not None
            else 0.0,
            "event_year": ctx.event_year,
            "event_label": ctx.killing_event,
            "series": [{"year": point.year, "count": point.count} for point in spec.record.series],
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
        },
        "narrative": {
            "alpha": round(sample_scalar_track(NARRATIVE_ALPHA, t), 6),
            "support_alpha": round(sample_scalar_track(SUPPORT_ALPHA, t), 6),
            "text": ctx.narrative_text,
            "supporting_text": ctx.supporting_text,
        },
        "comparison": {
            "alpha": round(sample_scalar_track(SUPPORT_ALPHA, t), 6),
            "label": "Reference",
            "name": ctx.comparison_name,
        },
        "footer": {
            "alpha": round(sample_scalar_track(FOOTER_ALPHA, t), 6),
            "site": "nobodynamed.com",
            "cta": "Run your name",
            # Breathing pulse on the CTA dot gives the otherwise-static 15–18s tail motion
            # (so frames stay distinct) and makes the CTA beat read as its own moment.
            "dot_alpha": round(lerp(0.5, 1.0, ease_in_out_sine(triangle_wave(t, 1.2))), 6),
        },
        "debug_safe": debug_safe,
    }
