"""Tests for easing math and CTA dot-pulse — verifies monotonicity, bounds, and values."""

import math

import pytest
from nobodynamed_video.render.motion import (
    cta_dot_alpha,
    ease_in_out_cubic,
    ease_out_quart,
    lerp,
    lerp_int,
    linear,
    progress_in_window,
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
