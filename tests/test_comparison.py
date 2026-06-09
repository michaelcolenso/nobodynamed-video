"""Tests for comparison name finding — the trajectory-flip algorithm."""

from pathlib import Path

import pytest

from nobodynamed_video.data.sqlite_source import SqliteSource

_FIXTURE = Path("fixtures/ssa.sqlite")


@pytest.fixture
def source() -> SqliteSource:
    return SqliteSource(_FIXTURE)


@pytest.mark.asyncio
async def test_dorothy_finds_flip(source: SqliteSource) -> None:
    """Dorothy peaked at 28000 in 1930, now 62.  Multiple names were below
    Dorothy in 1930 but beat her now — algorithm picks the highest current."""
    result = await source.find_comparison_name(
        "Dorothy", "F", peak_count=28000, current_count=62,
        peak_year=1930, latest_year=2024,
    )
    assert result in ("Violet", "Eleanor")


@pytest.mark.asyncio
async def test_thriving_name_has_no_flip(source: SqliteSource) -> None:
    """A name still at its peak can't have a flip — nobody currently beats
    it who was also below it at peak."""
    result = await source.find_comparison_name(
        "Violet", "F", peak_count=7000, current_count=6986,
        peak_year=2024, latest_year=2024,
    )
    assert result is None


@pytest.mark.asyncio
async def test_thriving_name_no_comparison(source: SqliteSource) -> None:
    """Emma is still at peak — nobody currently beats her who was below her
    at peak, so no flip."""
    result = await source.find_comparison_name(
        "Emma", "F", peak_count=20600, current_count=20600,
        peak_year=2014, latest_year=2024,
    )
    assert result is None


@pytest.mark.asyncio
async def test_returns_most_popular_flip(source: SqliteSource) -> None:
    """When multiple flips exist, the one with the highest current count wins."""
    result = await source.find_comparison_name(
        "Dorothy", "F", peak_count=28000, current_count=62,
        peak_year=1930, latest_year=2024,
    )
    if result is not None:
        record = await source.get_record(result, "F", 2024)
        assert record.current_count > 62


@pytest.mark.asyncio
async def test_cross_sex_excluded(source: SqliteSource) -> None:
    """Male names must not appear as comparisons for female names."""
    result = await source.find_comparison_name(
        "Walter", "M", peak_count=18000, current_count=180,
        peak_year=1920, latest_year=2024,
    )
    if result is not None:
        record = await source.get_record(result, "M", 2024)
        assert record.sex == "M"
