"""Regression tests for the dark-brand cover-frame QC threshold."""

from __future__ import annotations

import subprocess
from pathlib import Path

from nobodynamed_video.qc import checks


def _make_cover(path: Path, *, populated: bool) -> None:
    filters = "color=c=black:s=1080x1920:d=0.04"
    if populated:
        # Roughly 2% bright content: dark overall, but visibly non-empty.
        filters += ",drawbox=x=40:y=60:w=220:h=200:color=white:t=fill"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            filters,
            "-frames:v",
            "1",
            "-y",
            str(path),
        ],
        check=True,
    )


def test_story_cover_policy_rejects_blank_but_allows_dark_populated_frame(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blank_dir = tmp_path / "blank" / "frames"
    populated_dir = tmp_path / "populated" / "frames"
    blank_dir.mkdir(parents=True)
    populated_dir.mkdir(parents=True)
    _make_cover(blank_dir / "frame_0000.png", populated=False)
    _make_cover(populated_dir / "frame_0000.png", populated=True)

    monkeypatch.setattr(checks, "_COVER_BLACK_AMOUNT", 99)

    blank_issues = checks._check_cover_frame(blank_dir)
    populated_issues = checks._check_cover_frame(populated_dir)
    assert any(issue.code == "BLACK_COVER" for issue in blank_issues)
    assert populated_issues == []
