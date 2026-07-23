"""Six-tier name classifier with explicit, unit-tested thresholds.

Tier resolution order (first match wins):
  EXTINCT → RESURRECTED → CRITICAL → RISING → DECLINING → STABLE

Note on SSA data quality: counts under 5 are suppressed in the raw data.
A value of 5 in the series may mean "5 to 9". The classifier treats 5 as a
hard floor and never classifies a name as CRITICAL solely on that value when
peak_count is borderline.
"""

from nobodynamed_video.models import NameRecord, Tier

# ── Canonical thresholds ─────────────────────────────────────────────────────
LATEST_YEAR: int = 2024  # Update annually when SSA releases new data.
CRITICAL_THRESHOLD: int = 25
CRITICAL_PEAK_FLOOR: int = 1000
DECLINING_SLOPE_5Y: float = -0.10
DECLINING_PEAK_RATIO: float = 0.50
POST_DECLINE_RATIO: float = 0.15
STABLE_BAND: float = 0.10
RISING_SLOPE_5Y: float = 0.20
RISING_AVG_RATIO: float = 1.50
RESURRECTION_LOOKBACK_YEARS: int = 30


def _slope_5y(record: NameRecord) -> float:
    """Fractional change per year over the last 5 data years.

    Returns the average year-over-year fractional change:
        (count_now - count_5yr_ago) / (count_5yr_ago * 5)
    Returns 0.0 when there are fewer than 2 data points or the base is 0.
    """
    years_with_counts = [(yc.year, yc.count) for yc in record.series if yc.count > 0]
    if len(years_with_counts) < 2:
        return 0.0
    # Take up to 5 most-recent years.
    recent = years_with_counts[-min(6, len(years_with_counts)) :]
    if len(recent) < 2:
        return 0.0
    base_count = recent[0][1]
    end_count = recent[-1][1]
    span = recent[-1][0] - recent[0][0]
    if base_count == 0 or span == 0:
        return 0.0
    return (end_count - base_count) / (base_count * span)


def _avg_10y(record: NameRecord) -> float:
    """Average count over the last 10 data years (years with count > 0)."""
    years_with_counts = [yc.count for yc in record.series if yc.count > 0]
    if not years_with_counts:
        return 0.0
    recent = years_with_counts[-min(10, len(years_with_counts)) :]
    return sum(recent) / len(recent)


def _was_low_recently(record: NameRecord, threshold: int, lookback: int) -> bool:
    """Return True if any year within *lookback* years had count <= *threshold*."""
    cutoff = record.current_year - lookback
    return any(yc.year >= cutoff and yc.count <= threshold for yc in record.series)


def classify(record: NameRecord) -> Tier:
    """Classify a NameRecord into one of the six tiers.

    Resolution order: EXTINCT → RESURRECTED → CRITICAL → RISING → DECLINING → STABLE
    """
    current = record.current_count
    peak = record.peak_count

    # 1. EXTINCT — zero in the current year.
    if current == 0:
        return Tier.EXTINCT

    # 2. RESURRECTED — was EXTINCT or CRITICAL within last 30 years, now STABLE+
    #    "STABLE+" means current count > CRITICAL_THRESHOLD.
    if current > CRITICAL_THRESHOLD and _was_low_recently(
        record, CRITICAL_THRESHOLD, RESURRECTION_LOOKBACK_YEARS
    ):
        return Tier.RESURRECTED

    # 3. CRITICAL — currently very low AND once had significant popularity.
    if current <= CRITICAL_THRESHOLD and peak >= CRITICAL_PEAK_FLOOR:
        return Tier.CRITICAL

    # 4. RISING — strong positive slope AND well above long-run average.
    slope = _slope_5y(record)
    avg10 = _avg_10y(record)
    if slope > RISING_SLOPE_5Y and (avg10 == 0 or current > RISING_AVG_RATIO * avg10):
        return Tier.RISING

    # 5. DECLINING — negative slope AND well below peak.
    if slope < DECLINING_SLOPE_5Y and current < DECLINING_PEAK_RATIO * peak:
        return Tier.DECLINING

    # 5b. POST-DECLINE PLATEAU — massive historical decline, flat recent slope.
    # A name at <15% of a significant peak collapsed long ago; editorially it is
    # not "stable" even though the recent trajectory is flat.
    if peak >= CRITICAL_PEAK_FLOOR and current < POST_DECLINE_RATIO * peak:
        return Tier.DECLINING

    # 6. STABLE — default.
    return Tier.STABLE
