"""Classifier tests — 18+ cases covering every tier and every boundary condition."""

from nobodynamed_video.data.classifier import (
    CRITICAL_PEAK_FLOOR,
    CRITICAL_THRESHOLD,
    LATEST_YEAR,
    RESURRECTION_LOOKBACK_YEARS,
    classify,
)
from nobodynamed_video.models import NameRecord, Tier, YearCount

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_record(
    name: str = "Test",
    sex: str = "F",
    series: list[tuple[int, int]] | None = None,
) -> NameRecord:
    if series is None:
        series = [(2024, 100)]
    yc_list = [YearCount(year=y, count=c) for y, c in series]
    nonzero = [yc for yc in yc_list if yc.count > 0]
    peak = max(nonzero, key=lambda x: x.count) if nonzero else yc_list[-1]
    current = yc_list[-1]
    return NameRecord(
        name=name,
        sex=sex,
        series=yc_list,
        peak_year=peak.year,
        peak_count=max(peak.count, 1),
        current_year=current.year,
        current_count=current.count,
    )


def declining_series(peak: int = 50_000, current: int = 500) -> list[tuple[int, int]]:
    """Simulate a name that peaked high and is now very low with a steep slope."""
    result = [(1950, peak)]
    # Drop ~25% per year for last 6 years to ensure slope < -10%
    val = current * 4
    for yr in range(2019, 2025):
        result.append((yr, val))
        val = max(1, int(val * 0.70))
    result.append((2024, current))
    return result


def rising_series(base: int = 100, current: int = 1000) -> list[tuple[int, int]]:
    """Simulate a name rising strongly over the last 6 years."""
    result = []
    # 10-year avg should be low
    for yr in range(2014, 2019):
        result.append((yr, base))
    # Then strong growth
    val = base
    for yr in range(2019, 2024):
        val = int(val * 1.35)
        result.append((yr, val))
    result.append((2024, current))
    return result


# ── EXTINCT ───────────────────────────────────────────────────────────────────


def test_extinct_zero_current() -> None:
    record = make_record(series=[(1920, 5000), (2020, 500), (2024, 0)])
    assert classify(record) == Tier.EXTINCT


def test_extinct_never_popular() -> None:
    record = make_record(series=[(1990, 10), (2010, 5), (2024, 0)])
    assert classify(record) == Tier.EXTINCT


# ── CRITICAL ──────────────────────────────────────────────────────────────────


def test_critical_exactly_at_threshold() -> None:
    # count == CRITICAL_THRESHOLD and peak >= CRITICAL_PEAK_FLOOR
    record = make_record(series=[(1950, CRITICAL_PEAK_FLOOR), (2024, CRITICAL_THRESHOLD)])
    assert classify(record) == Tier.CRITICAL


def test_critical_below_threshold() -> None:
    record = make_record(series=[(1940, 10_000), (2024, 5)])
    assert classify(record) == Tier.CRITICAL


def test_not_critical_low_peak() -> None:
    # Count is low but peak never reached CRITICAL_PEAK_FLOOR → not CRITICAL
    record = make_record(series=[(1990, CRITICAL_PEAK_FLOOR - 1), (2024, 10)])
    result = classify(record)
    assert result != Tier.CRITICAL


def test_not_critical_count_above_threshold() -> None:
    # count > CRITICAL_THRESHOLD, so not CRITICAL even with a high peak
    record = make_record(series=[(1940, 10_000), (2024, CRITICAL_THRESHOLD + 1)])
    result = classify(record)
    assert result != Tier.CRITICAL


# ── RESURRECTED ───────────────────────────────────────────────────────────────


def test_resurrected_from_critical() -> None:
    # Was at 20 (< CRITICAL_THRESHOLD) 10 years ago, now at 500
    lookback_year = LATEST_YEAR - 10
    record = make_record(
        series=[
            (1920, 5000),
            (lookback_year, 20),  # critically low within lookback window
            (2024, 500),  # now well above threshold
        ]
    )
    assert classify(record) == Tier.RESURRECTED


def test_resurrected_from_extinct() -> None:
    near_year = LATEST_YEAR - 5
    record = make_record(
        series=[
            (1930, 8000),
            (near_year, 0),  # was extinct recently
            (2024, 300),
        ]
    )
    assert classify(record) == Tier.RESURRECTED


def test_not_resurrected_low_current() -> None:
    # Was low recently AND still low → should be CRITICAL, not RESURRECTED
    lookback_year = LATEST_YEAR - 10
    record = make_record(
        series=[
            (1940, 5000),
            (lookback_year, 10),
            (2024, CRITICAL_THRESHOLD),  # still at the boundary
        ]
    )
    # current == CRITICAL_THRESHOLD means it fails the "> CRITICAL_THRESHOLD" check
    result = classify(record)
    assert result == Tier.CRITICAL


def test_not_resurrected_too_old() -> None:
    # Low count was outside the lookback window → not resurrected
    old_year = LATEST_YEAR - RESURRECTION_LOOKBACK_YEARS - 1
    record = make_record(
        series=[
            (old_year, 10),
            (2010, 200),
            (2024, 500),
        ]
    )
    result = classify(record)
    assert result not in (Tier.RESURRECTED, Tier.EXTINCT, Tier.CRITICAL)


# ── RISING ────────────────────────────────────────────────────────────────────


def test_rising_strong_growth() -> None:
    record = make_record(series=rising_series(base=100, current=1500))
    assert classify(record) == Tier.RISING


def test_not_rising_weak_slope() -> None:
    # Minimal growth — not enough slope
    series = [(yr, 500 + yr - 2019) for yr in range(2019, 2025)]
    record = make_record(series=series)
    result = classify(record)
    assert result != Tier.RISING


# ── DECLINING ─────────────────────────────────────────────────────────────────


def test_declining_steep_drop() -> None:
    record = make_record(series=declining_series(peak=50_000, current=200))
    assert classify(record) == Tier.DECLINING


def test_not_declining_current_above_half_peak() -> None:
    # Slope might be negative but current is 60% of peak → not declining
    series = [(2000, 1000), (2020, 700), (2021, 680), (2022, 660), (2023, 640), (2024, 620)]
    record = make_record(series=series)
    result = classify(record)
    assert result != Tier.DECLINING


# ── STABLE ────────────────────────────────────────────────────────────────────


def test_stable_flat_series() -> None:
    series = [(yr, 500) for yr in range(2010, 2025)]
    record = make_record(series=series)
    assert classify(record) == Tier.STABLE


def test_stable_slight_variation() -> None:
    series = [(yr, 500 + (yr % 3) * 10) for yr in range(2010, 2025)]
    record = make_record(series=series)
    assert classify(record) == Tier.STABLE


# ── Boundary: CRITICAL_THRESHOLD exact edges ──────────────────────────────────


def test_boundary_critical_threshold_minus_one() -> None:
    record = make_record(series=[(1940, CRITICAL_PEAK_FLOOR), (2024, CRITICAL_THRESHOLD - 1)])
    assert classify(record) == Tier.CRITICAL


def test_boundary_critical_peak_floor_minus_one() -> None:
    # Peak just below the floor → should NOT be CRITICAL
    record = make_record(series=[(1940, CRITICAL_PEAK_FLOOR - 1), (2024, CRITICAL_THRESHOLD - 1)])
    result = classify(record)
    assert result != Tier.CRITICAL
