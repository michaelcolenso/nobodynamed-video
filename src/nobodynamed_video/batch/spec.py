"""YAML batch spec loader → list[VideoSpec]."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from nobodynamed_video.config import get_settings
from nobodynamed_video.data.classifier import classify
from nobodynamed_video.data.ctx import (
    build_base_context,
    finalize_video_context,
    load_cultural_events,
)
from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.data.doctor import require_publishable
from nobodynamed_video.data.hooks import load_hook_library, resolve_hook
from nobodynamed_video.data.sqlite_source import SqliteSource
from nobodynamed_video.exceptions import BlocklistedName
from nobodynamed_video.models import DataMode, Scene, VideoFormat, VideoSpec
from nobodynamed_video.render.frame_planner import SCENE_ORDER
from nobodynamed_video.seed import spec_seed

_BLOCKLIST_PATH = Path("fixtures/blocklist.txt")


def _load_blocklist() -> set[str]:
    if not _BLOCKLIST_PATH.exists():
        return set()
    return {line.strip() for line in _BLOCKLIST_PATH.read_text().splitlines() if line.strip()}


_FORMAT_DURATIONS: dict[VideoFormat, dict[str, float]] = {
    VideoFormat.FAST: {"hook": 3.0, "reveal": 6.0, "narrative": 6.0, "cta": 3.0},
    VideoFormat.EXPLAINER: {"hook": 5.0, "reveal": 12.0, "narrative": 18.0, "cta": 5.0},
    VideoFormat.DEEP_STORY: {"hook": 8.0, "reveal": 20.0, "narrative": 50.0, "cta": 10.0},
}


def _make_scenes(video_format: VideoFormat = VideoFormat.FAST) -> list[Scene]:
    durations = _FORMAT_DURATIONS[video_format]
    return [
        Scene(
            kind=k,
            duration_s=durations[k],
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
        source = D1Source(settings.d1_url, settings.get_d1_token())

    specs: list[VideoSpec] = []
    source_year, _provenance = await require_publishable(source, settings.data_mode)
    latest_year = settings.latest_year or source_year
    if settings.data_mode == DataMode.PUBLISH and latest_year != source_year:
        raise RuntimeError(
            f"Publish mode requires newest dataset year {source_year}; requested {latest_year}"
        )
    hooks_library = load_hook_library()
    cultural_events = load_cultural_events()

    for entry in videos:
        name: str = entry["name"]
        sex: str = entry["sex"]
        vid_id: str = entry.get("id", f"{name.lower()}-{latest_year}")
        style: str | None = entry.get("style")
        explicit_hook_id: str | None = entry.get("hook_id")
        video_format = VideoFormat(entry.get("format", defaults.get("format", "fast")))

        if name in blocklist and not force:
            raise BlocklistedName(
                f"'{name}' is on the editorial blocklist (fixtures/blocklist.txt). "
                "Use --force to override."
            )

        record = await source.get_record(name, sex, latest_year)
        tier = classify(record)
        seed = spec_seed(vid_id)
        base_context = await build_base_context(
            source,
            record,
            tier,
            latest_year,
            cultural_events,
            data_mode=settings.data_mode,
        )
        hook = resolve_hook(
            base_context,
            style=style,
            spec_seed=seed,
            hook_id=explicit_hook_id,
            library=hooks_library,
        )
        context = finalize_video_context(base_context, hook, seed)
        assert context.program is not None

        specs.append(
            VideoSpec(
                id=vid_id,
                record=record,
                tier=tier,
                scenes=_make_scenes(video_format),
                fps=fps,
                seed=seed,
                program=context.program,
                hook=hook,
                context=context,
                format=video_format,
            )
        )

    return specs
