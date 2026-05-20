"""Cloudflare D1 HTTP DataSource for production use.

Calls the D1 REST API:
  POST {D1_URL}
  Authorization: Bearer {D1_TOKEN}
  Body: {"sql": "...", "params": [...]}

Fetches the full series for a name in a single query to stay within
Cloudflare's ~50 req/s rate limit.
"""

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
        sql = (
            "SELECT year, count FROM names "
            "WHERE name = ?1 AND sex = ?2 AND year <= ?3 "
            "ORDER BY year ASC"
        )
        payload = {"sql": sql, "params": [name, sex, year]}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    self._url, json=payload, headers=self._headers
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise DataSourceError(f"D1 request failed: {exc}") from exc

        body = resp.json()
        if not body.get("success"):
            errors = body.get("errors", [])
            raise DataSourceError(f"D1 query error: {errors}")

        rows = body["result"][0].get("results", [])
        if not rows:
            raise DataSourceError(
                f"No D1 data for name={name!r} sex={sex!r} year<={year}"
            )

        series = [YearCount(year=r["year"], count=r["count"]) for r in rows]
        nonzero = [yc for yc in series if yc.count > 0]
        if not nonzero:
            raise DataSourceError(
                f"All counts zero in D1 for name={name!r} sex={sex!r}"
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
