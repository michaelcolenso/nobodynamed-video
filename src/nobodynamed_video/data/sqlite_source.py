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
        try:
            conn = sqlite3.connect(str(self._path))
        except sqlite3.Error as exc:
            raise DataSourceError(f"Cannot open {self._path}: {exc}") from exc

        try:
            rows = conn.execute(
                "SELECT year, count FROM names "
                "WHERE name = ? AND sex = ? AND year <= ? "
                "ORDER BY year ASC",
                (name, sex, year),
            ).fetchall()
        except sqlite3.Error as exc:
            conn.close()
            raise DataSourceError(f"Query failed: {exc}") from exc
        finally:
            conn.close()

        if not rows:
            raise DataSourceError(
                f"No data found for name={name!r} sex={sex!r} year<={year}"
            )

        series = [YearCount(year=r[0], count=r[1]) for r in rows]
        nonzero = [yc for yc in series if yc.count > 0]

        if not nonzero:
            raise DataSourceError(
                f"All counts are zero for name={name!r} sex={sex!r}"
            )

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
