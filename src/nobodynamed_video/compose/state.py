"""SQLite-backed hashtag combination tracker."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS used_combinations (
    combo_hash      TEXT PRIMARY KEY,
    tags_json       TEXT NOT NULL,
    first_used_at   TEXT NOT NULL,
    first_used_spec TEXT NOT NULL,
    use_count       INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_combo_first_used
    ON used_combinations(first_used_at DESC);
"""


class CombinationState:
    """Tracks shipped hashtag sets to enforce combination uniqueness."""

    def __init__(self, db_path: Path) -> None:
        """Open (or create) the state DB and ensure the schema exists."""
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        conn = self._connect()
        conn.executescript(_DDL)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def is_used(self, combo_hash: str) -> bool:
        """Return True if this combo hash has been recorded."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM used_combinations WHERE combo_hash = ?",
                (combo_hash,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def record(self, combo_hash: str, tags: list[str], spec_id: str) -> None:
        """Persist a new combo; increment use_count if it already exists."""
        now = datetime.now(tz=UTC).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO used_combinations
                    (combo_hash, tags_json, first_used_at, first_used_spec)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(combo_hash) DO UPDATE SET use_count = use_count + 1
                """,
                (combo_hash, json.dumps(sorted(tags)), now, spec_id),
            )
            conn.commit()
        finally:
            conn.close()

    def tag_uses_this_week(self, tag: str) -> int:
        """Count combos recorded in the last 7 days that include *tag*."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=7)).isoformat()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT tags_json FROM used_combinations WHERE first_used_at >= ?",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()
        return sum(1 for row in rows if tag in json.loads(row["tags_json"]))

    def stats(self) -> dict[str, int]:
        """Return total combinations recorded and total uses."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS combos, COALESCE(SUM(use_count), 0) AS uses "
                "FROM used_combinations"
            ).fetchone()
            return {"combos": int(row["combos"]), "uses": int(row["uses"])}
        finally:
            conn.close()

    def reset(self) -> None:
        """Wipe all records."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM used_combinations")
            conn.commit()
        finally:
            conn.close()
