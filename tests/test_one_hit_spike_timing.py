from nobodynamed_video.models import YearCount
from nobodynamed_video.render.programs import (
    ONE_HIT_HOLD_STEPS,
    ONE_HIT_RISE_STEPS,
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


def test_gradual_rise_is_not_resampled() -> None:
    source = [
        YearCount(year=2000, count=50),
        YearCount(year=2001, count=70),
        YearCount(year=2002, count=100),
    ]

    rendered = _prepare_render_series(source, peak_year=2002, peak_count=100)
    original_years = [1880 + index for index in range(120)] + [2000, 2001, 2002]

    assert [point.year for point in rendered] == original_years
