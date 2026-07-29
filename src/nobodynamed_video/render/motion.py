"""Easing functions and interpolation helpers for frame animation.

All easing functions take t ∈ [0, 1] and return a value ∈ [0, 1].
Overshooting easings (ease_out_back) may return values outside [0, 1].
"""

import math

# ── Easing functions ──────────────────────────────────────────────────────────


def linear(t: float) -> float:
    return max(0.0, min(1.0, t))


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    p = -2.0 * t + 2.0
    return 1.0 - (p * p * p) / 2.0


def ease_out_quart(t: float) -> float:
    t = max(0.0, min(1.0, t))
    p = 1.0 - t
    return 1.0 - p * p * p * p


def ease_out_cubic(t: float) -> float:
    """Decelerating easing with a gentler tail than ease_out_quart."""
    t = max(0.0, min(1.0, t))
    p = 1.0 - t
    return 1.0 - p * p * p


def ease_out_back(t: float, overshoot: float = 0.6) -> float:
    """Overshoot beyond 1.0 then settle back — spring-lite easing.

    *overshoot* controls the peak overshoot (0 = none, ~1 = extreme).
    Works like an underdamped spring for UI effects like dot landing.
    Returns values >1.0 in the middle, settling at 1.0.

    Anchored at both ends: f(0) == 0.0 and f(1) == 1.0 exactly. The earlier
    formulation returned -0.5·overshoot at t=0, so every track using it began
    with a one-frame jump away from its own start value — the dot landing
    "popped" before it sprang.
    """
    t = max(0.0, min(1.0, t))
    # 2.83 ≈ the classic back-easing c1 (1.70158) at the default overshoot,
    # so the default keeps the familiar ~10% peak.
    c1 = overshoot * 2.83
    c3 = c1 + 1.0
    p = t - 1.0
    return 1.0 + c3 * p * p * p + c1 * p * p


def ease_in_out_sine(t: float) -> float:
    """Smooth acceleration and deceleration — gentler than cubic."""
    t = max(0.0, min(1.0, t))
    return -(math.cos(math.pi * t) - 1.0) / 2.0


def smoothstep(t: float) -> float:
    """Classic 3t²−2t³ — zero velocity at both ends, no corner on entry/exit."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def smootherstep(t: float) -> float:
    """Perlin's 6t⁵−15t⁴+10t³ — zero velocity *and* acceleration at both ends.

    Preferred wherever a value ramps out of, or into, a hold: it leaves no
    perceptible kink at the seam between the ramp and the static beat.
    """
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


# ── Interpolation helpers ─────────────────────────────────────────────────────


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation from a to b at parameter t."""
    return a + (b - a) * t


def lerp_int(a: int, b: int, t: float) -> int:
    """Integer interpolation — rounds toward the target."""
    return round(lerp(float(a), float(b), t))


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def progress_in_window(t: float, start: float, end: float) -> float:
    """Return t normalised to [0, 1] within the [start, end] window.

    Returns 0.0 before the window, 1.0 after it.
    """
    if end <= start:
        return 1.0
    return clamp((t - start) / (end - start), 0.0, 1.0)


def triangle_wave(t: float, period: float) -> float:
    """Return a repeating 0..1..0 triangle wave.

    Kept for callers that want a strictly linear ramp. For *breathing* motion
    prefer :func:`sine_wave`: a triangle reverses direction instantaneously at
    every peak and trough, which reads as a tick on screen.
    """
    if period <= 0:
        return 0.0
    phase = (t % period) / period
    return 1.0 - abs(phase * 2.0 - 1.0)


def sine_wave(t: float, period: float, phase: float = 0.0) -> float:
    """Return a repeating 0..1..0 raised-cosine wave.

    Infinitely smooth — velocity and acceleration are continuous through the
    peaks and troughs — so anything riding it (glow radius, halo alpha, the
    CTA dot) breathes instead of ticking. *phase* is in cycles.
    """
    if period <= 0:
        return 0.0
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * ((t / period + phase) % 1.0))


# ── CTA dot pulse ─────────────────────────────────────────────────────────────

_PULSE_TIMES = (1.5, 2.0, 2.5)
_PULSE_HALF = 0.1  # ±0.1 s window around each pulse centre


def cta_dot_alpha(t: float) -> float:
    """Return the crimson dot alpha for the CTA scene at time *t*.

    Pulses (1.0) at t=1.5s, 2.0s, 2.5s; otherwise 0.3 (dim but visible).

    The pulse envelope is a raised cosine rather than a triangle, so the dot
    swells and relaxes rather than snapping to a point and back — and it meets
    the 0.3 baseline with zero slope, leaving no corner at the window edge.
    """
    for centre in _PULSE_TIMES:
        offset = abs(t - centre)
        if offset <= _PULSE_HALF:
            envelope = 0.5 + 0.5 * math.cos(math.pi * offset / _PULSE_HALF)
            return 0.3 + 0.7 * envelope
    return 0.3
