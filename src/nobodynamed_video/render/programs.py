"""Shared-canvas hyperframe programs for nobodynamed videos."""

from __future__ import annotations

from typing import Any

from nobodynamed_video.models import ProgramType, VideoContext, VideoSpec, YearCount
from nobodynamed_video.render.hyperframes import Hyperframe, sample_scalar_track
from nobodynamed_video.render.motion import (
    ease_in_out_cubic,
    ease_in_out_sine,
    ease_in_quart,
    ease_out_back,
    ease_out_cubic,
    ease_out_quart,
    lerp,
    progress_in_window,
    triangle_wave,
)

TOTAL_DURATION_S = 11.0
SSA_FIRST_YEAR = 1880
DOT_LAND_T = 4.5
# Collapse starts a beat AFTER the dot lands so the landing reads clearly in
# the still-expanded chart before the layout recomposes to make room for the
# stat cards.
RECOMPOSE_START_T = 4.6
RECOMPOSE_END_T = 5.4

# Frame 0 is the default TikTok cover and the loop-seam landing frame: the
# header and hook headline must be fully readable on it, never faded up from a
# black canvas. The chart fading in from t=0 keeps the opening frames animating
# (distinct hashes, no FROZEN_FRAMES) while the type carries the cover.
HEADER_ALPHA = (Hyperframe(0.0, 1.0),)
DIAGNOSIS_ALPHA = (Hyperframe(0.0, 1.0),)
CHART_ALPHA = (Hyperframe(0.0, 0.0, ease_out_quart), Hyperframe(0.5, 1.0))
# The sequence is inverted from the original 18s cut: chart motion starts
# almost immediately (t=0.3) UNDER the hook text, instead of holding a static
# title card for 1.2s and only then drawing. Progress is LINEAR — all pacing
# lives in smoothPathD's two-phase weighted mapping; the previous sine easing
# stacked a second nonlinearity on top (slow start crawled the flatline, slow
# end dragged the flat tail) and squeezed the spike from both sides.
CHART_DRAW = (Hyperframe(0.3, 0.0), Hyperframe(DOT_LAND_T, 1.0))
DOT_ALPHA = (Hyperframe(DOT_LAND_T, 0.0, ease_out_quart), Hyperframe(DOT_LAND_T + 0.45, 1.0))
DOT_RADIUS = (Hyperframe(DOT_LAND_T, 18.0, ease_out_back), Hyperframe(DOT_LAND_T + 0.45, 12.0))
# Shockwave ring: holds visible briefly then snaps to zero. ease_in_quart
# (slow start, fast finish) keeps the ring readable for the first ~60% then
# accelerates the dissipation — reads as a pulse, not a constant fade.
DOT_RING_ALPHA = (Hyperframe(DOT_LAND_T, 0.7, ease_in_quart), Hyperframe(DOT_LAND_T + 0.6, 0.0))
DOT_RING_RADIUS = (
    Hyperframe(DOT_LAND_T, 10.0, ease_out_quart),
    Hyperframe(DOT_LAND_T + 0.6, 30.0),
)
LAYOUT_PROGRESS = (
    Hyperframe(RECOMPOSE_START_T, 0.0, ease_in_out_cubic),
    Hyperframe(RECOMPOSE_END_T, 1.0),
)
# Text entrances use ease_out_cubic (gentler than ease_out_quart): content
# arrives quickly enough to read but with a more natural deceleration. Quart
# slams 80% of the motion in the first 20% of time, which felt mechanical on
# text elements.
# Metric cards: spring-like entrance with a strict 80ms stagger between
# PEAK YEAR, PEAK BIRTHS, CURRENT. ease_out_back gives the spring feel —
# the 12px rise overshoots slightly past the resting position, then settles.
CARD_START_T = 5.2
CARD_IN_S = 0.5
CARD_STAGGER_S = 0.08
CARD_RISE_PX = 12.0
# Rolling numeric counters (PEAK BIRTHS, CURRENT) run ~400ms with
# deceleration, starting with each card's staggered entrance.
COUNTER_IN_S = 0.4
CARDS_SETTLED_T = CARD_START_T + CARD_STAGGER_S * 2 + CARD_IN_S
# ease_out_back dips below 0 at t=0 (anticipation); normalise so the card
# rise is exactly CARD_RISE_PX end to end.
_CARD_SPRING_NORM = 1.0 - ease_out_back(0.0)
# Reveal timeline anchored at CARD_START_T (user-specified beats): PEAK YEAR
# at 0ms, PEAK BIRTHS at 80ms, CURRENT at 160ms, Text Narrative at 300ms,
# URL/CTA at 450ms. The support line rides in with the narrative beat.
NARRATIVE_DELAY_S = 0.300
CTA_DELAY_S = 0.450
SUPPORT_DELAY_S = 0.300
NARRATIVE_ALPHA = (
    Hyperframe(CARD_START_T + NARRATIVE_DELAY_S, 0.0, ease_out_cubic),
    Hyperframe(CARD_START_T + NARRATIVE_DELAY_S + 0.7, 1.0),
)
SUPPORT_ALPHA = (
    Hyperframe(CARD_START_T + SUPPORT_DELAY_S, 0.0, ease_out_cubic),
    Hyperframe(CARD_START_T + SUPPORT_DELAY_S + 0.8, 1.0),
)
# Footer fades in at CARD_START_T + 450ms with ease_out_quart for a snappier
# CTA entrance. The tighter 0.6s fade (was 0.9s linear) keeps the endcard a
# deliberate beat, not a slow drift in.
FOOTER_ALPHA = (
    Hyperframe(CARD_START_T + CTA_DELAY_S, 0.0, ease_out_quart),
    Hyperframe(CARD_START_T + CTA_DELAY_S + 0.6, 1.0),
)
EVENT_ALPHA = (
    Hyperframe(CARDS_SETTLED_T + 0.35, 0.0, ease_out_cubic),
    Hyperframe(CARDS_SETTLED_T + 1.0, 1.0),
)
# Stat card alpha envelope: ease_out_cubic (gentler than quart) so each card
# is readable quickly without a mechanical slam; the spring feel lives in the
# per-card offsets below, not the opacity.
STAT_ALPHA = (
    Hyperframe(CARD_START_T, 0.0, ease_out_cubic),
    Hyperframe(CARD_START_T + CARD_IN_S, 1.0),
)


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


