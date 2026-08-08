"""Retention CSV normalization and action-report tests."""

import json
from pathlib import Path

from nobodynamed_video.analytics.retention import (
    build_retention_report,
    import_retention_csv,
    parse_retention_csv,
    write_retention_report,
)


def _write_export(path: Path) -> None:
    path.write_text(
        "video_id,views,avg_watch_time,watched_full_video,shares,saves,2s_retention\n"
        "hazel-2024,5000,8.5,60%,100,50,80%\n"
    )


def test_parse_retention_csv_normalizes_percentages(tmp_path: Path) -> None:
    export = tmp_path / "retention.csv"
    _write_export(export)
    record = parse_retention_csv(export)[0]
    assert record.spec_id == "hazel-2024"
    assert record.completion_rate == 0.60
    assert record.retention_2s == 0.80
    assert record.share_rate == 0.02


def test_retention_report_joins_manifest_and_recommends_scale(tmp_path: Path) -> None:
    export = tmp_path / "retention.csv"
    db = tmp_path / "retention.db"
    out = tmp_path / "out"
    out.mkdir()
    _write_export(export)
    (out / "hazel-2024.json").write_text(
        json.dumps({"duration_s": 11.5, "story_kind": "comeback", "story_score": 85})
    )

    assert import_retention_csv(export, db) == 1
    report = build_retention_report(db, out)
    assert report[0]["story_kind"] == "comeback"
    assert report[0]["decision"] == "scale this story shape"

    json_path, markdown_path = write_retention_report(db, out)
    assert json_path.exists()
    assert "scale this story shape" in markdown_path.read_text()
