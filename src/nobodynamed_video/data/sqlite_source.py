"""SQLite-backed DataSource for dev and testing.

Reads from fixtures/ssa.sqlite (or any path configured via Settings).
Schema expected:
    CREATE TABLE names (
        name TEXT NOT NULL,
        sex  TEXT NOT NULL CHECK(sex IN ('M','F')),
        year INTEGER NOT NULL,
        count INTEGER NOT NULL,
        PRIMARY KEY (name, sex, year)
    );
"""

import sqlite3
from pathlib import Path

from nobodynamed_video.exceptions import DataSourceError
from nobodynamed_video.models import NameRecord, YearCount


class SqliteSource:
    """Synchronous SQLite data source wrapped in an async interface."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    async def get_record(self, name: str, sex: str, year: int) -> NameRecord:
        """Return a NameRecord for *name*/*sex* including all years up to *year*."""
        rows = self._query(
            "SELECT year, count FROM names "
            "WHERE name = ? AND sex = ? AND year <= ? "
            "ORDER BY year ASC",
            (name, sex, year),
        )

        if not rows:
            raise DataSourceError(f"No data found for name={name!r} sex={sex!r} year<={year}")

        series = [YearCount(year=r[0], count=r[1]) for r in rows]
        nonzero = [yc for yc in series if yc.count > 0]

        if not nonzero:
            raise DataSourceError(f"All counts are zero for name={name!r} sex={sex!r}")

        peak = max(nonzero, key=lambda yc: yc.count)
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

    def _query(self, sql: str, params: tuple[object, ...]) -> list[sqlite3.Row]:
        try:
            conn = sqlite3.connect(str(self._path))
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise DataSourceError(f"Cannot open {self._path}: {exc}") from exc

        try:
            return list(conn.execute(sql, params).fetchall())
        except sqlite3.Error as exc:
            raise DataSourceError(f"Query failed: {exc}") from exc
        finally:
            conn.close()

    async def get_rank(self, name: str, sex: str, year: int) -> int:
        rows = self._query(
            (
                "SELECT 1 + COUNT(*) AS rank FROM names "
                "WHERE sex = ? AND year = ? AND count > ("
                "  SELECT count FROM names WHERE name = ? AND sex = ? AND year = ?"
                ")"
            ),
            (sex, year, name, sex, year),
        )
        if not rows or rows[0]["rank"] is None:
            return 9999
        return int(rows[0]["rank"])

    async def get_last_top_year(self, name: str, sex: str, threshold: int) -> int | None:
        rows = self._query(
            (
                "SELECT base.year FROM names AS base "
                "WHERE base.name = ? AND base.sex = ? AND "
                "(SELECT 1 + COUNT(*) FROM names AS ranked "
                " WHERE ranked.sex = base.sex AND ranked.year = base.year "
                " AND ranked.count > base.count) <= ? "
                "ORDER BY base.year DESC LIMIT 1"
            ),
            (name, sex, threshold),
        )
        if not rows:
            return None
        return int(rows[0]["year"])

    async def count_years_in_top(self, name: str, sex: str, threshold: int) -> int:
        rows = self._query(
            (
                "SELECT COUNT(*) AS count_years FROM names AS base "
                "WHERE base.name = ? AND base.sex = ? AND "
                "(SELECT 1 + COUNT(*) FROM names AS ranked "
                " WHERE ranked.sex = base.sex AND ranked.year = base.year "
                " AND ranked.count > base.count) <= ?"
            ),
            (name, sex, threshold),
        )
        if not rows:
            return 0
        return int(rows[0]["count_years"])

    async def find_comparison_name(
        self,
        name: str,
        sex: str,
        peak_count: int,
        current_count: int,
        peak_year: int,
        latest_year: int,
    ) -> str | None:
        """Find a name that the subject beat at peak but that now beats the subject."""
        rows = self._query(
            "SELECT at_peak.name "
            "FROM names AS at_peak "
            "LEFT JOIN names AS now ON now.name = at_peak.name "
            "  AND now.sex = at_peak.sex AND now.year = ? "
            "WHERE at_peak.sex = ? "
            "  AND at_peak.year = ? "
            "  AND at_peak.name != ? "
            "  AND at_peak.count > 0 "
            "  AND at_peak.count < ? "
            "  AND COALESCE(now.count, 0) > ? "
            "ORDER BY COALESCE(now.count, 0) DESC "
            "LIMIT 1",
            (latest_year, sex, peak_year, name, peak_count, current_count),
        )
        if not rows:
            return None
        return str(rows[0]["name"])
