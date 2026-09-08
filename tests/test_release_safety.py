"""Regression checks for source/approval binding and fail-closed release behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from nobodynamed_video.batch.runner import run_batch
from nobodynamed_video.data.snapshot import SnapshotSource, verified_snapshot
from nobodynamed_video.editorial.story import approve_story, evaluate_story, load_story
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.models import CountClaim
from nobodynamed_video.qc.checks import QCIssue, QCResult, _check_audio_loudness
from nobodynamed_video.release import stage_release

from tests.test_frame_planner import make_bertha_spec

LAUNCH = Path("stories/launch-2025")


def test_six_launch_drafts_pass_facts_and_copy_but_require_human_approval() -> None:
    paths = sorted(LAUNCH.glob("*.yaml"))
    assert len(paths) == 6
    for path in paths:
        story = load_story(path)
        assert evaluate_story(story, require_approval=False).publishable
        assert not evaluate_story(story).publishable
        assert not story.approved_by and story.approved_at is None


def test_wrong_count_and_altered_snapshot_are_rejected() -> None:
    story = load_story(LAUNCH / "bertha-2025.yaml")
    wrong = story.model_copy(update={"count_claims": [CountClaim(year=2025, count=9)]})
    with pytest.raises(StoryQualityError, match="disagrees"):
        verified_snapshot(wrong)
    with pytest.raises(StoryQualityError, match="SHA256 mismatch"):
        verified_snapshot(story.model_copy(update={"data_sha256": "0" * 64}))


def test_copy_edit_invalidates_approval_without_a_new_reviewer() -> None:
    # In-memory test approval only; no story file or real approval is written.
    story = approve_story(load_story(LAUNCH / "bertha-2025.yaml"), "unit-test-only")
    assert evaluate_story(story).publishable
    changed = story.model_copy(update={"subhead": "An unreviewed replacement."})
    assert not evaluate_story(changed).publishable
    assert "approval does not cover the current story content" in evaluate_story(changed).blockers


@pytest.mark.asyncio
async def test_kunta_suppression_keeps_numeric_compatibility_without_claiming_zero() -> None:
    story = load_story(LAUNCH / "kunta-2025.yaml")
    snapshot = verified_snapshot(story)
    record = await SnapshotSource(snapshot).get_record("Kunta", "M", 2025)
    assert record.current_count == 0  # classification compatibility, not a published observation
    assert not record.series[-1].reported
    assert next(p for p in record.series if p.year == 2000).count == 6
    assert snapshot.observations[-1].count is None


@pytest.mark.asyncio
async def test_composed_but_qc_failed_batch_exits_nonzero(tmp_path: Path) -> None:
    result = {
        "id": "bertha-2024",
        "frames": 330,
        "composed": True,
        "mp4": str(tmp_path / "bertha-2024.mp4"),
    }
    qc = QCResult("bertha-2024", False, [QCIssue("error", "NARRATION", "missing narration")])
    with (
        patch("nobodynamed_video.batch.runner.SatoriClient", return_value=AsyncMock()),
        patch("nobodynamed_video.batch.runner.render_spec", new=AsyncMock(return_value=result)),
        patch("nobodynamed_video.batch.runner.run_all_checks", return_value=qc),
        patch("nobodynamed_video.batch.runner.build_qc_report", return_value=tmp_path / "qc.html"),
        patch("nobodynamed_video.batch.runner._STATE_DB", tmp_path / "state.db"),
        pytest.raises(SystemExit, match="1 video"),
    ):
        await run_batch(
            [make_bertha_spec()],
            "http://localhost:1",
            tmp_path,
            batch_name="failed",
            narration_enabled=False,
        )
    summary = json.loads((tmp_path / "failed.summary.json").read_text())
    assert summary["failed"] == 1 and summary["succeeded"] == 0
    assert summary["release_ids"] == []
    with pytest.raises(ValueError, match="complete"):
        stage_release(tmp_path / "failed.summary.json", tmp_path / "release")


def test_release_stages_only_allowlisted_complete_packages(tmp_path: Path) -> None:
    for suffix in (".mp4", ".json", ".story.json", ".source.json"):
        (tmp_path / f"approved{suffix}").write_bytes(b"test-content")
    (tmp_path / "stale.mp4").write_bytes(b"not in the batch")
    summary = {
        "total": 1,
        "succeeded": 1,
        "failed": 0,
        "errors": [],
        "qc_failed": [],
        "release_ids": ["approved"],
        "results": [{"id": "approved", "composed": True, "qc": {"passed": True}}],
    }
    path = tmp_path / "batch.summary.json"
    path.write_text(json.dumps(summary))
    staged = stage_release(path, tmp_path / "release")
    assert "stale.mp4" not in staged
    assert "approved.story.json" in staged and "approved.source.json" in staged
    (tmp_path / "approved.source.json").unlink()
    with pytest.raises(ValueError, match="missing release file"):
        stage_release(path, tmp_path / "second-release")


def test_actual_silent_audio_is_fatal(tmp_path: Path) -> None:
    path = tmp_path / "silence.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono",
            "-t",
            "1",
            str(path),
        ],
        check=True,
    )
    issues = _check_audio_loudness(path)
    assert any(i.code == "SILENT_NARRATION" and i.severity == "error" for i in issues)
