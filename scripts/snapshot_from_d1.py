"""Generate release snapshots from a D1 mirror verified against pinned SSA anchors.

GitHub-hosted runners are blocked by SSA's edge from downloading names.zip directly.
This script does not trust D1 by default: it first proves that D1 reproduces the
checked-in archive-derived launch snapshots, including annual counts, suppression
gaps, and ranks. Only then may it emit new snapshots carrying the same upstream
SSA release identity.

    uv run python scripts/snapshot_from_d1.py --out out/candidate-snapshots \
        --names Taylor:F Chad:M

``--from-connector`` is the weaker fallback for a workstation with no D1 credentials.
It replays captured nobodynamed connector responses, which serve annual counts but no
national rank, so it cannot run the rank-level anchor check and must not claim the SSA
archive identity. The snapshots it writes declare ``source_dataset`` instead, and the
Snapshot model refuses to let them carry an archive SHA256. Re-run the credentialed
path above before a release, then ``--repin-stories`` to re-pin the story hashes.

    uv run python scripts/snapshot_from_d1.py --out data/nobodynamed-2025 \
        --from-connector data/nobodynamed-2025/source --repin-stories stories/viral-2025
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.data.snapshot import Snapshot
from nobodynamed_video.editorial.story import load_story, write_story

SOURCE_URL = "https://www.ssa.gov/oact/babynames/names.zip"
DEFAULT_ARCHIVE_SHA256 = (
    "cd78e975ed7bb358e018dd62fbe14ced89295e9581c49172ca4eedcb011b3724"
)
CONNECTOR_DATASET = "nobodynamed-d1:name-vitals"
DEFAULT_ANCHORS = (
    "alexa-f.json",
    "hazel-f.json",
    "bertha-f.json",
    "kunta-m.json",
    "jennifer-f.json",
    "eleanor-f.json",
)


def _selected(items: list[str]) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    for item in items:
        name, separator, sex = item.partition(":")
        sex = sex.upper()
        if not separator or not name or sex not in {"M", "F"}:
            raise ValueError(f"invalid name/sex selector: {item!r}")
        selected.append((name, sex))
    return selected


async def _observations(
    source: D1Source,
    name: str,
    sex: str,
    latest_year: int,
) -> list[dict[str, int | None]]:
    rows = await source.query_rows(
        (
            "SELECT ny.year AS year, ny.count AS count, "
            "1 + ("
            "  SELECT COUNT(*) "
            "  FROM name_years AS ny2 "
            "  JOIN names AS n2 ON n2.id = ny2.name_id "
            "  WHERE n2.sex = ?2 "
            "    AND ny2.year = ny.year "
            "    AND ny2.count > ny.count"
            ") AS rank "
            "FROM names AS n "
            "JOIN name_years AS ny ON ny.name_id = n.id "
            "WHERE n.name_lower = lower(?1) "
            "  AND n.sex = ?2 "
            "  AND ny.year <= ?3 "
            "ORDER BY ny.year ASC"
        ),
        [name, sex, latest_year],
    )
    reported = {
        int(str(row["year"])): {
            "count": int(str(row["count"])),
            "rank": int(str(row["rank"])),
        }
        for row in rows
    }
    return [
        {
            "year": year,
            "count": reported.get(year, {}).get("count"),
            "rank": reported.get(year, {}).get("rank"),
        }
        for year in range(1880, latest_year + 1)
    ]


def _anchor_observations(snapshot: Snapshot) -> list[dict[str, int | None]]:
    return [
        {"year": point.year, "count": point.count, "rank": point.rank}
        for point in snapshot.observations
    ]


def _first_difference(
    expected: list[dict[str, int | None]],
    actual: list[dict[str, int | None]],
) -> tuple[dict[str, int | None], dict[str, int | None]] | None:
    return next(
        (
            (left, right)
            for left, right in zip(expected, actual, strict=True)
            if left != right
        ),
        None,
    )


async def _verify_anchors(
    source: D1Source,
    anchor_dir: Path,
    latest_year: int,
    archive_sha256: str,
) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for filename in DEFAULT_ANCHORS:
        path = anchor_dir / filename
        data = path.read_bytes()
        snapshot = Snapshot.model_validate_json(data)
        if snapshot.latest_year != latest_year:
            raise ValueError(f"{filename}: anchor year differs from requested year")
        if snapshot.archive_sha256 != archive_sha256:
            raise ValueError(f"{filename}: anchor archive SHA256 differs from pinned release")
        if snapshot.source_url != SOURCE_URL:
            raise ValueError(f"{filename}: anchor source URL is not official SSA archive")
        actual = await _observations(source, snapshot.name, snapshot.sex, latest_year)
        expected = _anchor_observations(snapshot)
        difference = _first_difference(expected, actual)
        if difference is not None:
            left, right = difference
            raise ValueError(
                f"{filename}: D1 differs from pinned SSA snapshot; "
                f"expected {left}, got {right}"
            )
        verified.append(
            {
                "file": filename,
                "sha256": hashlib.sha256(data).hexdigest(),
                "name": snapshot.name,
                "sex": snapshot.sex,
            }
        )
    return verified


def replay_connector(out: Path, source_dir: Path, latest_year: int) -> list[dict[str, Any]]:
    """Emit rank-free snapshots from captured connector responses.

    The connector serves counts only, so these snapshots carry ``source_dataset`` and
    are barred by the Snapshot model from claiming the SSA archive SHA256. Counts are
    still gated exactly as they are for an archive snapshot.
    """
    out.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()
    emitted: list[dict[str, Any]] = []
    for path in sorted(source_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        name, sex = str(payload["name"]), str(payload["sex"])
        series = {int(year): int(count) for year, count in payload["series"].items()}
        stray = sorted(year for year in series if year > latest_year)
        if stray:
            raise ValueError(f"{path}: observations after --year {latest_year}: {stray}")
        # rank is omitted, not null: the connector has no rank to report.
        payload = {
            "schema_version": 1,
            "source_dataset": CONNECTOR_DATASET,
            "retrieved_at": retrieved_at,
            "name": name,
            "sex": sex,
            "latest_year": latest_year,
            "observations": [
                {"year": year, "count": series.get(year)}
                for year in range(1880, latest_year + 1)
            ],
        }
        Snapshot.model_validate(payload)
        target = out / f"{name.lower()}-{sex.lower()}.json"
        data = json.dumps(payload, indent=2).encode() + b"\n"
        target.write_bytes(data)
        emitted.append(
            {
                "file": target.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "name": name,
                "sex": sex,
            }
        )
        print(target)
    if not emitted:
        raise ValueError(f"no captured connector responses in {source_dir}")
    return emitted


def repin_stories(story_dir: Path) -> None:
    """Re-pin each story to the current bytes of the snapshot it already names.

    A changed hash invalidates the story's approval digest by design, so the gate
    fails closed until a reviewer approves the re-pinned content.
    """
    for path in sorted(story_dir.glob("*.yaml")):
        story = load_story(path)
        if not story.data_snapshot:
            continue
        digest = hashlib.sha256(Path(story.data_snapshot).read_bytes()).hexdigest()
        if digest == story.data_sha256:
            continue
        write_story(story.model_copy(update={"data_sha256": digest}), path)
        print(f"re-pinned {path} -> {digest}")


async def generate(
    out: Path,
    anchor_dir: Path,
    latest_year: int,
    archive_sha256: str,
    names: list[str],
) -> None:
    d1_url = os.environ.get("D1_URL", "")
    d1_token = os.environ.get("D1_TOKEN", "")
    if not d1_url or not d1_token:
        raise ValueError("D1_URL and D1_TOKEN are required")

    source = D1Source(d1_url, d1_token, timeout=60.0)
    anchors = await _verify_anchors(
        source,
        anchor_dir,
        latest_year,
        archive_sha256,
    )
    out.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()
    emitted: list[dict[str, Any]] = []
    for name, sex in _selected(names):
        observations = await _observations(source, name, sex, latest_year)
        payload = {
            "schema_version": 1,
            "source_url": SOURCE_URL,
            "archive_sha256": archive_sha256,
            "retrieved_at": retrieved_at,
            "name": name,
            "sex": sex,
            "latest_year": latest_year,
            "observations": observations,
        }
        snapshot = Snapshot.model_validate(payload)
        target = out / f"{name.lower()}-{sex.lower()}.json"
        data = snapshot.model_dump_json(indent=2).encode() + b"\n"
        target.write_bytes(data)
        emitted.append(
            {
                "file": target.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "name": name,
                "sex": sex,
            }
        )
        print(target)

    manifest = {
        "schema_version": 1,
        "snapshot_origin": "verified_d1_mirror",
        "upstream_source_url": SOURCE_URL,
        "upstream_archive_sha256": archive_sha256,
        "latest_year": latest_year,
        "verified_at": retrieved_at,
        "anchor_snapshots": anchors,
        "emitted_snapshots": emitted,
    }
    (out / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified {len(anchors)} pinned SSA anchors before emitting {len(emitted)} snapshots")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--anchor-dir", type=Path, default=Path("data/ssa-2025"))
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--archive-sha256", default=DEFAULT_ARCHIVE_SHA256)
    parser.add_argument("--names", nargs="+", default=[])
    parser.add_argument(
        "--from-connector",
        type=Path,
        default=None,
        help="Replay captured connector responses instead of querying D1 (no ranks)",
    )
    parser.add_argument(
        "--repin-stories",
        type=Path,
        default=None,
        help="Re-pin data_sha256 for the stories in this directory after writing snapshots",
    )
    args = parser.parse_args()
    if args.from_connector is not None:
        replay_connector(args.out, args.from_connector, args.year)
    elif args.names:
        asyncio.run(
            generate(
                out=args.out,
                anchor_dir=args.anchor_dir,
                latest_year=args.year,
                archive_sha256=args.archive_sha256,
                names=args.names,
            )
        )
    else:
        parser.error("pass --names for a verified D1 extract, or --from-connector to replay")
    if args.repin_stories is not None:
        repin_stories(args.repin_stories)
