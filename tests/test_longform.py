"""Long-form episodes: gate, snapshot-backed facts, title-card motion, chapters, assembly."""

from __future__ import annotations

from pathlib import Path

import pytest
from nobodynamed_video.compose.caption import combo_hash
from nobodynamed_video.compose.ffmpeg import build_concat_cmd
from nobodynamed_video.compose.narration import CHAPTER_HOLD_S, NarrationArtifact, adaptive_duration
from nobodynamed_video.compose.state import CombinationState
from nobodynamed_video.data.snapshot import Snapshot, verified_snapshot
from nobodynamed_video.editorial.story import StoryEvaluation, chapter_narration_text, load_story
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.longform.bookends import (
    MAX_BOOKEND_NARRATION_S,
    MAX_BOOKEND_S,
    MIN_BOOKEND_S,
    bookend_duration,
    sample_bookend_frame,
)
from nobodynamed_video.longform.render import ChapterNarrator
from nobodynamed_video.longform.spec import (
    RosterEntry,
    aggregate_total,
    approve_longform,
    evaluate_longform,
    load_longform,
    longform_digest,
    roster_entry,
    stated_figures,
    write_longform,
)
from nobodynamed_video.models import AggregateClaim, LongFormSpec, StorySpec
from nobodynamed_video.render.frame_planner import plan_frames
from pydantic import ValidationError

from tests.test_frame_planner import make_bertha_spec

EPISODE = Path("longform/gen-z-five-2025.yaml")
FPS = 30


def _episode() -> LongFormSpec:
    return load_longform(EPISODE)


def _roster_and_totals(spec: LongFormSpec) -> tuple[list[RosterEntry], list[tuple[int, int]]]:
    chapters = evaluate_longform(spec, require_approval=False).chapters
    snapshots = [verified_snapshot(story) for story in chapters]
    roster = [roster_entry(s, n) for s, n in zip(chapters, snapshots, strict=True)]
    totals = [(c.year, aggregate_total(snapshots, c.year)) for c in spec.aggregate_claims]
    return roster, totals


def test_checked_in_episode_passes_every_gate_but_approval() -> None:
    evaluation = evaluate_longform(_episode(), require_approval=False)
    assert evaluation.publishable, evaluation.blockers
    assert [story.name for story in evaluation.chapters] == [
        "Jacob",
        "Emily",
        "Hannah",
        "Madison",
        "Destiny",
    ]


def test_aggregate_claims_are_recomputed_from_pinned_snapshots() -> None:
    spec = _episode()
    wrong = spec.model_copy(update={"aggregate_claims": [AggregateClaim(year=2000, total=113000)]})
    blockers = evaluate_longform(wrong, require_approval=False).blockers
    assert any("aggregate claim for 2000" in b and "113,356" in b for b in blockers)


def test_bookend_word_budget_and_ai_voice_tag_are_enforced() -> None:
    spec = _episode()
    long_intro = spec.intro.model_copy(update={"script": "word " * 31})
    no_tag = spec.model_copy(update={"intro": long_intro, "hashtags": ["#GenZ", "#NameData"]})
    blockers = evaluate_longform(no_tag, require_approval=False).blockers
    assert any(b.startswith("intro narration is 31 words") for b in blockers)
    assert any("#AIVoice" in b for b in blockers)


def test_approval_covers_episode_copy_and_chapter_order() -> None:
    approved = approve_longform(_episode(), "reviewer")
    assert evaluate_longform(approved).publishable
    reordered = approved.model_copy(update={"chapters": list(reversed(approved.chapters))})
    assert longform_digest(reordered) != approved.approved_content_sha256
    assert "approval does not cover the current episode or chapter content" in (
        evaluate_longform(reordered).blockers
    )
    with pytest.raises(StoryQualityError):
        approve_longform(_episode(), "  ")


def test_roster_matches_snapshot_peaks_and_latest_counts() -> None:
    roster, totals = _roster_and_totals(_episode())
    by_name = {entry.name: entry for entry in roster}
    assert (by_name["Jacob"].peak_year, by_name["Jacob"].peak_count) == (1998, 36031)
    assert (by_name["Destiny"].latest_count, by_name["Destiny"].decline_pct) == (458, 95)
    assert totals == [(2000, 113356), (2025, 20979)]


