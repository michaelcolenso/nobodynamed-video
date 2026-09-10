"""Publish a staged next-six release without replacing other videos or branch history."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from nobodynamed_video.release import stage_release

NEXT_SIX = {"rihanna-2025", "miley-2025", "aaliyah-2025", "elsa-2025", "leia-2025", "atlas-2025"}


def publish_release(release: Path, source_sha: str) -> None:
    """Require a complete staged package, then fast-forward the existing videos branch.

    Call only after D1, human approval, render/QC, and artifact upload succeed.
    This validates package completeness; it does not replace those upstream gates.
    A concurrent branch update rejects the push rather than overwriting it.
    """
    release = release.resolve()
    summary = release / "next-six.summary.json"
    if any(path.is_symlink() or not path.is_file() for path in release.iterdir()):
        raise ValueError("release must contain only regular files")
    if set(json.loads(summary.read_text()).get("release_ids", [])) != NEXT_SIX:
        raise ValueError("release must contain exactly the next six IDs")
    with tempfile.TemporaryDirectory(prefix="next-six-publish-") as temporary:
        root = Path(temporary)
        staged = root / "staged"
        files = stage_release(summary, staged)
        if {path.name for path in release.iterdir()} != set(files):
            raise ValueError("unexpected files in staged release")
        subprocess.run(["git", "fetch", "origin", "refs/heads/videos"], check=True)
        checkout = root / "videos"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(checkout), "FETCH_HEAD"], check=True
        )
        try:
            # Check every destination before copying; never follow branch symlinks.
            for name in files:
                target = checkout / name
                if target.is_symlink() or (target.exists() and not target.is_file()):
                    raise ValueError(f"unsafe release destination: {name}")
            for name in files:
                shutil.copyfile(staged / name, checkout / name)
            subprocess.run(["git", "-C", str(checkout), "add", "--", *files], check=True)
            diff = subprocess.run(["git", "-C", str(checkout), "diff", "--cached", "--quiet"])
            if diff.returncode == 0:
                print("Verified release already published; no changes.")
                return
            if diff.returncode != 1:
                diff.check_returncode()
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "-c",
                    "user.name=github-actions[bot]",
                    "-c",
                    "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                    "commit",
                    "-m",
                    f"Publish verified next-six release from {source_sha}",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(checkout), "push", "origin", "HEAD:refs/heads/videos"], check=True
            )
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(checkout)], check=True)


if __name__ == "__main__":
    publish_release(Path(sys.argv[1]), sys.argv[2])
