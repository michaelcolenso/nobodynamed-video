"""Truth-safe, explainable name classification.

SSA only publishes rows with at least five births. A missing row is therefore
not evidence of zero births. Classification separates three independent
questions—current prevalence, recent trajectory, and historical shape—while
retaining a conservative legacy tier for the existing renderer.
"""

from nobodynamed_video.models import (
    Classification,
    HistoricalShape,
    NameRecord,
    ObservationStatus,
    Prevalence,
    Tier,
    Trajectory,
)

CRITICAL_THRESHOLD = 25
CRITICAL_PEAK_FLOOR = 1000
DECLINING_ANNUAL_RATE = -0.10
RISING_ANNUAL_RATE = 0.10
RESURRECTION_LOOKBACK_YEARS = 30
# Retained only for downstream test/data compatibility. Runtime selection is
# always derived from ``DataSource.latest_year()``.
LATEST_YEAR = 2024


def _recent_window(record: NameRecord, years: int = 5) -> list[tuple[int, int]]:
    cutoff = record.current_year - years
    return [
        (p.year, p.count)
        for p in record.series
        if p.status == ObservationStatus.OBSERVED and p.count >= 5 and p.year >= cutoff
    ]


def _annual_rate(record: NameRecord) -> float | None:
    recent = _recent_window(record)
    if len(recent) < 2:
        return None
    start_year, start_count = recent[0]
    end_year, end_count = recent[-1]
    span = end_year - start_year
    # Two isolated observations across a large gap do not establish a trend.
    if start_count <= 0 or span <= 0 or span > 6:
        return None
    return (end_count - start_count) / (start_count * span)


def _prevalence(record: NameRecord) -> Prevalence:
    if record.current_status == ObservationStatus.MISSING_DATA:
        return Prevalence.UNOBSERVED
    if record.current_status == ObservationStatus.BELOW_REPORTING_THRESHOLD:
        return Prevalence.BELOW_REPORTING_THRESHOLD
    if record.current_count >= 1000:
        return Prevalence.HIGH
    if record.current_count >= 100:
        return Prevalence.MODERATE
    return Prevalence.LOW


def _trajectory(record: NameRecord) -> Trajectory:
    if record.current_status != ObservationStatus.OBSERVED:
        return Trajectory.INSUFFICIENT_DATA
    rate = _annual_rate(record)
    if rate is None:
        return Trajectory.INSUFFICIENT_DATA
    if rate >= RISING_ANNUAL_RATE:
        return Trajectory.RISING
    if rate <= DECLINING_ANNUAL_RATE:
        return Trajectory.DECLINING
    return Trajectory.STABLE


def _historical_shape(record: NameRecord, trajectory: Trajectory) -> HistoricalShape:
    observed = [p for p in record.series if p.status == ObservationStatus.OBSERVED and p.count >= 5]
    if len(observed) < 3:
        return HistoricalShape.INSUFFICIENT_DATA
    if observed[0].year >= record.current_year - 20:
        return HistoricalShape.NEW_OR_RECENT

    post_peak = [p for p in observed if p.year >= record.peak_year]
    trough = min(post_peak, key=lambda p: (p.count, p.year))
    if (
        trough.year < record.current_year
        and trough.count <= CRITICAL_THRESHOLD
        and record.current_count > CRITICAL_THRESHOLD
        and record.current_count > trough.count
        and trough.year >= record.current_year - RESURRECTION_LOOKBACK_YEARS
    ):
        return HistoricalShape.COMEBACK
    if (
        record.peak_year < record.current_year - 10
        and record.current_count < record.peak_count * 0.5
    ):
        return HistoricalShape.PEAKED
    return HistoricalShape.LONG_RUNNING


def classify_dimensions(record: NameRecord) -> Classification:
    prevalence = _prevalence(record)
    trajectory = _trajectory(record)
    shape = _historical_shape(record, trajectory)

    if shape == HistoricalShape.COMEBACK:
        legacy = Tier.RESURRECTED
    elif trajectory == Trajectory.RISING:
        legacy = Tier.RISING
    elif trajectory == Trajectory.DECLINING:
        legacy = Tier.DECLINING
    elif (
        prevalence in (Prevalence.LOW, Prevalence.BELOW_REPORTING_THRESHOLD)
        and record.current_count <= CRITICAL_THRESHOLD
        and record.peak_count >= CRITICAL_PEAK_FLOOR
    ):
        legacy = Tier.CRITICAL
    else:
        legacy = Tier.STABLE

    rationale = [
        f"current observation: {record.current_status.value}",
        f"prevalence: {prevalence.value}",
        f"trajectory: {trajectory.value}",
        f"historical shape: {shape.value}",
    ]
    return Classification(
        prevalence=prevalence,
        trajectory=trajectory,
        historical_shape=shape,
        legacy_tier=legacy,
        rationale=rationale,
    )


def classify(record: NameRecord) -> Tier:
    """Compatibility adapter for renderer code that still expects ``Tier``."""
    return classify_dimensions(record).legacy_tier
