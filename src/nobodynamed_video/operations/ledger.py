"""Local, source-agnostic publishing ledger and analytics importer."""

from __future__ import annotations

import csv
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS publications (
  spec_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  external_id TEXT NOT NULL,
  url TEXT,
  published_at TEXT NOT NULL,
  format TEXT NOT NULL,
  hook_id TEXT,
  experiment TEXT,
  PRIMARY KEY(platform, external_id)
);
CREATE TABLE IF NOT EXISTS metrics (
  platform TEXT NOT NULL,
  external_id TEXT NOT NULL,
  measured_at TEXT NOT NULL,
  views INTEGER,
  likes INTEGER,
  comments INTEGER,
  shares INTEGER,
  avg_watch_s REAL,
  completion_rate REAL,
  profile_visits INTEGER,
  site_clicks INTEGER,
  PRIMARY KEY(platform, external_id, measured_at)
);
CREATE TABLE IF NOT EXISTS content_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  sex TEXT NOT NULL,
  format TEXT NOT NULL DEFAULT 'fast',
  hook_style TEXT,
  experiment TEXT,
  status TEXT NOT NULL DEFAULT 'queued',
  source TEXT NOT NULL DEFAULT 'manual',
  created_at TEXT NOT NULL
);
"""


class PublishingLedger:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as conn:
            conn.executescript(_DDL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_publication(
        self,
        spec_id: str,
        platform: str,
        external_id: str,
        url: str | None,
        video_format: str,
        hook_id: str | None = None,
        experiment: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO publications VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    spec_id,
                    platform,
                    external_id,
                    url,
                    datetime.now(tz=UTC).isoformat(),
                    video_format,
                    hook_id,
                    experiment,
                ),
            )

    def import_metrics_csv(self, path: Path) -> int:
        required = {"platform", "external_id", "measured_at"}
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        if rows and not required.issubset(rows[0]):
            raise ValueError(f"Metrics CSV requires columns: {sorted(required)}")
        with self._connect() as conn:
            for row in rows:
                conn.execute(
                    "INSERT OR REPLACE INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["platform"],
                        row["external_id"],
                        row["measured_at"],
                        _int(row.get("views")),
                        _int(row.get("likes")),
                        _int(row.get("comments")),
                        _int(row.get("shares")),
                        _float(row.get("avg_watch_s")),
                        _float(row.get("completion_rate")),
                        _int(row.get("profile_visits")),
                        _int(row.get("site_clicks")),
                    ),
                )
        return len(rows)

    def enqueue(
        self,
        name: str,
        sex: str,
        video_format: str,
        hook_style: str | None,
        experiment: str | None,
        source: str = "manual",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO content_queue"
                "(name, sex, format, hook_style, experiment, source, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    sex,
                    video_format,
                    hook_style,
                    experiment,
                    source,
                    datetime.now(tz=UTC).isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Queue insert did not return an ID")
            return cursor.lastrowid


def _int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