def _card_display_value(card: dict[str, str], ctx: VideoContext, t: float, start: float) -> str:
    """Roll the numeric counter for PEAK BIRTHS / CURRENT cards.

    Counts up over ~400ms from the card's staggered entrance with ease_out_quart
    deceleration. Non-numeric cards (peak year, growth %, trigger) stay static.
    """
    target = {"Peak births": ctx.peak_count, "Current": ctx.current_count}.get(card["label"])
    if target is None:
        return card["value"]
    progress = progress_in_window(t, start, start + COUNTER_IN_S)
    return f"{round(target * ease_out_quart(progress)):,}"


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
    if series and series[0].year > SSA_FIRST_YEAR:
        # Pad the chart back to 1880 with zeros so the x-domain is always the
        # full record. Without this a 1977 debut starts AT its peak and only
        # the collapse is visible; the flat baseline makes the arrival — the
        # steep rise — the story. Presentation-only: record.series and the
        # classifier are untouched. Matches the blog charts' 1880–2025 domain.
        series = [
            YearCount(year=y, count=0) for y in range(SSA_FIRST_YEAR, series[0].year)
        ] + series
    if series:
        s_min = series[0].year
        s_max = series[-1].year
        peak_frac = (ctx.peak_year - s_min) / max(s_max - s_min, 1)
    else:
        peak_frac = 0.5
    peak_raw = max(0.0, (chart_draw_progress - peak_frac) / 0.04)
    peak_annotation_alpha = ease_out_quart(min(1.0, peak_raw)) * (1.0 - layout_progress)

    chart_cards = _stats_cards(ctx)
    card_alphas: list[float] = []
    card_offsets: list[float] = []
    card_values: list[str] = []
    for i, card in enumerate(chart_cards):
        start = CARD_START_T + CARD_STAGGER_S * i
        progress = progress_in_window(t, start, start + CARD_IN_S)
        card_alphas.append(round(ease_out_cubic(progress), 6))
        # Spring-like rise: ease_out_back overshoots past 1.0 mid-entrance,
        # so the offset dips slightly negative (card pops above its resting
        # spot) before settling — the spring feel, frame-sampled. The track
        # is normalised by ease_out_back's anticipation dip at t=0 so the
        # total rise is exactly CARD_RISE_PX.
        spring = (1.0 - ease_out_back(progress)) / _CARD_SPRING_NORM
        card_offsets.append(round(CARD_RISE_PX * spring, 6))
        card_values.append(_card_display_value(card, ctx, t, start))
    narrative_alpha = sample_scalar_track(NARRATIVE_ALPHA, t)
    support_alpha = sample_scalar_track(SUPPORT_ALPHA, t)
    footer_wave = ease_in_out_sine(triangle_wave(t, 1.2))
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
            # After the recompose the narrative takes over as the editorial
            # focus; dimming the hook block hands attention down the canvas
            # without losing the headline (it stays legible at 0.62).
            "alpha": round(
                sample_scalar_track(DIAGNOSIS_ALPHA, t) * (1.0 - 0.38 * layout_progress), 6
            ),
            "headline": spec.hook.headline,
            "subhead": spec.hook.subhead,
        },
        "chart": {
            "alpha": round(sample_scalar_track(CHART_ALPHA, t), 6),
            "draw_progress": round(chart_draw_progress, 6),
            "draw_duration_s": round(DOT_LAND_T - 0.3, 3),
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
            "card_values": card_values,
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
            # Breathing pulse on the CTA dot gives the otherwise-static 15–18s tail motion
            # (so frames stay distinct) and makes the CTA beat read as its own moment.
            # Size and alpha ride the same wave — an echo of the chart dot's vital sign.
            "dot_alpha": round(lerp(0.5, 1.0, footer_wave), 6),
            "dot_radius": round(lerp(9.0, 11.5, footer_wave), 6),
        },
        "debug_safe": debug_safe,
    }
