"""Shared-canvas hyperframe programs for nobodynamed videos."""

from __future__ import annotations

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
# Collapse starts a beat AFTER the dot lands so the landing reads clearly in
# the still-expanded chart before the layout recomposes to make room for the
# stat cards.
RECOMPOSE_START_T = 5.2
RECOMPOSE_END_T = 5.9

# Frame 0 is the default TikTok cover and the loop-seam landing frame: the
# header and hook headline must be fully readable on it, never faded up from a
# black canvas. The chart fading in from t=0 keeps the opening frames animating
# (distinct hashes, no FROZEN_FRAMES) while the type carries the cover.
HEADER_ALPHA = (Hyperframe(0.0, 1.0),)
DIAGNOSIS_ALPHA = (Hyperframe(0.0, 1.0),)
# Every fade-in below uses smootherstep rather than ease_out_quart. An
# ease-out leaves the hold at full speed, so the element *pops* onto the canvas
# and then creeps the last few percent; smootherstep departs from and arrives
# at its holds with zero velocity and zero acceleration, which is what reads as
# "professional" at 30fps — the seam between a hold and a move disappears.
CHART_ALPHA = (Hyperframe(0.0, 0.0, smootherstep), Hyperframe(0.6, 1.0))
# The sequence is inverted from the original 18s cut: chart motion starts
# almost immediately (t=0.3) UNDER the hook text, instead of holding a static
# title card for 1.2s and only then drawing. Progress is LINEAR — all pacing
# lives in smoothPathD's two-phase weighted mapping; the previous sine easing
# stacked a second nonlinearity on top (slow start crawled the flatline, slow
# end dragged the flat tail) and squeezed the spike from both sides.
CHART_DRAW = (Hyperframe(0.3, 0.0), Hyperframe(DOT_LAND_T, 1.0))
# The landing dot and the travelling tracer cross-fade through the handover
# instead of one vanishing on the frame the other appears. Both sit at the same
# coordinates at t=DOT_LAND_T (the tracer has reached the final point), so the
# 0.3s overlap reads as the tracer *becoming* the dot.
DOT_FADE_LEAD = 0.15
DOT_ALPHA = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 0.0, smootherstep),
    Hyperframe(DOT_LAND_T + 0.45, 1.0),
)
# The tracer also eases *in* over the first 0.45s of the draw, so the dot and
# its glow grow out of the line's origin instead of blinking on at full weight.
TRACER_IN = (Hyperframe(0.3, 0.0, smootherstep), Hyperframe(0.75, 1.0))
TRACER_OUT = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 1.0, smootherstep),
    Hyperframe(DOT_LAND_T + 0.3, 0.0),
)
# The year readout retires *before* the landing callout arrives. Both sit in
# the same corner above the final point, and at the handover they printed on
# top of each other ("2024" under the count). Clearing it by 4.3s — a beat
# ahead of the callout's own fade-in at 4.35s — keeps the corner to one idea
# at a time; the tracer dot itself carries the last stretch of the draw.
TRACER_YEAR_OUT = (
    Hyperframe(DOT_LAND_T - 0.6, 1.0, smootherstep),
    Hyperframe(DOT_LAND_T - 0.2, 0.0),
)
DOT_RADIUS = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 18.0, ease_out_back),
    Hyperframe(DOT_LAND_T + 0.5, 12.0),
)
# The impact ring swells in rather than switching on at full strength — the
# track used to start *at* 0.7, so its first sampled frame was already opaque.
# Expansion and fade now share an ease_out_cubic so the ring never looks like
# it stalled at the end of its travel before blinking out.
DOT_RING_ALPHA = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 0.0, smootherstep),
    Hyperframe(DOT_LAND_T + 0.2, 0.6, ease_out_cubic),
    Hyperframe(DOT_LAND_T + 0.65, 0.0),
)
DOT_RING_RADIUS = (
    Hyperframe(DOT_LAND_T - DOT_FADE_LEAD, 10.0, ease_out_cubic),
    Hyperframe(DOT_LAND_T + 0.65, 30.0),
)
# The recompose moves the largest object on the canvas, so it gets the
# smoothest curve available: smootherstep's zero acceleration at both ends
# means the chart never appears to be tugged into motion or clipped to a stop.
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
# Footer fades in 9.5–10.1s.
# The tighter 0.6s fade (was 0.9s linear) gives 0.9s of hold before the 11s
# cutoff — the endcard reads as a deliberate beat, not a slow drift in.
FOOTER_ALPHA = (Hyperframe(9.5, 0.0, smootherstep), Hyperframe(10.1, 1.0))
# The narrative support line yields to the footer ahead of the endcard: with
# the enlarged type ramp both occupy the same ~150px band at the bottom of the
# collapsed layout and collided. The fade-out (8.8–9.5s) completes before the
# footer fade-in begins, so the two never ghost over each other; the support
# line's facts remain visible on the chart itself.
SUPPORT_OUT = (Hyperframe(8.8, 0.0, smootherstep), Hyperframe(9.5, 1.0))
EVENT_ALPHA = (
    Hyperframe(RECOMPOSE_END_T + 1.3, 0.0, smootherstep),
    Hyperframe(RECOMPOSE_END_T + 1.9, 1.0),
)
# Stat cards ease in after the landing beat and layout recompose.
STAT_ALPHA = (Hyperframe(5.95, 0.0, smootherstep), Hyperframe(6.65, 1.0))


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
    # The dot block turns on with the cross-fade, a beat before the landing.
    dot_visible = t >= DOT_LAND_T - DOT_FADE_LEAD
    layout_progress = sample_scalar_track(LAYOUT_PROGRESS, t)
    # Raised cosine, not a triangle: the glow's radius and alpha now reverse
    # direction with zero velocity, so the tracer pulses instead of ticking.
    tracer_wave = sine_wave(t, 0.9)
    chart_draw_progress = sample_scalar_track(CHART_DRAW, t)
    tracer_in = sample_scalar_track(TRACER_IN, t)
    tracer_alpha = tracer_in * sample_scalar_track(TRACER_OUT, t)
    tracer_year_alpha = tracer_in * sample_scalar_track(TRACER_YEAR_OUT, t)
    # Once the landing flash fades, the dot keeps a slow breathing halo — the
    # "barely alive" focal point reads as a faint vital sign, and the 8 px
    # radius swing keeps every frame byte-distinct through the otherwise
    # static narrative beats (no FROZEN_FRAMES). The ramp is smoothstepped and
    # the wave is a raised cosine, so the breathing arrives without a corner
    # and never reverses direction abruptly.
    # Starts exactly where the impact ring's fade ends, so the single ring
    # element never cuts from one radius to another while it is visible.
    halo_t = t - (DOT_LAND_T + 0.65)
    halo_ramp = smoothstep(halo_t / 0.6)
    halo_retire = 1.0 - smoothstep((halo_t - 2.4) / 0.6)
    halo_wave = sine_wave(halo_t, 1.2)
    halo_alpha = halo_ramp * halo_retire * lerp(0.10, 0.22, halo_wave)
    halo_radius = lerp(14.0, 22.0, halo_wave)
    # Count finishes as the collapse begins, so the hero number lands in the
    # expanded chart. smootherstep rather than ease_out_quart: a counter that
    # starts at full speed and decays looks like it dropped frames at the top,
    # whereas easing in *and* out reads as a dial settling.
    count_progress = smootherstep((t - (DOT_LAND_T - DOT_FADE_LEAD)) / 1.3) if dot_visible else 0.0

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
    chart_cards = _stats_cards(ctx)
    card_stagger_s = 0.15
    card_alphas = [
        round(sample_scalar_track(STAT_ALPHA, t - card_stagger_s * i), 6)
        for i in range(len(chart_cards))
    ]
    # Entrances rise as they fade in. Deriving the offset from the (already
    # eased) alpha keeps the two perfectly in sync: fully transparent sits
    # low, fully opaque has settled into place.
    card_offsets = [round((1.0 - alpha) * 22.0, 6) for alpha in card_alphas]
    narrative_alpha = sample_scalar_track(NARRATIVE_ALPHA, t)
    support_alpha = sample_scalar_track(SUPPORT_ALPHA, t) * (
        1.0 - sample_scalar_track(SUPPORT_OUT, t)
    )
    # Half-cycle out of phase with the dot halo (same 2.4s period): the two
    # breathe against each other instead of throbbing in lockstep.
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
            # Both glow channels ride the same raised cosine — the previous
            # pairing (ease_in_out_cubic on alpha, ease_out_quart on radius)
            # made the halo brighten and swell out of phase, and the quart's
            # non-zero slope at the wave trough put a hard kink in the radius
            # once per cycle.
            "tracer_alpha": round(tracer_alpha, 6),
            "tracer_year_alpha": round(tracer_year_alpha, 6),
            "tracer_glow_alpha": round(lerp(0.14, 0.38, tracer_wave), 6),
            "tracer_glow_radius": round(lerp(10.0, 18.0, tracer_wave), 6),
            # No dot_visible gate on these: every track below starts at its
            # own resting value, so gating only reintroduced the jump (radius
            # snapping 0 → 18 on the frame the block switched on).
            "dot_visible": dot_visible,
            "dot_alpha": round(sample_scalar_track(DOT_ALPHA, t), 6),
            "dot_radius": round(sample_scalar_track(DOT_RADIUS, t), 6),
            "dot_ring_alpha": round(
                halo_alpha if halo_t >= 0.0 else sample_scalar_track(DOT_RING_ALPHA, t), 6
            ),
            "dot_ring_radius": round(
                halo_radius if halo_t >= 0.0 else sample_scalar_track(DOT_RING_RADIUS, t), 6
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
            # Breathing pulse on the CTA dot gives the otherwise-static 15–18s tail motion
            # (so frames stay distinct) and makes the CTA beat read as its own moment.
            # Size and alpha ride the same wave — an echo of the chart dot's vital sign.
            "dot_alpha": round(lerp(0.5, 1.0, footer_wave), 6),
            "dot_radius": round(lerp(9.0, 11.5, footer_wave), 6),
        },
        "debug_safe": debug_safe,
    }
