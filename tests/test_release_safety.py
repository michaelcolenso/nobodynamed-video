"""Regression checks for source/approval binding and fail-closed release behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from nobodynamed_video.batch.runner import run_batch
from nobodynamed_video.data.ctx import load_cultural_events
from nobodynamed_video.data.snapshot import Snapshot, SnapshotSource, verified_snapshot
from nobodynamed_video.editorial.story import approve_story, evaluate_story, load_story
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.models import CountClaim, StoryKind
from nobodynamed_video.qc.checks import QCIssue, QCResult, _check_audio_loudness
from nobodynamed_video.release import stage_release
from pydantic import ValidationError
from ruamel.yaml import YAML

from tests.test_frame_planner import make_bertha_spec

LAUNCH = Path("stories/launch-2025")


def test_six_launch_stories_are_currently_approved_and_publishable() -> None:
    paths = sorted(LAUNCH.glob("*.yaml"))
    assert len(paths) == 6
    for path in paths:
        story = load_story(path)
        assert evaluate_story(story, require_approval=False).publishable
        assert evaluate_story(story).publishable
        assert story.approved_by
        assert story.approved_at is not None
        assert story.approved_content_sha256


def test_wrong_count_and_altered_snapshot_are_rejected() -> None:
    story = load_story(LAUNCH / "bertha-2025.yaml")
    wrong = story.model_copy(update={"count_claims": [CountClaim(year=2025, count=9)]})
    with pytest.raises(StoryQualityError, match="disagrees"):
        verified_snapshot(wrong)
    with pytest.raises(StoryQualityError, match="SHA256 mismatch"):
        verified_snapshot(story.model_copy(update={"data_sha256": "0" * 64}))


def _archive_snapshot_payload() -> dict[str, object]:
    return json.loads((Path("data/ssa-2025") / "kunta-m.json").read_text())


def test_archive_snapshot_still_requires_its_sha256_and_a_rank_per_reported_year() -> None:
    payload = _archive_snapshot_payload()
    without_hash = {k: v for k, v in payload.items() if k != "archive_sha256"}
    with pytest.raises(ValidationError, match="must pin the archive SHA256"):
        Snapshot.model_validate(without_hash)

    rankless = _archive_snapshot_payload()
    reported = next(o for o in rankless["observations"] if o["count"] is not None)
    reported["rank"] = None
    with pytest.raises(ValidationError, match="both be present or absent"):
        Snapshot.model_validate(rankless)


def test_dataset_snapshot_may_omit_ranks_but_not_claim_an_archive() -> None:
    payload = _archive_snapshot_payload()
    dataset = {k: v for k, v in payload.items() if k not in {"source_url", "archive_sha256"}}
    dataset["source_dataset"] = "nobodynamed-d1:name-vitals"
    dataset["observations"] = [
        {"year": o["year"], "count": o["count"]} for o in payload["observations"]
    ]
    snapshot = Snapshot.model_validate(dataset)
    assert not snapshot.from_ssa_archive
    assert next(o for o in snapshot.observations if o.year == 1977).count == 215

    forged = dict(dataset, archive_sha256="0" * 64)
    with pytest.raises(ValidationError, match="must not claim an SSA archive SHA256"):
        Snapshot.model_validate(forged)

    ranked_gap = dict(dataset)
    ranked_gap["observations"] = [
        {"year": o["year"], "count": o["count"], "rank": None if o["count"] else 12}
        for o in payload["observations"]
    ]
    with pytest.raises(ValidationError, match="unreported year must not carry a rank"):
        Snapshot.model_validate(ranked_gap)


def test_snapshot_must_declare_exactly_one_provenance() -> None:
    payload = _archive_snapshot_payload()
    both = dict(payload, source_dataset="nobodynamed-d1:name-vitals")
    with pytest.raises(ValidationError, match="exactly one of source_url or source_dataset"):
        Snapshot.model_validate(both)

    neither = {k: v for k, v in payload.items() if k not in {"source_url", "archive_sha256"}}
    with pytest.raises(ValidationError, match="exactly one of source_url or source_dataset"):
        Snapshot.model_validate(neither)


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
    for suffix in (".mp4", ".json", ".story.json"):
        (tmp_path / f"approved{suffix}").write_bytes(b"test-content")
    # runner.py writes the approved snapshot verbatim into .source.json, and staging
    # now reads it back to confirm archive provenance, so the fixture must be one.
    (tmp_path / "approved.source.json").write_bytes(
        Path("data/ssa-2025/jennifer-f.json").read_bytes()
    )
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


VIRAL = Path("stories/viral-2025")


def test_viral_ten_stories_are_gate_clean_except_for_human_approval() -> None:
    """The ten viral-ten stories are render-ready the moment a reviewer approves them."""
    paths = sorted(VIRAL.glob("*.yaml"))
    assert len(paths) == 10
    for path in paths:
        story = load_story(path)
        evaluation = evaluate_story(story, require_approval=False)
        assert evaluation.publishable, (path.name, evaluation.blockers)
        assert evaluation.score == 100, (path.name, evaluation.components)
        # Every published number is pinned to the snapshot, not to the copy.
        assert story.count_claims
        verified_snapshot(story)
        # Unapproved by design: approval is a human act, never a generated field.
        assert evaluate_story(story).blockers == [
            "story has not been approved",
            "approval metadata is incomplete",
            "approval does not cover the current story content",
        ]


def test_viral_ten_batch_entries_match_their_stories() -> None:
    yaml = YAML(typ="safe")
    entries = yaml.load(Path("batches/viral-ten.yaml").read_text())["videos"]
    assert len(entries) == 10
    for entry in entries:
        story = load_story(Path(str(entry["story"])))
        assert (story.id, story.name, story.sex) == (entry["id"], entry["name"], entry["sex"])


def test_release_rejects_a_dataset_snapshot_even_when_everything_else_passes(
    tmp_path: Path,
) -> None:
    """Approval may rest on a connector snapshot; publication may not."""
    ids = ["taylor-2025"]
    summary = tmp_path / "viral.summary.json"
    summary.write_text(
        json.dumps(
            {
                "release_ids": ids,
                "failed": 0,
                "errors": [],
                "qc_failed": 0,
                "total": 1,
                "succeeded": 1,
                "results": [{"id": ids[0], "composed": True, "qc": {"passed": True}}],
            }
        )
    )
    for suffix in (".mp4", ".json", ".story.json"):
        (tmp_path / f"{ids[0]}{suffix}").write_text("x")
    (tmp_path / f"{ids[0]}.source.json").write_bytes(
        Path("data/nobodynamed-2025/taylor-f.json").read_bytes()
    )
    with pytest.raises(ValueError, match="requires an archive-pinned snapshot"):
        stage_release(summary, tmp_path / "staged")

    # The same package backed by an archive snapshot stages normally.
    (tmp_path / f"{ids[0]}.source.json").write_bytes(
        Path("data/ssa-2025/jennifer-f.json").read_bytes()
    )
    assert stage_release(summary, tmp_path / "staged-ok")


def test_viral_ten_event_markers_are_declared_in_the_story_anchors() -> None:
    """A rendered event marker must not contradict the copy a reviewer approved.

    build_base_context always resolves fixtures/cultural_events.yaml, so a
    cultural_rupture story inherits any shared marker for its name whether or not the
    story mentions it. Adolph inherited a 1945 World War II line under a 1933 thesis.
    """
    events = load_cultural_events()
    for path in sorted(VIRAL.glob("*.yaml")):
        story = load_story(path)
        event = events.get((story.name.lower(), story.sex))
        draws_marker = (
            story.story_kind == StoryKind.CULTURAL_RUPTURE
            and event is not None
            and bool(str(event.get("killing_event", "")).strip())
        )
        if not draws_marker:
            continue
        assert event is not None
        year = str(event["event_year"])
        assert any(year in anchor for anchor in story.visual_anchors), (
            path.name,
            year,
            story.visual_anchors,
        )
