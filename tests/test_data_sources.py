"""Backend parity and defensive data-boundary tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest
import respx
from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.data.records import build_name_record
from nobodynamed_video.data.sqlite_source import SqliteSource
from nobodynamed_video.exceptions import DataSourceError


def _sqlite_source(tmp_path: Path) -> SqliteSource:
    path = tmp_path / "ssa.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE names (name TEXT, sex TEXT, year INTEGER, count INTEGER)")
        connection.executemany(
            "INSERT INTO names VALUES (?, ?, ?, ?)",
            [
                ("Ada", "F", 1882, 10),
                ("Ada", "F", 1884, 20),
                ("Bea", "F", 1884, 30),
            ],
        )
    return SqliteSource(path)


def test_record_normalization_zero_fills_leading_internal_and_trailing_years() -> None:
    record = build_name_record("Ada", "F", 1885, [(1882, 10), (1884, 20)])

    assert [(point.year, point.count) for point in record.series] == [
        (1880, 0),
        (1881, 0),
        (1882, 10),
        (1883, 0),
        (1884, 20),
        (1885, 0),
    ]
    assert (record.peak_year, record.peak_count) == (1884, 20)
    assert (record.current_year, record.current_count) == (1885, 0)


def test_record_normalization_rejects_duplicate_years() -> None:
    with pytest.raises(DataSourceError, match="Duplicate SSA row"):
        build_name_record("Ada", "F", 1880, [(1880, 5), (1880, 6)])


@pytest.mark.asyncio
async def test_sqlite_lookup_is_case_insensitive_and_zero_filled(tmp_path: Path) -> None:
    record = await _sqlite_source(tmp_path).get_record("ada", "F", 1885)

    assert record.name == "ada"
    assert record.series[3].year == 1883
    assert record.series[3].count == 0


@pytest.mark.asyncio
async def test_sqlite_missing_rank_uses_sentinel(tmp_path: Path) -> None:
    source = _sqlite_source(tmp_path)

    assert await source.get_rank("Missing", "F", 1884) == 9999
    assert await source.get_rank("ada", "F", 1884) == 2


@respx.mock
@pytest.mark.asyncio
async def test_d1_rejects_malformed_success_envelope() -> None:
    url = "https://api.example.test/query"
    respx.post(url).mock(return_value=httpx.Response(200, json={"success": True, "result": []}))

    with pytest.raises(DataSourceError, match="missing a query result"):
        await D1Source(url, "token").query_rows("SELECT 1", [])


@respx.mock
@pytest.mark.asyncio
async def test_d1_rejects_non_json_response() -> None:
    url = "https://api.example.test/query"
    respx.post(url).mock(return_value=httpx.Response(200, text="gateway exploded"))

    with pytest.raises(DataSourceError, match="non-JSON"):
        await D1Source(url, "token").query_rows("SELECT 1", [])
