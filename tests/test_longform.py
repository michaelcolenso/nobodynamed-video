"""Long-form episodes: gate, snapshot-backed facts, title-card motion, chapters, assembly."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from nobodynamed_video.compose.caption import combo_hash
from nobodynamed_video.compose.ffmpeg import build_concat_cmd
from nobodynamed_video.compose.narration import CHAPTER_HOLD_S, NarrationArtifact, adaptive_duration
from nobodynamed_video.compose.narration_pacing import (
    PACED_OVERSHOOT_TOLERANCE_S,
    fit_narration_audio,
)
from nobodynamed_video.compose.state import CombinationState
from nobodynamed_video.data.snapshot import Snapshot, verified_snapshot
from nobodynamed_video.editorial.story import StoryEvaluation, chapter_narration_text, load_story
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.longform.bookends import (
    BOOKEND_FIT_TARGET_S,
    MAX_BOOKEND_NARRATION_S,
    MAX_BOOKEND_S,
    MIN_BOOKEND_S,
    bookend_duration,
    roster_rows,
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
    stated_name_counts,
    stated_rank_claims,
    stated_year_figures,
    write_longform,
)
from nobodynamed_video.models import AggregateClaim, LongFormSpec, RankClaim, StorySpec
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


def test_any_accepted_pace_fit_fits_the_title_card() -> None:
    # Regression: a 9.11s fit against a 9.10s limit rejected the whole episode.
    worst_accepted = BOOKEND_FIT_TARGET_S + PACED_OVERSHOOT_TOLERANCE_S
    assert worst_accepted < MAX_BOOKEND_NARRATION_S
    assert bookend_duration(_episode().intro, worst_accepted, FPS) <= MAX_BOOKEND_S


def test_overlong_bookend_narration_is_pace_fitted_onto_the_card(tmp_path: Path) -> None:
    wav = tmp_path / "card.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:duration=12.5",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ],
        check=True,
    )
    artifact = NarrationArtifact(
        audio_path=wav, word_timings=[], duration_s=12.5, provider="t", model="t", voice="t"
    )
    fitted = fit_narration_audio(artifact, target_duration_s=BOOKEND_FIT_TARGET_S)
    assert fitted.duration_s <= MAX_BOOKEND_NARRATION_S
    assert bookend_duration(_episode().intro, fitted.duration_s, FPS) <= MAX_BOOKEND_S


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
    assert "outro headline states 999,999 for 2025, which has no claim" in blockers
    assert stated_figures("over 113,000 in 2000, top-25, 1998") == [113000]


def test_each_stated_figure_must_match_its_own_year() -> None:
    spec = _episode()
    swapped = spec.outro.model_copy(update={"headline": "20,979 babies in 2000. 113,356 in 2025."})
    blockers = evaluate_longform(
        spec.model_copy(update={"outro": swapped}), require_approval=False
    ).blockers
    assert "outro headline states 20,979 for 2000; the declared total is 113,356" in blockers
    assert stated_year_figures("From 113,356 in 2000 to 20,979 in 2025.") == [
        (2000, 113356),
        (2025, 20979),
    ]
    assert stated_year_figures("113,356 and 20,979 in 2000.") == [(None, 113356), (None, 20979)]


def test_social_caption_figures_are_verified() -> None:
    spec = _episode()
    bad = spec.model_copy(update={"social_caption": "These five had 999,999 births in 2025."})
    blockers = evaluate_longform(bad, require_approval=False).blockers
    assert "social caption states 999,999 for 2025; the declared total is 20,979" in blockers


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


def test_rank_claims_are_verified_against_snapshot_ranks() -> None:
    spec = _episode()
    too_tight = spec.model_copy(update={"rank_claims": [RankClaim(year=2000, top=10)]})
    blockers = evaluate_longform(too_tight, require_approval=False).blockers
    assert "rank claim top-10 in 2000 fails: Destiny was #24" in blockers
    undeclared = spec.model_copy(update={"rank_claims": []})
    blockers = evaluate_longform(undeclared, require_approval=False).blockers
    assert "intro subhead states top-25 in 2000, which has no rank claim" in blockers
    assert "intro script states top-25 in 2000, which has no rank claim" in blockers
    assert stated_rank_claims("In 2000, all five were top twenty-five.") == [(2000, 25)]
    assert stated_rank_claims("They held the top spot.") == []


def test_counts_below_one_thousand_are_verified() -> None:
    spec = _episode()
    outro = spec.outro.model_copy(update={"headline": "Only 999 babies in 2025."})
    blockers = evaluate_longform(
        spec.model_copy(update={"outro": outro}), require_approval=False
    ).blockers
    assert "outro headline states 999 for 2025; the declared total is 20,979" in blockers


def test_chapters_must_carry_archive_pinned_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    import nobodynamed_video.longform.spec as spec_module

    real = spec_module.verified_snapshot

    def dataset_only(story: StorySpec) -> Snapshot:
        return real(story).model_copy(
            update={
                "source_url": None,
                "archive_sha256": None,
                "source_dataset": "nobodynamed-d1:name-vitals",
            }
        )

    monkeypatch.setattr(spec_module, "verified_snapshot", dataset_only)
    blockers = evaluate_longform(_episode(), require_approval=False).blockers
    assert "every chapter snapshot must be pinned to the SSA archive" in blockers


def test_counts_below_one_hundred_and_the_title_are_verified() -> None:
    spec = _episode()
    blockers = evaluate_longform(
        spec.model_copy(
            update={"social_caption": "Only 99 babies in 2025.", "title": "458 in 2025"}
        ),
        require_approval=False,
    ).blockers
    assert "social caption states 99 for 2025; the declared total is 20,979" in blockers
    assert "title states 458 for 2025; the declared total is 20,979" in blockers
    assert stated_figures("Emily held #1 and was top-25 in 2000.") == []


def test_title_card_holds_at_most_four_totals() -> None:
    claims = [{"year": 2000 + i, "total": 1000} for i in range(5)]
    with pytest.raises(ValidationError):
        LongFormSpec.model_validate({**_episode().model_dump(), "aggregate_claims": claims})


def test_a_title_card_uses_one_detail_layout() -> None:
    with pytest.raises(ValidationError, match="roster or the totals"):
        _episode().intro.model_copy(update={"show_totals": True}).model_validate(
            {**_episode().intro.model_dump(), "show_totals": True}
        )


def test_suppressed_latest_count_renders_as_under_five() -> None:
    entry = RosterEntry("Bertha", 1918, 5051, 2025, None)
    row = roster_rows([entry])[0]
    assert entry.decline_pct is None
    assert row["detail"] == "5,051 in 1918 → <5 in 2025"
    assert row["value"] == "<5"


@pytest.mark.parametrize(
    ("caption", "token"),
    [
        ("They had 999k births in 2025.", "999k"),
        ("Jacob ranked #1 in 2000.", "#1"),
        ("Down 83% since 2000.", "83%"),
    ],
)
def test_unverifiable_numeric_notation_is_rejected(caption: str, token: str) -> None:
    spec = _episode().model_copy(update={"social_caption": caption})
    blockers = evaluate_longform(spec, require_approval=False).blockers
    assert any(
        b.startswith("social caption uses numeric notation") and token in b for b in blockers
    )


def test_name_count_phrases_must_match_the_chapter_count() -> None:
    spec = _episode()
    four = spec.model_copy(update={"chapters": spec.chapters[:4], "aggregate_claims": []})
    blockers = evaluate_longform(four, require_approval=False).blockers
    assert "title speaks of 5 names; the episode has 4 chapters" in blockers
    assert "intro script speaks of 5 names; the episode has 4 chapters" in blockers
    assert stated_name_counts("Which one was yours? All five were top-25.") == [5]


def test_combination_claim_is_atomic_and_releasable(tmp_path: Path) -> None:
    state = CombinationState(tmp_path / "combos.db")
    assert state.claim("abc", ["genz"], "episode-a")
    assert not state.claim("abc", ["genz"], "episode-b")
    state.release("abc", "episode-b")
    assert state.is_used("abc")
    state.release("abc", "episode-a")
    assert not state.is_used("abc")
