from nobodynamed_video.models import YearCount
from nobodynamed_video.render.programs import (
    ONE_HIT_FALL_STEPS,
    ONE_HIT_HOLD_STEPS,
    ONE_HIT_RISE_STEPS,
    RenderPoint,
    _prepare_render_series,
)


def test_one_hit_spike_adds_rise_and_hold_samples() -> None:
    source = [
        YearCount(year=1976, count=0),
        YearCount(year=1977, count=215),
        YearCount(year=1978, count=40),
        YearCount(year=1979, count=16),
        YearCount(year=1980, count=5),
        YearCount(year=1981, count=0),
    ]

    rendered = _prepare_render_series(source, peak_year=1977, peak_count=215)

    peak_points = [point for point in rendered if 1976 < point.year <= 1977]
    hold_points = [point for point in rendered if 1977 < point.year <= 1977.2]

    assert len(peak_points) == ONE_HIT_RISE_STEPS
    assert len(hold_points) == ONE_HIT_HOLD_STEPS
    assert peak_points[-1].year == 1977
    assert peak_points[-1].count == 215
    assert all(point.count == 215 for point in hold_points)


def test_one_hit_collapse_gets_eased_fall_samples() -> None:
    """A sharp one-year post-peak drop must not stay one raw segment.

    Left alone, that segment's |dy| dwarfs every rise sub-step's, becomes the
    render's maxDy, and — stacked with canvas.tsx's spike/collapse timing
    weights — claims a wildly disproportionate share of the draw: the tracer
    stalls on the fall, then snaps through several later years in under a
    frame. Mirror the rise's eased-sub-step treatment on the way down.
    """
    source = [
        YearCount(year=1976, count=0),
        YearCount(year=1977, count=215),
        YearCount(year=1978, count=34),
        YearCount(year=1979, count=16),
        YearCount(year=1980, count=5),
        YearCount(year=1981, count=0),
    ]

    rendered = _prepare_render_series(source, peak_year=1977, peak_count=215)

    hold_end_year = 1977 + 0.20
    fall_points = [point for point in rendered if hold_end_year < point.year <= 1978]

    assert len(fall_points) == ONE_HIT_FALL_STEPS
    assert fall_points[-1].year == 1978
    assert fall_points[-1].count == 34
    # Eased (smootherstep), not linear: strictly decreasing, no single sub-step
    # carrying an outsized share of the drop.
    counts = [215.0, *[p.count for p in fall_points]]
    deltas = [counts[i] - counts[i + 1] for i in range(len(counts) - 1)]
    assert all(d > 0 for d in deltas), "fall must be monotonically decreasing"
    assert max(deltas) / (215.0 - 34.0) < 0.4, "no single fall sub-step dominates the drop"

    # A gentler drop (below ONE_HIT_FALL_RATIO) is left alone — this is a
    # one-hit spike guard, not a general collapse re-timer.
    gentle = [
        YearCount(year=1976, count=0),
        YearCount(year=1977, count=215),
        YearCount(year=1978, count=180),
        YearCount(year=1979, count=0),
    ]
    gentle_rendered = _prepare_render_series(gentle, peak_year=1977, peak_count=215)
    gentle_fall_points = [p for p in gentle_rendered if hold_end_year < p.year <= 1978]
    # Only the original, un-densified landing point survives — no eased
    # sub-steps were inserted for this shallower drop.
    assert gentle_fall_points == [RenderPoint(1978.0, 180.0)]


def test_gradual_rise_is_not_resampled() -> None:
    source = [
        YearCount(year=2000, count=50),
        YearCount(year=2001, count=70),
        YearCount(year=2002, count=100),
    ]

    rendered = _prepare_render_series(source, peak_year=2002, peak_count=100)
    original_years = [1880 + index for index in range(120)] + [2000, 2001, 2002]

    assert [point.year for point in rendered] == original_years
