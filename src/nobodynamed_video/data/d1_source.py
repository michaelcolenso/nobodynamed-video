"""Cloudflare D1 HTTP DataSource for production use.

Calls the D1 REST API:
  POST {D1_URL}
  Authorization: Bearer {D1_TOKEN}
  Body: {"sql": "...", "params": [...]}

Fetches the full series for a name in a single query to stay within
Cloudflare's ~50 req/s rate limit.
"""

import asyncio
import json
from typing import cast

import httpx

from nobodynamed_video.data.records import build_name_record
from nobodynamed_video.exceptions import DataSourceError
from nobodynamed_video.models import NameRecord


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
        try:
            normalized_rows = (
                (int(cast(int | str, row["year"])), int(cast(int | str, row["count"])))
                for row in rows
            )
            return build_name_record(
                name=name,
                sex=sex,
                reference_year=year,
                rows=normalized_rows,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataSourceError(f"D1 returned invalid SSA rows: {exc}") from exc

    async def query_rows(self, sql: str, params: list[object]) -> list[dict[str, object]]:
        payload = {"sql": sql, "params": params}

        resp: httpx.Response | None = None
        last_exc: httpx.HTTPError | None = None
        for attempt in range(4):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(self._url, json=payload, headers=self._headers)
                    resp.raise_for_status()
                break
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < 3:
                    await asyncio.sleep(1.5 * (attempt + 1))
        else:
            raise DataSourceError(f"D1 request failed: {last_exc}") from last_exc
        assert resp is not None

        try:
            body = resp.json()
        except json.JSONDecodeError as exc:
            raise DataSourceError("D1 returned a non-JSON response") from exc
        if not isinstance(body, dict):
            raise DataSourceError("D1 returned an invalid response envelope")
        if not body.get("success"):
            errors = body.get("errors", [])
            raise DataSourceError(f"D1 query error: {errors}")
        result = body.get("result")
        if not isinstance(result, list) or not result or not isinstance(result[0], dict):
            raise DataSourceError("D1 response is missing a query result")
        rows = result[0].get("results")
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise DataSourceError("D1 query result contains invalid rows")
        return cast(list[dict[str, object]], rows)

    async def get_rank(self, name: str, sex: str, year: int) -> int:
        rows = await self.query_rows(
            (
                "SELECT CASE WHEN EXISTS ("
                "  SELECT 1 FROM names AS n3 JOIN name_years AS ny3 ON ny3.name_id = n3.id "
                "  WHERE n3.name_lower = lower(?3) AND n3.sex = ?1 AND ny3.year = ?2"
                ") THEN 1 + COUNT(*) ELSE 9999 END AS rank "
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
        rows = await self.query_rows(
            "SELECT n.name "
            "FROM names AS n "
            "JOIN name_years AS ny_then ON ny_then.name_id = n.id "
            "  AND ny_then.year = ?1 "
            "LEFT JOIN name_years AS ny_now ON ny_now.name_id = n.id "
            "  AND ny_now.year = ?2 "
            "WHERE n.sex = ?3 "
            "  AND n.name_lower != lower(?4) "
            "  AND ny_then.count > 0 "
            "  AND ny_then.count < ?5 "
            "  AND COALESCE(ny_now.count, 0) > ?6 "
            "ORDER BY COALESCE(ny_now.count, 0) DESC "
            "LIMIT 1",
            [peak_year, latest_year, sex, name, peak_count, current_count],
        )
        if not rows:
            return None
        return str(rows[0]["name"])
