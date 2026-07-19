"""Release state, format, importer, and operations tests."""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path

import pytest
from nobodynamed_video.batch.spec import _make_scenes
from nobodynamed_video.compose.state import CombinationState
from nobodynamed_video.models import NameRecord, VideoFormat, VideoSpec, YearCount
from nobodynamed_video.operations.ledger import PublishingLedger
from nobodynamed_video.render.frame_planner import spec_duration, spec_frame_count
from nobodynamed_video.render.golden import check_or_write_golden

from scripts.fetch_ssa import _build_database


def test_caption_reservation_is_transactional(tmp_path: Path) -> None:
    state = CombinationState(tmp_path / "state.db")
    assert state.reserve("hash", ["one", "two"], "spec")
    assert not state.reserve("hash", ["one", "two"], "other")
    assert state.stats() == {"combos": 0, "uses": 0}
    state.commit_reservation("hash")
    assert state.stats() == {"combos": 1, "uses": 1}


def test_failed_render_can_release_caption(tmp_path: Path) -> None:
    state = CombinationState(tmp_path / "state.db")
    assert state.reserve("hash", ["one"], "spec")
    state.release_reservation("hash")
    assert state.reserve("hash", ["one"], "rerender")


def test_committed_combination_is_idempotent_by_spec(tmp_path: Path) -> None:
    state = CombinationState(tmp_path / "state.db")
    assert state.reserve("hash", ["one", "two"], "spec")
    state.commit_reservation("hash")
    assert state.combination_for_spec("spec") == ("hash", ["one", "two"])


@pytest.mark.parametrize(
    ("video_format", "duration"),
    [
        (VideoFormat.FAST, 18.0),
        (VideoFormat.EXPLAINER, 40.0),
        (VideoFormat.DEEP_STORY, 88.0),
    ],
)
def test_format_durations(video_format: VideoFormat, duration: float) -> None:
    record = NameRecord(
        name="Test",
        sex="F",
        series=[YearCount(year=2025, count=5)],
        peak_year=2025,
        peak_count=5,
        current_year=2025,
        current_count=5,
    )
    spec = VideoSpec(
        id="test",
        record=record,
        tier="stable",
        scenes=_make_scenes(video_format),
        seed=1,
        format=video_format,
    )
    assert spec_duration(spec) == duration
    assert spec_frame_count(spec) == round(duration * 30)


def test_golden_creation_requires_explicit_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nobodynamed_video.render.golden as golden

    monkeypatch.setattr(golden, "GOLDEN_DIR", tmp_path)
    with pytest.raises(AssertionError, match="Missing golden"):
        check_or_write_golden("spec", "frame", b"png")
    check_or_write_golden("spec", "frame", b"png", update=True)
    check_or_write_golden("spec", "frame", b"png")


def test_official_import_records_provenance(tmp_path: Path) -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("yob2025.txt", "Alice,F,5\nBob,M,7\n")
    target = tmp_path / "ssa.sqlite"
    year, rows = _build_database(payload.getvalue(), target, "https://ssa.example/names.zip")
    assert (year, rows) == (2025, 2)
    with sqlite3.connect(target) as conn:
        metadata = conn.execute(
            "SELECT source, dataset_year, synthetic, length(sha256) FROM dataset_metadata"
        ).fetchone()
    assert metadata == ("US Social Security Administration", 2025, 0, 64)


def test_publishing_ledger_and_metrics_import(tmp_path: Path) -> None:
    ledger = PublishingLedger(tmp_path / "publishing.db")
    queue_id = ledger.enqueue("Alice", "F", "fast", None, "hook-a")
    assert queue_id == 1
    ledger.record_publication("alice-2025", "tiktok", "123", None, "fast")
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text(
        "platform,external_id,measured_at,views,completion_rate\n"
        "tiktok,123,2026-07-19T00:00:00Z,1000,0.42\n"
    )
    assert ledger.import_metrics_csv(csv_path) == 1
    with sqlite3.connect(ledger.path) as conn:
        row = conn.execute("SELECT views, completion_rate FROM metrics").fetchone()
    assert row == (1000, 0.42)
