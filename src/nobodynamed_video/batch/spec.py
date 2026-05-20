"""YAML batch spec loader → list[VideoSpec]."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from nobodynamed_video.config import get_settings
from nobodynamed_video.data.classifier import classify
from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.data.sqlite_source import SqliteSource
from nobodynamed_video.exceptions import BlocklistedName
from nobodynamed_video.models import Scene, VideoSpec
from nobodynamed_video.render.frame_planner import SCENE_DURATIONS, SCENE_ORDER
from nobodynamed_video.seed import spec_seed

_BLOCKLIST_PATH = Path("fixtures/blocklist.txt")


def _load_blocklist() -> set[str]:
    if not _BLOCKLIST_PATH.exists():
        return set()
    return {line.strip() for line in _BLOCKLIST_PATH.read_text().splitlines() if line.strip()}


def _make_scenes() -> list[Scene]:
    return [
        Scene(
            kind=k,
            duration_s=SCENE_DURATIONS[k],
            template=k,
            static_props={},
        )
        for k in SCENE_ORDER
    ]


async def load_specs(yaml_path: Path, force: bool = False) -> list[VideoSpec]:
    """Parse a batch YAML file and resolve each entry to a VideoSpec."""
    settings = get_settings()
    blocklist = _load_blocklist()

    yaml = YAML()
    raw: dict[str, Any] = yaml.load(yaml_path.read_text())

    defaults: dict[str, Any] = raw.get("defaults", {})
    fps: int = int(defaults.get("fps", 30))
    videos: list[dict[str, Any]] = raw.get("videos", [])

    if settings.use_sqlite:
        source: SqliteSource | D1Source = SqliteSource(settings.sqlite_fixture)
    else:
        source = D1Source(settings.d1_url, settings.d1_token)

    specs: list[VideoSpec] = []
    latest_year = settings.latest_year

    for entry in videos:
        name: str = entry["name"]
        sex: str = entry["sex"]
        vid_id: str = entry.get("id", f"{name.lower()}-{latest_year}")

        if name in blocklist and not force:
            raise BlocklistedName(
                f"'{name}' is on the editorial blocklist (fixtures/blocklist.txt). "
                "Use --force to override."
            )

        record = await source.get_record(name, sex, latest_year)
        tier = classify(record)
        seed = spec_seed(vid_id)

        specs.append(
            VideoSpec(
                id=vid_id,
                record=record,
                tier=tier,
                scenes=_make_scenes(),
                fps=fps,
                seed=seed,
            )
        )

    return specs
