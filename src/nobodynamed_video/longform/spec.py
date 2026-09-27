"""Long-form episodes: a gate over approved chapter stories plus reviewed bookends.

A long-form episode never introduces new SSA claims of its own. Every chapter is an
approved StorySpec pinned to an SSA snapshot, the roster figures on the title cards are
computed from those snapshots at render time, and any combined total the narration
states is declared in ``aggregate_claims`` and recomputed here before approval.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from nobodynamed_video.data.snapshot import Snapshot, verified_snapshot
from nobodynamed_video.editorial.story import evaluate_story, load_story
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.models import LongFormSpec, StorySpec, StoryStatus

MIN_EPISODE_S = 60.0
MAX_EPISODE_S = 90.0
MIN_BOOKEND_WORDS = 8
# At a documentary read rate this keeps narration inside the 10s title-card cap.
MAX_BOOKEND_WORDS = 22
CORE_TAGS = {"#namedata", "#ssadata", "#namehistory"}


@dataclass(frozen=True)
class RosterEntry:
    """Snapshot-derived facts for one chapter name, shown on the title cards."""

    name: str
    peak_year: int
    peak_count: int
    latest_year: int
    latest_count: int

    @property
    def decline_pct(self) -> int:
        return round(100 * (1 - self.latest_count / self.peak_count))


@dataclass
class LongFormEvaluation:
    publishable: bool
    blockers: list[str] = field(default_factory=list)
    chapters: list[StorySpec] = field(default_factory=list)


def load_longform(path: Path) -> LongFormSpec:
    raw = YAML(typ="safe").load(path.read_text())
    if not isinstance(raw, dict):
        raise StoryQualityError(f"Invalid long-form file: {path}")
    return LongFormSpec.model_validate(raw)


def write_longform(spec: LongFormSpec, path: Path) -> Path:
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    data: dict[str, Any] = spec.model_dump(mode="json", exclude_none=True)
    with path.open("w") as fh:
        yaml.dump(data, fh)
    return path


def longform_digest(spec: LongFormSpec) -> str:
    """Approval covers the episode copy and the exact bytes of every chapter story."""
    payload = spec.model_dump(
        mode="json", exclude={"status", "approved_by", "approved_at", "approved_content_sha256"}
    )
    payload["chapter_sha256"] = [
        hashlib.sha256(Path(chapter).read_bytes()).hexdigest() for chapter in spec.chapters
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def roster_entry(story: StorySpec, snapshot: Snapshot) -> RosterEntry:
    reported = [p for p in snapshot.observations if p.count is not None]
    peak = max(reported, key=lambda p: p.count or 0)
    latest = next(p for p in snapshot.observations if p.year == snapshot.latest_year)
    return RosterEntry(
        name=story.name,
        peak_year=peak.year,
        peak_count=int(peak.count or 0),
        latest_year=snapshot.latest_year,
        latest_count=int(latest.count or 0),
    )


def aggregate_total(snapshots: list[Snapshot], year: int) -> int:
    """Sum one year across snapshots; a year a snapshot does not cover is an error.

    A covered year with no count is an SSA-suppressed gap (<5) and sums as zero.
    """
    total = 0
    for snapshot in snapshots:
        point = next((p for p in snapshot.observations if p.year == year), None)
        if point is None:
            raise ValueError(f"{snapshot.name} snapshot has no {year} observation")
        total += int(point.count or 0)
    return total


def evaluate_longform(spec: LongFormSpec, *, require_approval: bool = True) -> LongFormEvaluation:
    blockers: list[str] = []
    chapters: list[StorySpec] = []
    snapshots: list[Snapshot] = []
    for ref in spec.chapters:
        try:
            story = load_story(Path(ref))
        except (OSError, StoryQualityError, ValueError) as exc:
            blockers.append(f"{ref}: {exc}")
            continue
        evaluation = evaluate_story(story)
        if not evaluation.publishable:
            blockers.append(f"{story.id}: {'; '.join(evaluation.blockers)}")
            continue
        chapters.append(story)
        snapshots.append(verified_snapshot(story))

    ids = [story.id for story in chapters]
    if len(ids) != len(set(ids)):
        blockers.append("chapters must be distinct stories")
    releases = {
        (s.latest_year, s.archive_sha256, s.source_url, s.source_dataset) for s in snapshots
    }
    if len(releases) > 1:
        blockers.append("chapter snapshots must share one SSA release")

    for label, bookend in (("intro", spec.intro), ("outro", spec.outro)):
        if not MIN_BOOKEND_WORDS <= bookend.word_count <= MAX_BOOKEND_WORDS:
            blockers.append(
                f"{label} narration is {bookend.word_count} words; "
                f"expected {MIN_BOOKEND_WORDS}-{MAX_BOOKEND_WORDS}"
            )

    if snapshots and len(snapshots) == len(spec.chapters):
        for claim in spec.aggregate_claims:
            try:
                actual = aggregate_total(snapshots, claim.year)
            except ValueError as exc:
                blockers.append(f"aggregate claim for {claim.year}: {exc}")
                continue
            if actual != claim.total:
                blockers.append(
                    f"aggregate claim for {claim.year} is {claim.total:,}; "
                    f"snapshots total {actual:,}"
                )

    tags = {tag.lower() for tag in spec.hashtags}
    if "#aivoice" not in tags:
        blockers.append("hashtags must include #AIVoice — every episode is narrated")
    if not tags & CORE_TAGS:
        blockers.append("caption requires a relevant core name-data/history tag")
    caption = spec.social_caption.rstrip()
    if caption[-1:] not in ".!?":
        caption += "."
    if len(caption + " " + " ".join(spec.hashtags)) > 150:
        blockers.append("caption including hashtags exceeds 150 characters")

    if require_approval:
        if spec.status != StoryStatus.APPROVED:
            blockers.append("episode has not been approved")
        if not spec.approved_by or spec.approved_at is None:
            blockers.append("approval metadata is incomplete")
        if not blockers and spec.approved_content_sha256 != longform_digest(spec):
            blockers.append("approval does not cover the current episode or chapter content")

    return LongFormEvaluation(publishable=not blockers, blockers=blockers, chapters=chapters)


def approve_longform(spec: LongFormSpec, reviewer: str) -> LongFormSpec:
    if not reviewer.strip():
        raise StoryQualityError("reviewer must not be blank")
    evaluation = evaluate_longform(spec, require_approval=False)
    if not evaluation.publishable:
        raise StoryQualityError("; ".join(evaluation.blockers))
    return spec.model_copy(
        update={
            "status": StoryStatus.APPROVED,
            "approved_by": reviewer.strip(),
            "approved_at": datetime.now(tz=UTC),
            "approved_content_sha256": longform_digest(spec),
        }
    )
