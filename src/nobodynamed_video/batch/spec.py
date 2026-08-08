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
from nobodynamed_video.data.hooks import load_hook_library, resolve_hook
from nobodynamed_video.data.sqlite_source import SqliteSource
from nobodynamed_video.editorial.story import evaluate_story, load_story
from nobodynamed_video.exceptions import BlocklistedName, StoryQualityError
from nobodynamed_video.models import ProgramType, Scene, StoryKind, StorySpec, VideoSpec
from nobodynamed_video.render.frame_planner import SCENE_DURATIONS, SCENE_ORDER
from nobodynamed_video.seed import spec_seed

_BLOCKLIST_PATH = Path("fixtures/blocklist.txt")

# Hard character caps, enforced at load: every copy field sits in a fixed
# layout band; overflow wraps into the chart or the TikTok caption zone.
# Caps are ~2 lines at the field's font size inside the 920px safe width.
COPY_CAPS = {"headline": 60, "subhead": 70, "narrative": 80, "support": 70}

_STORY_PROGRAMS = {
    StoryKind.ONE_HIT: ProgramType.CASE_FILE,
    StoryKind.CULTURAL_RUPTURE: ProgramType.CULTURAL_EVENT,
    StoryKind.LONG_DECLINE: ProgramType.CASE_FILE,
    StoryKind.COMEBACK: ProgramType.RETURN_NOTICE,
}


def _story_path(batch_path: Path, value: str) -> Path:
    direct = Path(value)
    if direct.exists():
        return direct
    relative = batch_path.parent / value
    if relative.exists():
        return relative
    raise StoryQualityError(f"Story file not found: {value}")


def _load_approved_story(batch_path: Path, entry: dict[str, Any]) -> StorySpec | None:
    story_ref = entry.get("story")
    if not story_ref:
        return None
    story = load_story(_story_path(batch_path, str(story_ref)))
    evaluation = evaluate_story(story)
    if not evaluation.publishable:
        reasons = "; ".join(evaluation.blockers)
        raise StoryQualityError(f"{story.id}: rejected by story gate — {reasons}")
    return story


def _validate_copy(
    spec_id: str,
    fields: dict[str, str],
    event: dict[str, Any] | None,
) -> None:
    """Enforce copy caps and the withholding rule on final (post-override) text."""
    for field, text in fields.items():
        cap = COPY_CAPS[field]
        if len(text) > cap:
            raise ValueError(f"{spec_id}: {field} exceeds {cap} chars ({len(text)}): {text!r}")
    # Cause-leak lint: the hook teases the year, never the cause — the chart's
    # event marker is the payoff. Applies to headline/subhead only; the
    # narrative may assert a cause precisely because one was passed in here.
    if event:
        tokens = {
            w.strip(".,'\"()").lower()
            for w in str(event.get("killing_event", "")).split()
            if len(w) >= 4
        }
        tokens.add(str(event.get("event_year", "")))
        for field in ("headline", "subhead"):
            lowered = fields[field].lower()
            leaked = sorted(t for t in tokens if t and t in lowered)
            if leaked:
                raise ValueError(f"{spec_id}: {field} leaks the cause {leaked}: {fields[field]!r}")


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
        source = D1Source(settings.d1_url, settings.get_d1_token())

    specs: list[VideoSpec] = []
    latest_year = settings.latest_year
    hooks_library = load_hook_library()
    cultural_events = load_cultural_events()

    for entry in videos:
        name: str = entry["name"]
        sex: str = entry["sex"]
        vid_id: str = entry.get("id", f"{name.lower()}-{latest_year}")
        story = _load_approved_story(yaml_path, entry)
        if story and (story.id != vid_id or story.name != name or story.sex != sex):
            raise StoryQualityError(
                f"{vid_id}: story identity does not match batch entry "
                f"({story.id}, {story.name}, {story.sex})"
            )
        style: str | None = entry.get("style")
        explicit_hook_id: str | None = entry.get("hook_id")

        if name in blocklist and not force:
            raise BlocklistedName(
                f"'{name}' is on the editorial blocklist (fixtures/blocklist.txt). "
                "Use --force to override."
            )

        record = await source.get_record(name, sex, latest_year)
        tier = classify(record)
        seed = spec_seed(vid_id)
        base_context = await build_base_context(source, record, tier, latest_year, cultural_events)
        hook = resolve_hook(
            base_context,
            style=style,
            spec_seed=seed,
            hook_id=explicit_hook_id,
            library=hooks_library,
        )
        context = finalize_video_context(base_context, hook, seed)

        # Editorial copy overrides — hand-written per name in the batch YAML.
        # Tier-templated copy can misfire on a name's actual story (an
        # invented-from-zero name getting "Vintage names are back"), so any
        # entry may pin reviewed text: headline, subhead, narrative, support.
        if headline := entry.get("headline"):
            hook = hook.model_copy(update={"headline": headline})
        if subhead := entry.get("subhead"):
            hook = hook.model_copy(update={"subhead": subhead})
        if narrative := entry.get("narrative"):
            context = context.model_copy(update={"narrative_text": narrative})
        if support := entry.get("support"):
            context = context.model_copy(update={"supporting_text": support})

        if story:
            program = _STORY_PROGRAMS[story.story_kind]
            hook = hook.model_copy(
                update={
                    "headline": story.headline,
                    "subhead": story.subhead,
                    "caption": story.social_caption,
                    "pinned_comment": story.share_prompt,
                    "voice_register": "documentary",
                }
            )
            context = context.model_copy(
                update={
                    "program": program,
                    "narrative_text": story.takeaway,
                    "supporting_text": story.support,
                }
            )

        _validate_copy(
            vid_id,
            {
                "headline": hook.headline,
                "subhead": hook.subhead,
                "narrative": context.narrative_text or "",
                "support": context.supporting_text or "",
            },
            cultural_events.get((record.name.lower(), record.sex)),
        )

        # Re-narrow after model_copy: program is always set by
        # finalize_video_context and preserved by the copies above.
        assert context.program is not None

        specs.append(
            VideoSpec(
                id=vid_id,
                record=record,
                tier=tier,
                scenes=_make_scenes(),
                fps=fps,
                seed=seed,
                program=context.program,
                hook=hook,
                context=context,
                story=story,
                duration_s=story.target_duration_s if story else 11.0,
            )
        )

    return specs
