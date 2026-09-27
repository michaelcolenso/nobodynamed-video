"""Long-form episodes: a gate over approved chapter stories plus reviewed bookends.

A long-form episode never introduces new SSA claims of its own. Every chapter is an
approved StorySpec pinned to an SSA snapshot, the roster figures on the title cards are
computed from those snapshots at render time, and any combined total the narration
states is declared in ``aggregate_claims`` and recomputed here before approval.
"""

from __future__ import annotations

import hashlib
import json
import re
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
# A figure stated in title-card copy must sit within this share of a declared,
# snapshot-verified total ("over 113,000" for 113,356 is 0.3%).
FIGURE_TOLERANCE = 0.01
_BOOKEND_FIELDS = ("kicker", "headline", "subhead", "script")
# A trailing comma is punctuation ("In 2000, ...") unless a digit follows it.
# Every numeral is a checked count unless it is a year, a "top-N" rank (verified
# separately) or a "#N" ordinal; copy spells out other small numbers ("five names").
_FIGURE = re.compile(r"(?<![\w,#])(\d{1,3}(?:,\d{3})+|\d+)(?!\w|,\d)")
_YEAR = re.compile(r"(?<![\w,])(18[89]\d|19\d\d|20\d\d|2100)(?!\w|,\d)")
_TOP = re.compile(r"\btop[\s-]+(\d+|[a-z]+(?:-[a-z]+)?)\b", re.IGNORECASE)
_UNITS = {
    word: value
    for value, word in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen".split()
    )
}
_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _small_number(token: str) -> int | None:
    """Parse '25', 'ten' or 'twenty-five'; None when the token is not a number."""
    if token.isdigit():
        return int(token)
    parts = token.lower().split("-")
    if len(parts) == 1:
        return _UNITS.get(parts[0], _TENS.get(parts[0]))
    if len(parts) == 2 and parts[0] in _TENS and parts[1] in _UNITS and _UNITS[parts[1]] < 10:
        return _TENS[parts[0]] + _UNITS[parts[1]]
    return None


def stated_rank_claims(text: str) -> list[tuple[int | None, int]]:
    """'top-25 ... in 2000' / 'top twenty-five in 2000' as (year, top) pairs.

    A rank claim binds to the single year stated in its sentence; with no year or
    several, it is unbound (``None``) and the gate rejects it.
    """
    claims: list[tuple[int | None, int]] = []
    for sentence in _SENTENCE_END.split(text):
        tops = [n for n in (_small_number(m) for m in _TOP.findall(sentence)) if n]
        if not tops:
            continue
        years = [int(y) for y in _YEAR.findall(sentence)]
        year = years[0] if len(years) == 1 else None
        claims.extend((year, top) for top in tops)
    return claims


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def stated_figures(text: str) -> list[int]:
    """Count numerals in copy, excluding bare four-digit years (1880-2100)."""
    return [figure for _, figure in stated_year_figures(text)]


def stated_year_figures(text: str) -> list[tuple[int | None, int]]:
    """Pair each stated figure with the year it is stated for.

    Within a sentence, figures and years pair in reading order when their counts
    match ("from 113,356 in 2000 to 20,979 in 2025"); otherwise the figure is
    unbound (``None``) and the gate rejects it rather than guess.
    """
    pairs: list[tuple[int | None, int]] = []
    for sentence in _SENTENCE_END.split(text):
        years: list[int] = []
        figures: list[int] = []
        for token in _FIGURE.findall(_TOP.sub(" ", sentence)):
            value = int(token.replace(",", ""))
            if "," not in token and 1880 <= value <= 2100:
                years.append(value)
            else:
                figures.append(value)
        if not figures:
            continue
        if len(years) == len(figures):
            pairs.extend(zip(years, figures, strict=True))
        else:
            pairs.extend((None, figure) for figure in figures)
    return pairs


@dataclass(frozen=True)
class RosterEntry:
    """Snapshot-derived facts for one chapter name, shown on the title cards."""

    name: str
    peak_year: int
    peak_count: int
    latest_year: int
    # None when SSA suppressed the latest year (<5 births); never a zero-fill.
    latest_count: int | None

    @property
    def decline_pct(self) -> int | None:
        if self.latest_count is None:
            return None
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
        latest_count=latest.count,
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
    series = [(story.name, story.sex) for story in chapters]
    if len(ids) != len(set(ids)) or len(series) != len(set(series)):
        # Two stories about one SSA series would double-count it in every total.
        blockers.append("chapters must be distinct names (one story per name and sex)")
    releases = {
        (s.latest_year, s.archive_sha256, s.source_url, s.source_dataset) for s in snapshots
    }
    if not all(s.from_ssa_archive for s in snapshots):
        # Only an archive-pinned snapshot names an immutable SSA release; a bare
        # dataset label cannot tell two D1 retrievals apart.
        blockers.append("every chapter snapshot must be pinned to the SSA archive")
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

    declared = {claim.year: claim.total for claim in spec.aggregate_claims}
    published = [
        ("title", spec.title),
        *((f"intro {field}", getattr(spec.intro, field)) for field in _BOOKEND_FIELDS),
        *((f"outro {field}", getattr(spec.outro, field)) for field in _BOOKEND_FIELDS),
        ("social caption", spec.social_caption),
        ("pinned comment", spec.share_prompt),
    ]
    for rank_claim in spec.rank_claims:
        for story, snapshot in zip(chapters, snapshots, strict=True):
            point = next((p for p in snapshot.observations if p.year == rank_claim.year), None)
            if point is None or point.rank is None or point.rank > rank_claim.top:
                rank = "unranked" if point is None or point.rank is None else f"#{point.rank}"
                blockers.append(
                    f"rank claim top-{rank_claim.top} in {rank_claim.year} fails: "
                    f"{story.name} was {rank}"
                )
    declared_ranks = {(rc.year, rc.top) for rc in spec.rank_claims}
    for label, copy in published:
        for year, top in stated_rank_claims(copy):
            if year is None:
                blockers.append(f"{label} states top-{top} without one year to bind it to")
            elif (year, top) not in declared_ranks:
                blockers.append(f"{label} states top-{top} in {year}, which has no rank claim")
        for year, figure in stated_year_figures(copy):
            if year is None:
                blockers.append(f"{label} states {figure:,} without one year to bind it to")
            elif year not in declared:
                blockers.append(f"{label} states {figure:,} for {year}, which has no claim")
            elif abs(figure - declared[year]) > FIGURE_TOLERANCE * declared[year]:
                blockers.append(
                    f"{label} states {figure:,} for {year}; "
                    f"the declared total is {declared[year]:,}"
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
