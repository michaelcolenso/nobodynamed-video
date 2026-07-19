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
from datetime import datetime
from pathlib import Path

from nobodynamed_video.exceptions import DataSourceError
from nobodynamed_video.models import (
    DataProvenance,
    NameRecord,
    ObservationStatus,
    YearCount,
)


class SqliteSource:
    """Synchronous SQLite data source wrapped in an async interface."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    async def latest_year(self) -> int:
        rows = self._query("SELECT MAX(year) AS year FROM names", ())
        if not rows or rows[0]["year"] is None:
            raise DataSourceError(f"No SSA rows in {self._path}")
        return int(rows[0]["year"])

    def _has_table(self, name: str) -> bool:
        rows = self._query("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return bool(rows)

    async def provenance(self) -> DataProvenance:
        dataset_year = await self.latest_year()
        if not self._has_table("dataset_metadata"):
            return DataProvenance(
                source="synthetic_fixture",
                dataset_year=dataset_year,
                synthetic=True,
            )
        rows = self._query(
            "SELECT source, source_url, dataset_year, imported_at, sha256, synthetic "
            "FROM dataset_metadata ORDER BY dataset_year DESC LIMIT 1",
            (),
        )
        if not rows:
            raise DataSourceError("dataset_metadata exists but is empty")
        row = rows[0]
        imported = datetime.fromisoformat(str(row["imported_at"])) if row["imported_at"] else None
        return DataProvenance(
            source=str(row["source"]),
            source_url=str(row["source_url"]) if row["source_url"] else None,
            dataset_year=int(row["dataset_year"]),
            imported_at=imported,
            sha256=str(row["sha256"]) if row["sha256"] else None,
            synthetic=bool(row["synthetic"]),
        )

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

        series = [
            YearCount(
                year=int(r[0]),
                count=max(0, int(r[1])),
                status=(
                    ObservationStatus.OBSERVED
                    if int(r[1]) >= 5
                    else ObservationStatus.BELOW_REPORTING_THRESHOLD
                ),
            )
            for r in rows
        ]
        nonzero = [yc for yc in series if yc.status == ObservationStatus.OBSERVED and yc.count > 0]

        if not nonzero:
            raise DataSourceError(f"All counts are zero for name={name!r} sex={sex!r}")

        peak = max(nonzero, key=lambda yc: yc.count)
        source_year = await self.latest_year()
        exact = next((point for point in reversed(series) if point.year == year), None)
        if exact is not None and exact.status == ObservationStatus.OBSERVED:
            current_count = exact.count
            current_status = ObservationStatus.OBSERVED
        elif year <= source_year:
            current_count = 0
            current_status = ObservationStatus.BELOW_REPORTING_THRESHOLD
        else:
            current_count = 0
            current_status = ObservationStatus.MISSING_DATA

        return NameRecord(
            name=name,
            sex=sex,
            series=series,
            peak_year=peak.year,
            peak_count=peak.count,
            current_year=year,
            current_count=current_count,
            current_status=current_status,
            provenance=await self.provenance(),
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
                "WHERE sex = ? AND year = ? AND (count > ("
                "  SELECT count FROM names WHERE name = ? AND sex = ? AND year = ?"
                ") OR (count = (SELECT count FROM names WHERE name = ? AND sex = ? AND year = ?) "
                "AND lower(name) < lower(?)))"
            ),
            (sex, year, name, sex, year, name, sex, year, name),
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
                " AND (ranked.count > base.count OR "
                " (ranked.count = base.count AND lower(ranked.name) < lower(base.name)))) <= ? "
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
                " AND (ranked.count > base.count OR "
                " (ranked.count = base.count AND lower(ranked.name) < lower(base.name)))) <= ?"
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
