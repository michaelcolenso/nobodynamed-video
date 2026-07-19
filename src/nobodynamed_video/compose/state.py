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
CREATE TABLE IF NOT EXISTS caption_reservations (
    combo_hash  TEXT PRIMARY KEY,
    tags_json   TEXT NOT NULL,
    spec_id     TEXT NOT NULL,
    reserved_at TEXT NOT NULL
);
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
                "SELECT 1 FROM used_combinations WHERE combo_hash = ? "
                "UNION ALL SELECT 1 FROM caption_reservations WHERE combo_hash = ?",
                (combo_hash, combo_hash),
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

    def combination_for_spec(self, spec_id: str) -> tuple[str, list[str]] | None:
        """Return the already-shipped combination for an idempotent rerender."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT combo_hash, tags_json FROM used_combinations "
                "WHERE first_used_spec = ? ORDER BY first_used_at LIMIT 1",
                (spec_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return str(row["combo_hash"]), [str(tag) for tag in json.loads(row["tags_json"])]

    def reserve(self, combo_hash: str, tags: list[str], spec_id: str) -> bool:
        """Atomically reserve a combination while a render is in flight."""
        now = datetime.now(tz=UTC).isoformat()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            used = conn.execute(
                "SELECT 1 FROM used_combinations WHERE combo_hash = ?", (combo_hash,)
            ).fetchone()
            if used:
                conn.rollback()
                return False
            cursor = conn.execute(
                "INSERT OR IGNORE INTO caption_reservations VALUES (?, ?, ?, ?)",
                (combo_hash, json.dumps(sorted(tags)), spec_id, now),
            )
            conn.commit()
            return cursor.rowcount == 1
        finally:
            conn.close()

    def commit_reservation(self, combo_hash: str) -> None:
        """Ship a reserved combination only after render and QC succeed."""
        now = datetime.now(tz=UTC).isoformat()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT tags_json, spec_id FROM caption_reservations WHERE combo_hash = ?",
                (combo_hash,),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"Caption reservation not found: {combo_hash}")
            conn.execute(
                "INSERT INTO used_combinations "
                "(combo_hash, tags_json, first_used_at, first_used_spec) VALUES (?, ?, ?, ?)",
                (combo_hash, row["tags_json"], now, row["spec_id"]),
            )
            conn.execute("DELETE FROM caption_reservations WHERE combo_hash = ?", (combo_hash,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release_reservation(self, combo_hash: str) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM caption_reservations WHERE combo_hash = ?", (combo_hash,))
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
            conn.execute("DELETE FROM caption_reservations")
            conn.commit()
        finally:
            conn.close()
