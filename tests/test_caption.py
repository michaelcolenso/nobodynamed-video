"""Tests for caption compositor: lexicon, state, and composition."""

from __future__ import annotations

import tempfile
from pathlib import Path

from nobodynamed_video.compose.state import CombinationState

from nobodynamed_video.compose.lexicon import Lexicon

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
