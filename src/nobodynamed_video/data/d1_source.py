"""Cloudflare D1 HTTP DataSource for production use.

Calls the D1 REST API:
  POST {D1_URL}
  Authorization: Bearer {D1_TOKEN}
  Body: {"sql": "...", "params": [...]}

Fetches the full series for a name in a single query to stay within
Cloudflare's ~50 req/s rate limit.
"""

from typing import cast

import httpx

from nobodynamed_video.exceptions import DataSourceError
from nobodynamed_video.models import NameRecord, YearCount


class D1Source:
    """Production DataSource backed by Cloudflare D1 over HTTP."""

    def __init__(self, d1_url: str, d1_token: str, timeout: float = 10.0) -> None:
        self._url = d1_url
        self._headers = {
            "Authorization": f"Bearer {d1_token}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    async def get_record(self, name: str, sex: str, year: int) -> NameRecord:
        """Return a NameRecord for *name*/*sex* up to *year*, fetched from D1."""
        rows = await self.query_rows(
            (
            "SELECT ny.year, ny.count "
            "FROM names AS n "
            "JOIN name_years AS ny ON ny.name_id = n.id "
            "WHERE n.name_lower = lower(?1) AND n.sex = ?2 AND ny.year <= ?3 "
            "ORDER BY ny.year ASC"
            ),
            [name, sex, year],
        )
        if not rows:
            raise DataSourceError(f"No D1 data for name={name!r} sex={sex!r} year<={year}")

        series = [
            YearCount(
                year=int(cast(int | str, r["year"])),
                count=int(cast(int | str, r["count"])),
            )
            for r in rows
        ]
        nonzero = [yc for yc in series if yc.count > 0]
        if not nonzero:
            raise DataSourceError(f"All counts zero in D1 for name={name!r} sex={sex!r}")

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

    async def query_rows(self, sql: str, params: list[object]) -> list[dict[str, object]]:
        payload = {"sql": sql, "params": params}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(self._url, json=payload, headers=self._headers)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise DataSourceError(f"D1 request failed: {exc}") from exc

        body = resp.json()
        if not body.get("success"):
            errors = body.get("errors", [])
            raise DataSourceError(f"D1 query error: {errors}")
        return list(body["result"][0].get("results", []))

    async def get_rank(self, name: str, sex: str, year: int) -> int:
        rows = await self.query_rows(
            (
                "SELECT 1 + COUNT(*) AS rank "
                "FROM names AS n2 "
                "JOIN name_years AS ny2 ON ny2.name_id = n2.id "
                "WHERE n2.sex = ?1 AND ny2.year = ?2 AND ny2.count > ("
                "  SELECT ny.count "
                "  FROM names AS n "
                "  JOIN name_years AS ny ON ny.name_id = n.id "
                "  WHERE n.name_lower = lower(?3) AND n.sex = ?1 AND ny.year = ?2"
                ")"
            ),
            [sex, year, name],
        )
        if not rows or rows[0].get("rank") is None:
            return 9999
        return int(str(rows[0]["rank"]))

    async def get_last_top_year(self, name: str, sex: str, threshold: int) -> int | None:
        rows = await self.query_rows(
            (
                "SELECT ny.year "
                "FROM names AS n "
                "JOIN name_years AS ny ON ny.name_id = n.id "
                "WHERE n.name_lower = lower(?1) AND n.sex = ?2 AND "
                "(SELECT 1 + COUNT(*) "
                " FROM name_years AS ny2 "
                " JOIN names AS n2 ON n2.id = ny2.name_id "
                " WHERE n2.sex = ?2 AND ny2.year = ny.year AND ny2.count > ny.count) <= ?3 "
                "ORDER BY ny.year DESC LIMIT 1"
            ),
            [name, sex, threshold],
        )
        if not rows:
            return None
        return int(str(rows[0]["year"]))

    async def count_years_in_top(self, name: str, sex: str, threshold: int) -> int:
        rows = await self.query_rows(
            (
                "SELECT COUNT(*) AS count_years "
                "FROM names AS n "
                "JOIN name_years AS ny ON ny.name_id = n.id "
                "WHERE n.name_lower = lower(?1) AND n.sex = ?2 AND "
                "(SELECT 1 + COUNT(*) "
                " FROM name_years AS ny2 "
                " JOIN names AS n2 ON n2.id = ny2.name_id "
                " WHERE n2.sex = ?2 AND ny2.year = ny.year AND ny2.count > ny.count) <= ?3"
            ),
            [name, sex, threshold],
        )
        if not rows:
            return 0
        return int(str(rows[0]["count_years"]))
