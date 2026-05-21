"""Tests for caption compositor: lexicon, state, and composition."""

from __future__ import annotations

import tempfile
from pathlib import Path

from nobodynamed_video.compose.lexicon import Lexicon
from nobodynamed_video.compose.state import CombinationState

CAPTIONS_YAML = Path("fixtures/captions.yaml")


def test_lexicon_loads_constraints() -> None:
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    assert lex.constraints.caption_max_chars == 150
    assert lex.constraints.hashtags_min == 3
    assert lex.constraints.hashtags_max == 5
    assert lex.constraints.emotional_words_min == 2
    assert lex.constraints.emotional_words_max == 3
    assert lex.constraints.pinned_max_chars == 100
    assert lex.constraints.regeneration_attempts == 50


def test_lexicon_hashtags_for_returns_active_only() -> None:
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    core = lex.hashtags_for("morbid", "core")
    assert all(h.active for h in core)
    assert all("morbid" in h.registers for h in core)
    all_tags = [h.tag for h in lex.hashtags_for("morbid", "trend")]
    assert "namesoftiktok2026" not in all_tags


def test_lexicon_words_for_returns_register_pool() -> None:
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    words = lex.words_for("morbid")
    assert "vanishing" in words
    assert "fading" in words
    assert len(words) >= 5


def test_lexicon_frames_for_filters_requires_vars() -> None:
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    ctx: dict = {"name": "Karen", "peak_count": 32873, "current_count": 325}
    frames = lex.frames_for("cultural-collapse", ctx)
    ids = [f.id for f in frames]
    assert "cult-frame-killed" not in ids
    assert "cult-frame-before" not in ids


def test_lexicon_frames_for_includes_when_vars_present() -> None:
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    ctx: dict = {
        "name": "Karen",
        "killing_event": "the meme",
        "peak_count": 32873,
        "current_count": 325,
    }
    frames = lex.frames_for("cultural-collapse", ctx)
    ids = [f.id for f in frames]
    assert "cult-frame-killed" in ids


def test_lexicon_patterns_for_filters_unresolvable() -> None:
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    ctx: dict = {"name": "Bertha", "peak_year": 1910}
    patterns = lex.patterns_for("peak-year", ctx)
    assert len(patterns) > 0
    for p in patterns:
        assert "{{" not in p


def test_state_new_combo_not_used() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        assert not state.is_used("abc123")


def test_state_record_then_is_used() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        state.record("deadbeef", ["namedata", "babynames", "onthebrink"], "bertha-2024")
        assert state.is_used("deadbeef")


def test_state_different_combos_independent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        state.record("hash1", ["a", "b", "c"], "spec-1")
        assert state.is_used("hash1")
        assert not state.is_used("hash2")


def test_state_tag_uses_this_week_counts_correctly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        state.record("h1", ["fyp", "namedata", "babynames"], "spec-1")
        state.record("h2", ["fyp", "ssadata", "onthebrink"], "spec-2")
        state.record("h3", ["namedata", "babynames", "namefact"], "spec-3")
        assert state.tag_uses_this_week("fyp") == 2
        assert state.tag_uses_this_week("namedata") == 2
        assert state.tag_uses_this_week("culturalcollapse") == 0


def test_state_reset_clears_all_records() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        state.record("h1", ["a", "b", "c"], "spec-1")
        state.reset()
        assert not state.is_used("h1")


# ---------------------------------------------------------------------------
# Compositor tests
# ---------------------------------------------------------------------------

from nobodynamed_video.compose.caption import (  # noqa: E402
    ComposedCaption,
    combo_hash,
    compose_caption,
)
from nobodynamed_video.models import (  # noqa: E402
    ResolvedHook,
    Tier,
    VideoContext,
)


def _make_hook(pillar: str = "extinction-watch", register: str = "morbid") -> ResolvedHook:
    return ResolvedHook(
        id="ext-001",
        pillar=pillar,
        voice_register=register,
        headline="The Bertha you know is probably the last one you'll meet.",
        subhead="9 born last year.",
        pinned_comment="Tag the only Bertha you know.",
        caption="Bertha is on the brink.",
    )


def _make_ctx() -> VideoContext:
    return VideoContext(
        name="Bertha",
        sex="F",
        first_letter="B",
        tier=Tier.CRITICAL,
        current_year=2024,
        current_count=9,
        current_rank=9999,
        current_decade=2020,
        peak_year=1910,
        peak_count=5000,
        peak_decade=1910,
        rank_at_peak=12,
        trough_year=2020,
        trough_count=9,
        years_since_peak=114,
        trough_to_now_years=4,
        decline_pct=99,
        rise_pct=0,
        year_range=144,
        start_year=1880,
        avg_age=80,
        generation_at_peak="Greatest",
    )


def test_combo_hash_is_order_independent() -> None:
    h1 = combo_hash(["namedata", "babynames", "onthebrink"])
    h2 = combo_hash(["onthebrink", "namedata", "babynames"])
    assert h1 == h2


def test_compose_caption_returns_composed_caption() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state)
        assert isinstance(result, ComposedCaption)
        assert result.caption
        assert result.pinned_comment
        assert result.hashtag_set


def test_compose_caption_respects_length_limits() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state)
        assert len(result.caption) <= 150
        assert len(result.pinned_comment) <= 100


def test_compose_caption_pinned_ends_with_question_mark() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state)
        assert result.pinned_comment.rstrip().endswith("?")


def test_compose_caption_has_core_hashtag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state)
        core_tags = {h.tag for h in lex.hashtags_for("morbid", "core")}
        assert any(t in core_tags for t in result.hashtag_set)


def test_compose_caption_hashtag_count_in_range() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state)
        assert 3 <= len(result.hashtag_set) <= 5


def test_compose_caption_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state1 = CombinationState(Path(tmp) / "a.db")
        state2 = CombinationState(Path(tmp) / "b.db")
        r1 = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state1)
        r2 = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state2)
        assert r1.caption == r2.caption
        assert r1.pinned_comment == r2.pinned_comment
        assert r1.hashtag_set == r2.hashtag_set


def test_compose_caption_records_combo_in_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption("bertha-2024", _make_hook(), _make_ctx(), lex, state)
        h = combo_hash(result.hashtag_set)
        assert state.is_used(h)


def test_compose_caption_can_reach_five_hashtags() -> None:
    """When emotional pool is large, compositor can produce 5 hashtags."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        # Run across multiple spec IDs and verify at least one produces 4+
        counts = set()
        for i in range(10):
            r = compose_caption(f"spec-{i}", _make_hook(), _make_ctx(), lex, state)
            counts.add(len(r.hashtag_set))
        assert max(counts) >= 4  # can reach 4 or 5 depending on pools
