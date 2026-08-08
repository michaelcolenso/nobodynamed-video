"""Import per-video retention exports and turn them into editorial decisions."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class RetentionRecord(BaseModel):
    spec_id: str
    views: int = Field(ge=0)
    average_watch_time_s: float = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    shares: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    retention_2s: float | None = Field(default=None, ge=0, le=1)
    midpoint_retention: float | None = Field(default=None, ge=0, le=1)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @property
    def share_rate(self) -> float:
        return self.shares / self.views if self.views else 0.0

    @property
    def save_rate(self) -> float:
        return self.saves / self.views if self.views else 0.0


_ALIASES = {
    "spec_id": ("spec_id", "video_id", "name", "video"),
    "views": ("views", "video_views"),
    "average_watch_time_s": ("average_watch_time_s", "avg_watch_time", "average_watch_time"),
    "completion_rate": ("completion_rate", "watched_full_video", "full_watch_rate"),
    "shares": ("shares",),
    "saves": ("saves", "favorites", "favourites"),
    "retention_2s": ("retention_2s", "2s_retention", "two_second_retention"),
    "midpoint_retention": ("midpoint_retention", "50pct_retention", "halfway_retention"),
}


def _value(row: dict[str, str], field: str, *, required: bool = True) -> str | None:
    normalized = {key.strip().lower().replace(" ", "_"): value for key, value in row.items()}
    for alias in _ALIASES[field]:
        value = normalized.get(alias)
        if value is not None and value.strip() != "":
            return value.strip()
    if required:
        raise ValueError(f"Retention CSV is missing required field {field!r}")
    return None


def _integer(value: str) -> int:
    return int(float(value.replace(",", "")))


def _percent(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip().replace(",", "")
    if stripped.endswith("%"):
        return float(stripped[:-1]) / 100.0
    number = float(stripped)
    return number / 100.0 if number > 1 else number


def parse_retention_csv(path: Path) -> list[RetentionRecord]:
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"Retention CSV has no rows: {path}")
    return [
        RetentionRecord(
            spec_id=str(_value(row, "spec_id")),
            views=_integer(str(_value(row, "views"))),
            average_watch_time_s=float(str(_value(row, "average_watch_time_s"))),
            completion_rate=float(_percent(_value(row, "completion_rate")) or 0),
            shares=_integer(_value(row, "shares", required=False) or "0"),
            saves=_integer(_value(row, "saves", required=False) or "0"),
            retention_2s=_percent(_value(row, "retention_2s", required=False)),
            midpoint_retention=_percent(_value(row, "midpoint_retention", required=False)),
        )
        for row in rows
    ]


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS retention_snapshots (
            spec_id TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            views INTEGER NOT NULL,
            average_watch_time_s REAL NOT NULL,
            completion_rate REAL NOT NULL,
            shares INTEGER NOT NULL,
            saves INTEGER NOT NULL,
            retention_2s REAL,
            midpoint_retention REAL,
            PRIMARY KEY (spec_id, captured_at)
        )
        """
    )
    return conn


def import_retention_csv(csv_path: Path, db_path: Path) -> int:
    records = parse_retention_csv(csv_path)
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO retention_snapshots (
                spec_id, captured_at, views, average_watch_time_s,
                completion_rate, shares, saves, retention_2s, midpoint_retention
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    record.spec_id,
                    record.captured_at.isoformat(),
                    record.views,
                    record.average_watch_time_s,
                    record.completion_rate,
                    record.shares,
                    record.saves,
                    record.retention_2s,
                    record.midpoint_retention,
                )
                for record in records
            ],
        )
    return len(records)


def _latest_records(db_path: Path) -> list[RetentionRecord]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT r.spec_id, r.captured_at, r.views, r.average_watch_time_s,
                   r.completion_rate, r.shares, r.saves,
                   r.retention_2s, r.midpoint_retention
            FROM retention_snapshots r
            JOIN (
                SELECT spec_id, MAX(captured_at) AS captured_at
                FROM retention_snapshots GROUP BY spec_id
            ) latest USING (spec_id, captured_at)
            ORDER BY r.views DESC
            """
        ).fetchall()
    return [
        RetentionRecord(
            spec_id=str(row[0]),
            captured_at=datetime.fromisoformat(str(row[1])),
            views=int(row[2]),
            average_watch_time_s=float(row[3]),
            completion_rate=float(row[4]),
            shares=int(row[5]),
            saves=int(row[6]),
            retention_2s=float(row[7]) if row[7] is not None else None,
            midpoint_retention=float(row[8]) if row[8] is not None else None,
        )
        for row in rows
    ]


def _manifest(out_dir: Path, spec_id: str) -> dict[str, object]:
    path = out_dir / f"{spec_id}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return raw if isinstance(raw, dict) else {}


def _decision(record: RetentionRecord, watch_ratio: float) -> str:
    if record.views < 1000:
        return "collect more data"
    if record.retention_2s is not None and record.retention_2s < 0.65:
        return "rewrite the first two seconds"
    if record.completion_rate < 0.45 or watch_ratio < 0.70:
        return "tighten the middle and reveal sooner"
    if record.share_rate < 0.015:
        return "keep the premise; strengthen the ending and share prompt"
    return "scale this story shape"


def build_retention_report(db_path: Path, out_dir: Path) -> list[dict[str, object]]:
    report: list[dict[str, object]] = []
    for record in _latest_records(db_path):
        manifest = _manifest(out_dir, record.spec_id)
        duration_s = float(str(manifest.get("duration_s") or 0))
        watch_ratio = record.average_watch_time_s / duration_s if duration_s else 0.0
        report.append(
            {
                "spec_id": record.spec_id,
                "story_kind": manifest.get("story_kind"),
                "story_score": manifest.get("story_score"),
                "views": record.views,
                "completion_rate": round(record.completion_rate, 4),
                "average_watch_time_s": record.average_watch_time_s,
                "watch_ratio": round(watch_ratio, 4),
                "share_rate": round(record.share_rate, 4),
                "save_rate": round(record.save_rate, 4),
                "retention_2s": record.retention_2s,
                "midpoint_retention": record.midpoint_retention,
                "decision": _decision(record, watch_ratio),
            }
        )
    return report


def write_retention_report(db_path: Path, out_dir: Path) -> tuple[Path, Path]:
    rows = build_retention_report(db_path, out_dir)
    json_path = out_dir / "retention-report.json"
    markdown_path = out_dir / "retention-report.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({"videos": rows}, indent=2) + "\n")

    lines = [
        "# Retention decision report",
        "",
        "Initial decision rules: 1,000-view evidence floor, 45% completion, "
        "70% watch ratio, and 1.5% share rate. Recalibrate after 20 comparable posts.",
        "",
        "| Video | Shape | Views | Complete | Watch ratio | Share rate | Decision |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['spec_id']} | {row['story_kind'] or 'unknown'} | "
            f"{int(str(row['views'])):,} | {float(str(row['completion_rate'])):.1%} | "
            f"{float(str(row['watch_ratio'])):.1%} | "
            f"{float(str(row['share_rate'])):.1%} | "
            f"{row['decision']} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n")
    return json_path, markdown_path
