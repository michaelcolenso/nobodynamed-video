"""Tests for easing math and CTA dot-pulse — verifies monotonicity, bounds, and values."""

import math

import pytest
from nobodynamed_video.render.motion import (
    cta_dot_alpha,
    ease_in_out_cubic,
    ease_out_back,
    ease_out_cubic,
    ease_out_quart,
    lerp,
    lerp_int,
    linear,
    progress_in_window,
    sine_wave,
    smootherstep,
    smoothstep,
    triangle_wave,
)

# ── linear ────────────────────────────────────────────────────────────────────


def test_linear_at_boundaries() -> None:
    assert linear(0.0) == 0.0
    assert linear(1.0) == 1.0


def test_linear_midpoint() -> None:
    assert math.isclose(linear(0.5), 0.5)


def test_linear_clamps_below_zero() -> None:
    assert linear(-1.0) == 0.0


def test_linear_clamps_above_one() -> None:
    assert linear(2.0) == 1.0


# ── ease_out_quart ────────────────────────────────────────────────────────────


def test_ease_out_quart_boundaries() -> None:
    assert math.isclose(ease_out_quart(0.0), 0.0)
    assert math.isclose(ease_out_quart(1.0), 1.0)


def test_ease_out_quart_monotonic() -> None:
    values = [ease_out_quart(t / 100) for t in range(101)]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_ease_out_quart_fast_early() -> None:
    # Should cover more than half the range in the first quarter.
    assert ease_out_quart(0.25) > 0.5


# ── ease_in_out_cubic ─────────────────────────────────────────────────────────


def test_ease_in_out_cubic_boundaries() -> None:
    assert math.isclose(ease_in_out_cubic(0.0), 0.0)
    assert math.isclose(ease_in_out_cubic(1.0), 1.0)


def test_ease_in_out_cubic_monotonic() -> None:
    values = [ease_in_out_cubic(t / 100) for t in range(101)]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def test_ease_in_out_cubic_symmetric_at_midpoint() -> None:
    assert math.isclose(ease_in_out_cubic(0.5), 0.5, abs_tol=1e-9)


def test_ease_in_out_cubic_slow_at_ends() -> None:
    # Derivative near 0 and 1 should be lower than at 0.5.
    delta = 0.01
    derivative_start = (ease_in_out_cubic(delta) - ease_in_out_cubic(0.0)) / delta
    derivative_mid = (ease_in_out_cubic(0.5 + delta) - ease_in_out_cubic(0.5)) / delta
    assert derivative_start < derivative_mid


# ── lerp / lerp_int ───────────────────────────────────────────────────────────


def test_lerp_endpoints() -> None:
    assert lerp(0.0, 10.0, 0.0) == 0.0
    assert lerp(0.0, 10.0, 1.0) == 10.0


def test_lerp_midpoint() -> None:
    assert math.isclose(lerp(0.0, 100.0, 0.5), 50.0)


def test_lerp_int_rounds() -> None:
    assert lerp_int(0, 10, 0.55) == 6  # 0 + (10-0)*0.55 = 5.5 → rounds to 6


# ── progress_in_window ────────────────────────────────────────────────────────


def test_progress_before_window() -> None:
    assert progress_in_window(0.0, 1.0, 2.0) == 0.0


def test_progress_after_window() -> None:
    assert progress_in_window(3.0, 1.0, 2.0) == 1.0


def test_progress_midway() -> None:
    assert math.isclose(progress_in_window(1.5, 1.0, 2.0), 0.5)


def test_triangle_wave_boundaries() -> None:
    assert triangle_wave(0.0, 1.0) == pytest.approx(0.0)
    assert triangle_wave(0.5, 1.0) == pytest.approx(1.0)
    assert triangle_wave(1.0, 1.0) == pytest.approx(0.0)


def test_triangle_wave_stays_in_bounds() -> None:
    values = [triangle_wave(t / 20, 0.6) for t in range(21)]
    assert all(0.0 <= value <= 1.0 for value in values)


# ── CTA dot pulse ─────────────────────────────────────────────────────────────

_PULSE_CENTRES = [1.5, 2.0, 2.5]


@pytest.mark.parametrize("centre", _PULSE_CENTRES)
def test_dot_alpha_peak_at_pulse_centres(centre: float) -> None:
    assert cta_dot_alpha(centre) == pytest.approx(1.0)


