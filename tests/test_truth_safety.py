"""Adversarial regression tests for the publication trust boundary."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from nobodynamed_video.data.claim_safety import copy_is_supported
from nobodynamed_video.data.classifier import classify, classify_dimensions
from nobodynamed_video.data.ctx import _find_collapse_year, _find_trough, _resolve_event
from nobodynamed_video.data.doctor import inspect_data
from nobodynamed_video.data.sqlite_source import SqliteSource
from nobodynamed_video.models import (
    DataMode,
    DataProvenance,
    NameRecord,
    ObservationStatus,
    Prevalence,
    Tier,
    YearCount,
)


def _record(*points: tuple[int, int], status: ObservationStatus) -> NameRecord:
    series = [YearCount(year=year, count=count) for year, count in points]
    peak = max(series, key=lambda point: point.count)
    return NameRecord(
        name="Test",
        sex="F",
        series=series,
        peak_year=peak.year,
        peak_count=peak.count,
        current_year=points[-1][0],
        current_count=points[-1][1],
        current_status=status,
    )


def test_suppressed_current_is_not_extinct() -> None:
    record = _record(
        (1950, 5000),
        (2024, 5),
        (2025, 0),
        status=ObservationStatus.BELOW_REPORTING_THRESHOLD,
    )
    assert classify(record) != Tier.EXTINCT
    assert classify_dimensions(record).prevalence == Prevalence.BELOW_REPORTING_THRESHOLD


def test_missing_current_count_copy_fails_closed() -> None:
    ctx = {"current_status": ObservationStatus.MISSING_DATA, "current_count": 0}
    assert not copy_is_supported("Only {{ current_count }} babies last year", ctx)


@pytest.mark.parametrize("field", ["decline_pct", "rise_pct"])
def test_suppressed_current_derived_copy_fails_closed(field: str) -> None:
    ctx = {"current_status": ObservationStatus.BELOW_REPORTING_THRESHOLD, field: 100}
    assert not copy_is_supported(f"Change: {{{{ {field} }}}}%", ctx)


@pytest.mark.parametrize(
    "copy",
    [
        "Mean age of every living {{ name }}",
        "Most {{ name }}s are over {{ avg_age }}",
        "{{ name }} was almost extinct",
        "{{ name }} is one bad year from zero",
    ],
)
def test_unsupported_copy_is_rejected(copy: str) -> None:
    assert not copy_is_supported(copy, {"current_status": ObservationStatus.OBSERVED})


def test_sparse_rows_do_not_create_fake_collapse() -> None:
    record = _record(
        (1950, 1000),
        (2000, 100),
        (2025, 10),
        status=ObservationStatus.OBSERVED,
    )
    assert _find_collapse_year(record) is None


def test_comeback_trough_cannot_precede_peak() -> None:
    record = _record(
        (1880, 5),
        (1920, 1000),
        (1980, 20),
        (2025, 200),
        status=ObservationStatus.OBSERVED,
    )
    assert _find_trough(record) == (1980, 20)


def test_low_confidence_event_never_executes() -> None:
    record = _record(
        (2015, 100),
        (2016, 50),
        status=ObservationStatus.OBSERVED,
    )
    event = {
        ("test", "F"): {
            "killing_event": "a rumor",
            "event_year": 2015,
            "confidence": "low",
            "evidence": "uncertain",
        }
    }
    assert _resolve_event(event, record) is None


class _SyntheticSource:
    async def latest_year(self) -> int:
        return 2025

    async def provenance(self) -> DataProvenance:
        return DataProvenance(source="fixture", dataset_year=2025, synthetic=True)


@pytest.mark.asyncio
async def test_publish_mode_rejects_synthetic_data() -> None:
    result = await inspect_data(_SyntheticSource(), DataMode.PUBLISH)  # type: ignore[arg-type]
    assert not result.passed
    assert any("synthetic" in error.lower() for error in result.errors)


@pytest.mark.asyncio
async def test_ssa_rank_ties_break_alphabetically(tmp_path: Path) -> None:
    database = tmp_path / "names.sqlite"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "CREATE TABLE names(name TEXT, sex TEXT, year INTEGER, count INTEGER, "
            "PRIMARY KEY(name, sex, year))"
        )
        conn.executemany(
            "INSERT INTO names VALUES (?, 'F', 2025, ?)",
            [("Zoe", 10), ("Amy", 10), ("Bea", 20)],
        )
    source = SqliteSource(database)
    assert await source.get_rank("Bea", "F", 2025) == 1
    assert await source.get_rank("Amy", "F", 2025) == 2
    assert await source.get_rank("Zoe", "F", 2025) == 3


@pytest.mark.asyncio
async def test_absent_row_is_below_reporting_threshold(tmp_path: Path) -> None:
    database = tmp_path / "names.sqlite"
    with sqlite3.connect(database) as conn:
        conn.execute(
            "CREATE TABLE names(name TEXT, sex TEXT, year INTEGER, count INTEGER, "
            "PRIMARY KEY(name, sex, year))"
        )
        conn.executemany(
            "INSERT INTO names VALUES (?, ?, ?, ?)",
            [("Alice", "F", 2024, 8), ("Other", "F", 2025, 5)],
        )
    record = await SqliteSource(database).get_record("Alice", "F", 2025)
    assert record.current_count == 0
    assert record.current_status == ObservationStatus.BELOW_REPORTING_THRESHOLD
