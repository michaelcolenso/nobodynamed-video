"""Easing functions and interpolation helpers for frame animation.

All easing functions take t ∈ [0, 1] and return a value ∈ [0, 1].
"""


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
    """Return a repeating 0..1..0 triangle wave."""
    if period <= 0:
        return 0.0
    phase = (t % period) / period
    return 1.0 - abs(phase * 2.0 - 1.0)


# ── CTA dot pulse ─────────────────────────────────────────────────────────────

_PULSE_TIMES = (1.5, 2.0, 2.5)
_PULSE_HALF = 0.1  # ±0.1 s window around each pulse centre


def cta_dot_alpha(t: float) -> float:
    """Return the crimson dot alpha for the CTA scene at time *t*.

    Pulses (1.0) at t=1.5s, 2.0s, 2.5s; otherwise 0.3 (dim but visible).
    """
    for centre in _PULSE_TIMES:
        if abs(t - centre) <= _PULSE_HALF:
            # Triangle pulse: peak at centre, zero at edges.
            return 1.0 - abs(t - centre) / _PULSE_HALF * 0.7
    return 0.3