def test_dot_alpha_dim_between_pulses() -> None:
    # At t=1.75 (midway between 1.5 and 2.0 pulses) should be dim.
    assert cta_dot_alpha(1.75) < 1.0


def test_dot_alpha_always_positive() -> None:
    times = [t / 10 for t in range(31)]
    assert all(cta_dot_alpha(t) >= 0.0 for t in times)


# ── smoothstep / smootherstep ─────────────────────────────────────────────────


@pytest.mark.parametrize("fn", [smoothstep, smootherstep])
def test_smoothsteps_anchored_and_clamped(fn) -> None:  # type: ignore[no-untyped-def]
    assert fn(0.0) == pytest.approx(0.0)
    assert fn(1.0) == pytest.approx(1.0)
    assert fn(-3.0) == pytest.approx(0.0)
    assert fn(4.0) == pytest.approx(1.0)
    assert fn(0.5) == pytest.approx(0.5)


@pytest.mark.parametrize("fn", [smoothstep, smootherstep])
def test_smoothsteps_monotonic(fn) -> None:  # type: ignore[no-untyped-def]
    values = [fn(t / 200) for t in range(201)]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


@pytest.mark.parametrize("fn", [smoothstep, smootherstep])
def test_smoothsteps_rest_at_both_ends(fn) -> None:  # type: ignore[no-untyped-def]
    # Near-zero velocity where the ramp meets its holds — this is what keeps
    # fades from popping on and creeping off.
    h = 1e-4
    assert (fn(h) - fn(0.0)) / h < 1e-2
    assert (fn(1.0) - fn(1.0 - h)) / h < 1e-2


def test_smootherstep_is_gentler_at_the_seams_than_smoothstep() -> None:
    assert smootherstep(0.05) < smoothstep(0.05)
    assert smootherstep(0.95) > smoothstep(0.95)


# ── ease_out_cubic ────────────────────────────────────────────────────────────


def test_ease_out_cubic_boundaries() -> None:
    assert ease_out_cubic(0.0) == pytest.approx(0.0)
    assert ease_out_cubic(1.0) == pytest.approx(1.0)


def test_ease_out_cubic_decelerates() -> None:
    assert ease_out_cubic(0.25) > 0.25
    values = [ease_out_cubic(t / 100) for t in range(101)]
    assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))


# ── ease_out_back ─────────────────────────────────────────────────────────────


def test_ease_out_back_anchored_at_both_ends() -> None:
    # Regression: the old formulation returned -0.5*overshoot at t=0, so every
    # track using it jumped away from its own start value on the first frame.
    assert ease_out_back(0.0) == pytest.approx(0.0)
    assert ease_out_back(1.0) == pytest.approx(1.0)


def test_ease_out_back_overshoots_then_settles() -> None:
    values = [ease_out_back(t / 100) for t in range(101)]
    assert max(values) > 1.0
    assert values[-1] == pytest.approx(1.0)


def test_ease_out_back_zero_overshoot_never_exceeds_one() -> None:
    assert all(ease_out_back(t / 100, overshoot=0.0) <= 1.0 + 1e-9 for t in range(101))


# ── sine_wave ─────────────────────────────────────────────────────────────────


def test_sine_wave_boundaries() -> None:
    assert sine_wave(0.0, 1.0) == pytest.approx(0.0)
    assert sine_wave(0.5, 1.0) == pytest.approx(1.0)
    assert sine_wave(1.0, 1.0) == pytest.approx(0.0)


def test_sine_wave_stays_in_bounds_and_repeats() -> None:
    values = [sine_wave(t / 30, 0.9) for t in range(91)]
    assert all(0.0 <= value <= 1.0 for value in values)
    assert sine_wave(0.37, 0.9) == pytest.approx(sine_wave(0.37 + 0.9, 0.9))


def test_sine_wave_turns_around_smoothly() -> None:
    # Unlike a triangle wave, the slope vanishes at the peak — no visible tick
    # when the breathing motion reverses.
    h = 1e-4
    peak = 0.45
    assert abs(sine_wave(peak + h, 0.9) - sine_wave(peak - h, 0.9)) / (2 * h) < 1e-2


def test_sine_wave_phase_offsets_by_cycles() -> None:
    assert sine_wave(0.0, 2.4, phase=0.5) == pytest.approx(1.0)


def test_sine_wave_zero_period_is_safe() -> None:
    assert sine_wave(1.0, 0.0) == 0.0