def test_opening_card_is_a_complete_cover_on_frame_zero() -> None:
    spec = _episode()
    roster, totals = _roster_and_totals(spec)
    first = sample_bookend_frame(spec.intro, 0.0, opening=True, roster=roster, totals=totals)
    second = sample_bookend_frame(spec.intro, 1 / FPS, opening=True, roster=roster, totals=totals)
    assert first["headline_alpha"] == 1.0 and first["subhead_alpha"] == 1.0
    assert len(first["roster"]) == 5
    assert all(row["alpha"] == 1.0 for row in first["roster"])
    assert first["headline_offset_y"] != second["headline_offset_y"]


def test_closing_card_reveals_totals_without_jumps() -> None:
    spec = _episode()
    roster, totals = _roster_and_totals(spec)
    frames = [
        sample_bookend_frame(spec.outro, i / FPS, opening=False, roster=roster, totals=totals)
        for i in range(int(4 * FPS))
    ]
    assert frames[0]["headline_alpha"] == 0.0
    assert frames[0]["roster"] == []
    widths = [[bar["fraction"] for bar in f["totals"]] for f in frames]
    for bar in range(2):
        series = [w[bar] for w in widths]
        assert all(b >= a for a, b in zip(series, series[1:], strict=False))
        assert max(abs(b - a) for a, b in zip(series, series[1:], strict=False)) < 0.08
    assert widths[-1] == [1.0, round(20979 / 113356, 6)]


def test_bookend_duration_is_bounded_and_frame_quantized() -> None:
    spec = _episode()
    assert bookend_duration(spec.intro, 0.5, FPS) == MIN_BOOKEND_S
    assert bookend_duration(spec.intro, MAX_BOOKEND_NARRATION_S, FPS) == MAX_BOOKEND_S
    duration = bookend_duration(spec.intro, 6.37, FPS)
    assert duration * FPS == round(duration * FPS)


def test_overlong_bookend_narration_is_rejected_not_truncated() -> None:
    with pytest.raises(StoryQualityError, match="title card narration needs"):
        bookend_duration(_episode().intro, MAX_BOOKEND_NARRATION_S + 0.5, FPS)


def test_aggregate_claim_outside_snapshot_coverage_is_rejected() -> None:
    spec = _episode()
    future = spec.model_copy(update={"aggregate_claims": [AggregateClaim(year=2026, total=0)]})
    blockers = evaluate_longform(future, require_approval=False).blockers
    assert any(b.startswith("aggregate claim for 2026:") for b in blockers)


def test_social_copy_follows_caption_rules() -> None:
    raw = _episode().model_dump()
    with pytest.raises(ValidationError):
        LongFormSpec.model_validate({**raw, "hashtags": ["#GenZ", "#AIVoice"]})
    with pytest.raises(ValidationError):
        LongFormSpec.model_validate({**raw, "share_prompt": "Tell us your class name."})
    five = ["#GenZ", "#NameData", "#AIVoice", "#Names", "#History"]
    assert LongFormSpec.model_validate({**raw, "hashtags": five}).hashtags == five


def test_chapters_from_different_archive_revisions_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nobodynamed_video.longform.spec as spec_module

    real = spec_module.verified_snapshot

    def mixed(story: StorySpec) -> Snapshot:
        snapshot = real(story)
        if story.name == "Destiny":
            return snapshot.model_copy(update={"archive_sha256": "0" * 64})
        return snapshot

    monkeypatch.setattr(spec_module, "verified_snapshot", mixed)
    blockers = evaluate_longform(_episode(), require_approval=False).blockers
    assert "chapter snapshots must share one SSA release" in blockers


def test_chapter_mode_labels_the_header_and_drops_the_loop_bridge() -> None:
    story = load_story(Path("stories/bertha-2024.yaml"))
    base = make_bertha_spec().model_copy(
        update={"story": story, "duration_s": story.target_duration_s}
    )
    chapter = base.model_copy(update={"chapter_label": "PART 2 OF 5"})
    frames = [props for _s, _i, _t, props in plan_frames(chapter, fps=FPS)]
    assert all(frame["loop_progress"] == 0.0 for frame in frames)
    assert frames[0]["header"]["label"].startswith("PART 2 OF 5 · ")
    looped = [props for _s, _i, _t, props in plan_frames(base, fps=FPS)]
    assert looped[-1]["loop_progress"] > 0.99


def test_chapter_hold_is_shorter_than_the_loop_beat() -> None:
    story = load_story(Path("stories/bertha-2024.yaml"))
    assert adaptive_duration(story, 12.5, CHAPTER_HOLD_S) == 12.9
    assert adaptive_duration(story, 12.5) == 13.35


