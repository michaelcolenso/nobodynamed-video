"""Exercise publication against real local Git repositories."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from nobodynamed_video.publish_release import NEXT_SIX, publish_release
from ruamel.yaml import YAML

# Tests chdir into a temporary checkout, so repo fixtures need an absolute path.
REPO = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


@pytest.fixture
def publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    git("init", "--bare", str(remote))
    checkout = tmp_path / "checkout"
    git("clone", str(remote), str(checkout))
    monkeypatch.chdir(checkout)
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    git("switch", "--orphan", "videos")
    Path("earlier.mp4").write_bytes(b"existing release")
    git("add", ".")
    git("commit", "-m", "Existing release")
    git("push", "origin", "videos")
    git("switch", "-c", "main")
    release = tmp_path / "release"
    release.mkdir()
    # .source.json is the approved snapshot copied verbatim, and staging reads it back
    # to confirm archive provenance, so these fixtures must be real archive snapshots.
    archive_snapshot = (REPO / "data" / "ssa-2025" / "jennifer-f.json").read_bytes()
    for name in NEXT_SIX:
        for suffix in (".mp4", ".json", ".story.json"):
            (release / f"{name}{suffix}").write_bytes(b"verified artifact")
        (release / f"{name}.source.json").write_bytes(archive_snapshot)
    (release / "next-six.summary.json").write_text(
        json.dumps(
            {
                "total": 6,
                "succeeded": 6,
                "failed": 0,
                "errors": [],
                "qc_failed": [],
                "release_ids": sorted(NEXT_SIX),
                "results": [
                    {"id": name, "composed": True, "qc": {"passed": True}}
                    for name in sorted(NEXT_SIX)
                ],
            }
        )
    )
    return release, remote


def test_publish_preserves_existing_files_history_and_is_idempotent(
    publication: tuple[Path, Path],
) -> None:
    release, remote = publication
    old = git("--git-dir", str(remote), "rev-parse", "videos")
    publish_release(release, "test-source")
    new = git("--git-dir", str(remote), "rev-parse", "videos")
    assert new != old
    assert git("--git-dir", str(remote), "rev-parse", "videos^") == old
    assert git("--git-dir", str(remote), "show", "videos:earlier.mp4") == "existing release"
    for path in release.iterdir():
        # git() strips; the snapshot fixtures end in a newline, so strip both sides.
        published = git("--git-dir", str(remote), "show", f"videos:{path.name}")
        assert published == path.read_text().strip()
    assert git("branch", "--show-current") == "main"
    publish_release(release, "test-source")
    assert git("--git-dir", str(remote), "rev-parse", "videos") == new


@pytest.mark.parametrize("damage", ["missing", "extra", "qc", "symlink", "wrong_ids"])
def test_invalid_release_never_updates_remote(publication: tuple[Path, Path], damage: str) -> None:
    release, remote = publication
    old = git("--git-dir", str(remote), "rev-parse", "videos")
    if damage == "missing":
        (release / "atlas-2025.source.json").unlink()
    elif damage == "extra":
        (release / "unrelated.mp4").write_text("not approved")
    elif damage == "symlink":
        (release / "atlas-2025.mp4").unlink()
        (release / "atlas-2025.mp4").symlink_to(release / "leia-2025.mp4")
    else:
        path = release / "next-six.summary.json"
        summary = json.loads(path.read_text())
        if damage == "qc":
            summary["results"][0]["qc"]["passed"] = False
        else:
            summary["release_ids"][0] = "unapproved"
        path.write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        publish_release(release, "test-source")
    assert git("--git-dir", str(remote), "rev-parse", "videos") == old


def test_next_six_workflow_keeps_success_gates_and_manual_trigger() -> None:
    workflow = YAML(typ="safe").load(Path(".github/workflows/render-next-six.yaml"))
    assert set(workflow["on"]) == {"workflow_dispatch"}
    job = workflow["jobs"]["render"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["permissions"]["contents"] == "write"
    steps = job["steps"]
    names = [step.get("name") for step in steps]
    gated = [
        "Verify current D1 data against checked-in next-six snapshots",
        "Verify approved story content",
        "Render next-six batch",
        "Stage verified release",
        "Upload verified release",
        "Publish verified release to videos branch",
    ]
    assert [names.index(name) for name in gated] == sorted(names.index(name) for name in gated)
    for step in steps:
        assert not step.get("continue-on-error", False)
        if step.get("name") in gated:
            assert step.get("if", "success()") == "success()"
    assert "snapshot_from_d1.py" in steps[names.index(gated[0])]["run"]
    assert "nbn story score" in steps[names.index(gated[1])]["run"]


def test_concurrent_update_rejects_push_without_losing_other_commit(
    publication: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    release, remote = publication
    original_run = subprocess.run
    raced = False

    def race(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal raced
        command = args[0]
        if isinstance(command, list) and "push" in command and not raced:
            raced = True
            Path("concurrent.txt").write_text("keep this update")
            git("add", "concurrent.txt")
            git("commit", "-m", "Concurrent publication")
            git("push", "origin", "HEAD:videos")
        return original_run(*args, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(subprocess, "run", race)
    with pytest.raises(subprocess.CalledProcessError):
        publish_release(release, "test-source")
    assert git("--git-dir", str(remote), "show", "videos:concurrent.txt") == "keep this update"
    assert "atlas-2025.mp4" not in git("--git-dir", str(remote), "ls-tree", "--name-only", "videos")


def test_destination_symlink_is_rejected(publication: tuple[Path, Path]) -> None:
    release, remote = publication
    Path("atlas-2025.mp4").symlink_to("earlier.mp4")
    git("add", "atlas-2025.mp4")
    git("commit", "-m", "Destination symlink")
    git("push", "origin", "HEAD:videos")
    old = git("--git-dir", str(remote), "rev-parse", "videos")
    with pytest.raises(ValueError, match="unsafe release destination"):
        publish_release(release, "test-source")
    assert git("--git-dir", str(remote), "rev-parse", "videos") == old
