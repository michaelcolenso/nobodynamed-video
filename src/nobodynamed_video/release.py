"""Stage only a completely successful, QC-passed release; never glob arbitrary outputs."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from nobodynamed_video.data.snapshot import Snapshot


def _require_archive_provenance(spec_id: str, path: Path) -> None:
    """Release only what an archive-pinned snapshot backs.

    A ``source_dataset`` snapshot is a drafting source: it is read from the
    nobodynamed connector, which serves no national rank, so it never passes the
    rank-level anchor comparison that docs/DATA_VERIFICATION.md requires. Scoring and
    approval accept one; publication does not. Regenerate through
    scripts/snapshot_from_d1.py with D1 credentials, re-pin, and re-approve.
    """
    if not Snapshot.model_validate_json(path.read_bytes()).from_ssa_archive:
        raise ValueError(
            f"{spec_id}: release requires an archive-pinned snapshot, "
            f"but {path.name} declares dataset provenance"
        )


def stage_release(summary_path: Path, destination: Path) -> list[str]:
    summary = json.loads(summary_path.read_text())
    ids = summary.get("release_ids", [])
    if (
        not ids
        or summary.get("failed") != 0
        or summary.get("errors")
        or summary.get("qc_failed")
        or summary.get("total") != len(ids)
        or summary.get("succeeded") != len(ids)
        or len(ids) != len(set(ids))
    ):
        raise ValueError("release requires a complete, QC-passed batch")
    results = summary.get("results", [])
    if (
        len(results) != len(ids)
        or {r["id"] for r in results} != set(ids)
        or not all(r.get("composed") and r.get("qc", {}).get("passed") is True for r in results)
    ):
        raise ValueError("release results disagree with successful IDs")
    source = summary_path.parent
    files: list[Path] = [summary_path]
    for spec_id in ids:
        if not isinstance(spec_id, str) or Path(spec_id).name != spec_id:
            raise ValueError("invalid release ID")
        for suffix in (".mp4", ".json", ".story.json", ".source.json"):
            path = source / f"{spec_id}{suffix}"
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"missing release file: {path.name}")
            if suffix == ".source.json":
                _require_archive_provenance(spec_id, path)
            files.append(path)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("release destination must be empty; stale files are not publishable")
    destination.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copy2(path, destination / path.name)
    return [p.name for p in files]


if __name__ == "__main__":
    stage_release(Path(sys.argv[1]), Path(sys.argv[2]))