def test_concat_trims_each_segment_and_normalizes_once(tmp_path: Path) -> None:
    segments = [tmp_path / "intro.mp4", tmp_path / "part1.mp4", tmp_path / "outro.mp4"]
    cmd = build_concat_cmd(segments, [7.5, 13.2, 8.0], tmp_path / "episode.mp4")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "[1:a]atrim=0:13.2,asetpts=PTS-STARTPTS[a1]" in graph
    assert "concat=n=3:v=1:a=1" in graph
    assert graph.count("loudnorm") == 1
    assert cmd[cmd.index("-color_range") + 1] == "tv"
    silent = build_concat_cmd(segments, [7.5, 13.2, 8.0], tmp_path / "e.mp4", narrated=False)
    assert "loudnorm" not in silent[silent.index("-filter_complex") + 1]
    with pytest.raises(ValueError):
        build_concat_cmd(segments, [7.5], tmp_path / "e.mp4")


def test_chapter_narration_drops_the_short_form_loop_beat() -> None:
    story = load_story(Path("stories/jacob-2024.yaml"))
    loop = story.script_beats[-1].text
    text = chapter_narration_text(story)
    assert loop not in text
    assert text == " ".join(beat.text.strip() for beat in story.script_beats[:-1])


@pytest.mark.asyncio
async def test_chapter_narrator_speaks_only_the_chapter_script(tmp_path: Path) -> None:
    spoken: list[str] = []

    class Inner:
        async def generate(self, story: StorySpec) -> NarrationArtifact:
            raise AssertionError("chapters must not narrate the full short-form script")

        async def generate_text(self, text: str, voice: str | None = None) -> NarrationArtifact:
            spoken.append(text)
            return NarrationArtifact(
                audio_path=tmp_path / "a.wav",
                word_timings=[],
                duration_s=5.0,
                provider="fake",
                model="fake",
                voice=voice or "luna",
            )

    story = load_story(Path("stories/jacob-2024.yaml"))
    await ChapterNarrator(Inner()).generate(story)
    assert spoken == [chapter_narration_text(story)]


def test_two_stories_for_one_name_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    import nobodynamed_video.longform.spec as spec_module

    real_load = spec_module.load_story
    real_evaluate = spec_module.evaluate_story
    jacob = real_load(Path("stories/jacob-2024.yaml"))

    def load(path: Path) -> StorySpec:
        if path.name == "emily-2024.yaml":
            return jacob.model_copy(update={"id": "jacob-duplicate"})
        return real_load(path)

    def evaluate(story: StorySpec) -> StoryEvaluation:
        return real_evaluate(jacob if story.id == "jacob-duplicate" else story)

    monkeypatch.setattr(spec_module, "load_story", load)
    monkeypatch.setattr(spec_module, "evaluate_story", evaluate)
    blockers = evaluate_longform(_episode(), require_approval=False).blockers
    assert "chapters must be distinct names (one story per name and sex)" in blockers


@pytest.mark.asyncio
async def test_release_render_rejects_a_used_hashtag_combination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nobodynamed_video.longform.render as render_module

    approved = tmp_path / "episode.yaml"
    write_longform(approve_longform(_episode(), "reviewer"), approved)
    db = tmp_path / "combos.db"
    # Recorded as the caption lexicon stores it: lowercase, no '#'. The episode's
    # mixed-case '#NameData' must still collide with it.
    tags = sorted(tag.lstrip("#").lower() for tag in _episode().hashtags)
    CombinationState(db).record(combo_hash(tags), tags, "earlier-video")
    monkeypatch.setattr(render_module, "_STATE_DB", db)

    with pytest.raises(StoryQualityError, match="hashtag combination already used"):
        await render_module.render_longform(approved, "http://unused.invalid", tmp_path / "out")


def test_undeclared_figures_in_title_card_copy_are_rejected() -> None:
    spec = _episode()
    outro = spec.outro.model_copy(update={"headline": "999,999 babies in 2025."})
    blockers = evaluate_longform(
        spec.model_copy(update={"outro": outro, "aggregate_claims": []}),
        require_approval=False,
    ).blockers
    assert "outro states 999,999, which matches no declared aggregate claim" in blockers
    assert stated_figures("over 113,000 in 2000, top-25, 1998") == [113000]


@pytest.mark.parametrize(
    "tags",
    [
        ["#AIVoice", "#NameData", "#NameData"],
        ["#AIVoice", "#NameData", "#namedata"],
        ["#AIVoice", "#NameData", "not a tag"],
    ],
)
def test_hashtags_must_be_distinct_valid_tokens(tags: list[str]) -> None:
    with pytest.raises(ValidationError):
        LongFormSpec.model_validate({**_episode().model_dump(), "hashtags": tags})
