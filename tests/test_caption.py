"""Tests for caption compositor: lexicon, state, and composition."""

from __future__ import annotations

from pathlib import Path

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
