"""Shared normalization for SSA rows returned by every data backend."""

from __future__ import annotations

from collections.abc import Iterable

from nobodynamed_video.exceptions import DataSourceError
from nobodynamed_video.models import NameRecord, YearCount

SSA_FIRST_YEAR = 1880


def build_name_record(
    name: str, sex: str, reference_year: int, rows: Iterable[tuple[int, int]]
) -> NameRecord:
    """Validate sparse SSA rows and expand them into a contiguous annual series.

    SSA omits counts below five. Those omissions occur both before a name first
    appears and between reported years, so retaining only database rows makes a
    chart interpolate births that were never reported. All backends use this
    function to give classifiers and renderers identical zero-filled input.
    """
    if reference_year < SSA_FIRST_YEAR:
        raise DataSourceError(
            f"Reference year {reference_year} predates SSA data ({SSA_FIRST_YEAR})"
        )

    counts: dict[int, int] = {}
    for raw_year, raw_count in rows:
        if raw_year < SSA_FIRST_YEAR or raw_year > reference_year:
            raise DataSourceError(f"SSA row year {raw_year} is outside the requested range")
        if raw_count < 0:
            raise DataSourceError(f"SSA row for {raw_year} has negative count {raw_count}")
        if raw_year in counts:
            raise DataSourceError(f"Duplicate SSA row for year {raw_year}")
        counts[raw_year] = raw_count

    if not counts:
        raise DataSourceError(f"No data found for name={name!r} sex={sex!r} year<={reference_year}")
    if not any(count > 0 for count in counts.values()):
        raise DataSourceError(f"All counts are zero for name={name!r} sex={sex!r}")

    series = [
        YearCount(year=year, count=counts.get(year, 0), reported=year in counts)
        for year in range(SSA_FIRST_YEAR, reference_year + 1)
    ]
    peak = max(series, key=lambda point: point.count)
    current = series[-1]
    return NameRecord(
        name=name,
        sex=sex,
        series=series,
        peak_year=peak.year,
        peak_count=peak.count,
        current_year=current.year,
        current_count=current.count,
    )
