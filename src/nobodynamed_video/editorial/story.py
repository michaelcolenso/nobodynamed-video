"""Evidence-backed StorySpec scoring and one-time human approval."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from ruamel.yaml import YAML

from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.models import (
    EvidenceKind,
    EvidenceSource,
    NameRecord,
    ScriptBeat,
    ScriptBeatKind,
    StoryKind,
    StorySpec,
    StoryStatus,
)

MIN_STORY_SCORE = 75
MIN_SCRIPT_WORDS = 24
MAX_SCRIPT_WORDS = 36
MAX_HOOK_WORDS = 10


class StoryEvaluation(BaseModel):
    story_id: str
    score: int = Field(ge=0, le=100)
    components: dict[str, int]
    blockers: list[str]
    warnings: list[str]
    publishable: bool


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?:\s|$)", text.strip()))


def score_story(story: StorySpec) -> tuple[int, dict[str, int]]:
    """Score the editorial strength from inspectable, deterministic signals."""
    ssa_count = sum(source.kind == EvidenceKind.SSA for source in story.evidence)
    external_count = sum(source.kind != EvidenceKind.SSA for source in story.evidence)
    evidence = min(10, ssa_count * 10) + min(15, external_count * 8)

    thesis_lower = story.thesis.lower()
    premise = 5 if story.name.lower() in thesis_lower else 0
    premise += 5 if 30 <= len(story.thesis) <= 150 else 0
    trajectory_terms = ("rose", "fell", "decline", "return", "comeback", "created", "peak")
    premise += 5 if any(term in thesis_lower for term in trajectory_terms) else 0

    first = story.script_beats[0]
    first_words = len(first.text.split())
    hook = 10 if first.kind == ScriptBeatKind.HOOK and first_words <= MAX_HOOK_WORDS else 0
    hook += 5 if len(story.headline) <= 45 else 0
    hook += 5 if re.search(r"\d|\bone\b|\bthis\b|\bwhat\b|\bhow\b", story.headline.lower()) else 0

    script = 10 if MIN_SCRIPT_WORDS <= story.narration_word_count <= MAX_SCRIPT_WORDS else 0
    script += 5 if any(beat.kind == ScriptBeatKind.PROOF for beat in story.script_beats) else 0
    script += 5 if story.script_beats[-1].kind == ScriptBeatKind.LOOP else 0

    visual = 7 if len(story.visual_anchors) >= 3 else 3
    visual += 3 if len(set(story.visual_anchors)) == len(story.visual_anchors) else 0

    sharing = 4 if story.share_prompt.rstrip().endswith("?") else 0
    sharing += 3 if _sentence_count(story.social_caption) <= 1 else 0
    sharing += 3 if 2 <= len(story.hashtags) <= 4 else 0

    components = {
        "evidence": evidence,
        "premise": premise,
        "hook": hook,
        "script": script,
        "visual": visual,
        "sharing": sharing,
    }
    return sum(components.values()), components


def evaluate_story(story: StorySpec, *, require_approval: bool = True) -> StoryEvaluation:
    score, components = score_story(story)
    blockers: list[str] = []
    warnings: list[str] = []

    if score < MIN_STORY_SCORE:
        blockers.append(f"quality score {score} is below {MIN_STORY_SCORE}")
    if not MIN_SCRIPT_WORDS <= story.narration_word_count <= MAX_SCRIPT_WORDS:
        blockers.append(
            f"narration is {story.narration_word_count} words; "
            f"expected {MIN_SCRIPT_WORDS}-{MAX_SCRIPT_WORDS}"
        )
    first = story.script_beats[0]
    if first.kind != ScriptBeatKind.HOOK:
        blockers.append("first script beat must be hook")
    elif len(first.text.split()) > MAX_HOOK_WORDS:
        blockers.append(f"hook exceeds {MAX_HOOK_WORDS} words")
    if story.script_beats[-1].kind != ScriptBeatKind.LOOP:
        blockers.append("final script beat must be loop")
    if not story.share_prompt.rstrip().endswith("?"):
        blockers.append("share prompt must be a question")
    if _sentence_count(story.social_caption) > 1:
        blockers.append("social caption must be one sentence")
    if not all(tag.startswith("#") and " " not in tag for tag in story.hashtags):
        blockers.append("hashtags must start with # and contain no spaces")
    if not any(source.kind == EvidenceKind.SSA for source in story.evidence):
        blockers.append("story must cite SSA data")

    if story.story_kind == StoryKind.CULTURAL_RUPTURE:
        external = [source for source in story.evidence if source.kind != EvidenceKind.SSA]
        if len(external) < 2:
            blockers.append("cultural rupture requires at least two non-SSA sources")

    insecure_sources = [
        source.label for source in story.evidence if not source.url.startswith("https://")
    ]
    if insecure_sources:
        blockers.append(f"sources must use https: {', '.join(insecure_sources)}")

    if story.quality_score not in (0, score):
        blockers.append(
            f"stored quality score {story.quality_score} does not match computed {score}"
        )
    if require_approval:
        if story.status != StoryStatus.APPROVED:
            blockers.append("story has not been approved")
        if not story.approved_by or story.approved_at is None:
            blockers.append("approval metadata is incomplete")

    if len(story.headline) > 45:
        warnings.append("headline is valid but loses the short-hook score")

    return StoryEvaluation(
        story_id=story.id,
        score=score,
        components=components,
        blockers=blockers,
        warnings=warnings,
        publishable=not blockers,
    )


def load_story(path: Path) -> StorySpec:
    yaml = YAML(typ="safe")
    raw = yaml.load(path.read_text())
    if not isinstance(raw, dict):
        raise StoryQualityError(f"Invalid story file: {path}")
    return StorySpec.model_validate(raw)


def write_story(story: StorySpec, path: Path) -> Path:
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = story.model_dump(mode="json", exclude_none=True)
    with path.open("w") as fh:
        yaml.dump(data, fh)
    return path


def approve_story(story: StorySpec, reviewer: str) -> StorySpec:
    """Approve only after every non-approval publish gate clears."""
    score, _ = score_story(story)
    candidate = story.model_copy(update={"quality_score": score})
    evaluation = evaluate_story(candidate, require_approval=False)
    if not evaluation.publishable:
        raise StoryQualityError("; ".join(evaluation.blockers))
    return candidate.model_copy(
        update={
            "status": StoryStatus.APPROVED,
            "approved_by": reviewer.strip(),
            "approved_at": datetime.now(tz=UTC),
        }
    )


def draft_story(record: NameRecord, story_kind: StoryKind, story_id: str) -> StorySpec:
    """Create an evidence-first draft that still requires human copy review."""
    return StorySpec(
        id=story_id,
        name=record.name,
        sex=record.sex,
        story_kind=story_kind,
        thesis=(
            f"{record.name} peaked at {record.peak_count:,} births in {record.peak_year} "
            f"and reached {record.current_count:,} in {record.current_year}."
        ),
        headline=f"Watch {record.name}'s curve break.",
        subhead=f"{record.peak_count:,} births then. {record.current_count:,} now.",
        takeaway="The shape is the story; the data supplies the proof.",
        support=f"Peak {record.peak_year}. Current {record.current_year}.",
        script_beats=[
            ScriptBeat(kind=ScriptBeatKind.HOOK, text="This curve should not look like this."),
            ScriptBeat(
                kind=ScriptBeatKind.REVEAL,
                text=(
                    f"{record.name} peaked at {record.peak_count:,} births in "
                    f"{record.peak_year}, then reached {record.current_count:,} in "
                    f"{record.current_year}."
                ),
            ),
            ScriptBeat(
                kind=ScriptBeatKind.PROOF,
                text=(
                    "The complete Social Security series shows exactly where the "
                    "direction changed."
                ),
            ),
            ScriptBeat(kind=ScriptBeatKind.LOOP, text="Watch the curve again."),
        ],
        evidence=[
            EvidenceSource(
                label="Social Security baby-name data",
                url="https://www.ssa.gov/oact/babynames/",
                kind=EvidenceKind.SSA,
                supports="Annual United States birth counts and rankings from 1880 onward.",
            )
        ],
        visual_anchors=["first appearance", "peak year", "current count"],
        social_caption=f"The complete rise and fall of {record.name}, in one curve.",
        hashtags=["#NameData", "#SSAData", "#AIVoice"],
        share_prompt=f"Who knows a {record.name}?",
        voice_instructions=(
            "Read like a precise culture-documentary narrator: immediate, restrained, "
            "and curious, with a short pause before the final line."
        ),
    )
