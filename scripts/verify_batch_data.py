"""Verify an approved batch against current D1 without changing its pinned sources."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from nobodynamed_video.data.snapshot import Snapshot, verified_snapshot
from nobodynamed_video.editorial.story import evaluate_story, load_story
from nobodynamed_video.publish_release import RELEASE_BATCHES
from ruamel.yaml import YAML

from scripts.snapshot_from_d1 import generate


def approved_snapshots(batch: Path) -> list[Snapshot]:
    entries = YAML(typ="safe").load(batch.read_text())["videos"]
    ids = [entry["id"] for entry in entries]
    if (
        batch.stem not in RELEASE_BATCHES
        or set(ids) != RELEASE_BATCHES[batch.stem]
        or len(ids) != len(set(ids))
    ):
        raise ValueError("batch must contain exactly its approved release IDs")
    snapshots = []
    for entry in entries:
        story = load_story(Path(entry["story"]))
        if (story.id, story.name, story.sex) != (entry["id"], entry["name"], entry["sex"]):
            raise ValueError(f"{entry['id']}: batch identity differs from approved story")
        evaluation = evaluate_story(story)
        if not evaluation.publishable:
            raise ValueError(f"{story.id}: {'; '.join(evaluation.blockers)}")
        snapshot = verified_snapshot(story)
        if not snapshot.from_ssa_archive:
            raise ValueError(f"{story.id}: release requires archive provenance")
        snapshots.append(snapshot)
    if len({(s.latest_year, s.archive_sha256) for s in snapshots}) != 1:
        raise ValueError("batch snapshots must use one reviewed SSA release")
    return snapshots


async def verify(batch: Path, out: Path) -> None:
    snapshots = approved_snapshots(batch)
    await generate(
        out=out,
        anchor_dir=Path("data/ssa-2025"),
        latest_year=snapshots[0].latest_year,
        archive_sha256=str(snapshots[0].archive_sha256),
        names=[f"{s.name}:{s.sex}" for s in snapshots],
    )
    for expected in snapshots:
        path = out / f"{expected.name.lower()}-{expected.sex.lower()}.json"
        current = Snapshot.model_validate_json(path.read_bytes())
        fields = {"name", "sex", "source_url", "archive_sha256", "latest_year", "observations"}
        if current.model_dump(include=fields) != expected.model_dump(include=fields):
            raise ValueError(f"{expected.name}: current D1 differs from approved snapshot")
        print(f"{expected.name}: approved content and all annual D1 observations verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--out", type=Path, default=Path("out/d1-preflight"))
    args = parser.parse_args()
    asyncio.run(verify(args.batch, args.out))
