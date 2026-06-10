"""Tests for narrative scene copy selection."""

from __future__ import annotations

from nobodynamed_video.data.narratives import (
    _NARRATIVE_SALT,
    load_narrative_library,
    select_narrative,
)
from nobodynamed_video.models import ProgramType, Tier, VideoContext


def _make_ctx(**overrides: object) -> VideoContext:
    defaults = dict(
        name="Bertha",
        sex="F",
        first_letter="B",
        tier=Tier.EXTINCT,
        current_year=2024,
        current_count=8,
        current_rank=9999,
        current_decade=2020,
        peak_year=1904,
        peak_count=5198,
        peak_decade=1900,
        rank_at_peak=14,
        trough_year=2019,
        trough_count=5,
        years_since_peak=120,
        trough_to_now_years=5,
        decline_pct=99,
        rise_pct=0,
        year_range=144,
        start_year=1880,
        avg_age=72,
        generation_at_peak="Greatest",
    )
    defaults.update(overrides)
    return VideoContext(**defaults)


def test_select_narrative_returns_tuple() -> None:
    primary, supporting = select_narrative(
        _make_ctx(), ProgramType.CASE_FILE, Tier.EXTINCT, seed=42
    )
    assert isinstance(primary, str)
    assert primary


def test_select_narrative_deterministic() -> None:
    ctx = _make_ctx()
    a = select_narrative(ctx, ProgramType.CASE_FILE, Tier.EXTINCT, seed=42)
    b = select_narrative(ctx, ProgramType.CASE_FILE, Tier.EXTINCT, seed=42)
    assert a == b


def test_select_narrative_variety() -> None:
    ctx = _make_ctx()
    results = {
        select_narrative(ctx, ProgramType.CASE_FILE, Tier.EXTINCT, seed=s)[0] for s in range(50)
    }
    assert len(results) >= 2, "Expected multiple distinct narratives across seeds"


def test_select_narrative_cultural_event() -> None:
    from nobodynamed_video.models import ResolvedCulturalEvent

    event = ResolvedCulturalEvent(name="Karen", sex="F", killing_event="the meme", event_year=2018)
    ctx = _make_ctx(
        name="Karen",
        tier=Tier.DECLINING,
        killing_event="the meme",
        cultural_event=event,
    )
    primary, supporting = select_narrative(ctx, ProgramType.CULTURAL_EVENT, Tier.DECLINING, seed=1)
    assert primary
    assert supporting


def test_select_narrative_return_notice() -> None:
    ctx = _make_ctx(
        name="Hazel",
        tier=Tier.RESURRECTED,
        rise_pct=340,
        trough_count=50,
        current_count=1200,
    )
    primary, _supporting = select_narrative(
        ctx, ProgramType.RETURN_NOTICE, Tier.RESURRECTED, seed=7
    )
    assert primary


def test_requires_var_filtering() -> None:
    lib = load_narrative_library()
    ctx = _make_ctx(killing_event=None)
    primary, _ = select_narrative(
        ctx, ProgramType.CULTURAL_EVENT, Tier.DECLINING, seed=0, library=lib
    )
    assert "killing_event" not in primary
    assert "None" not in primary


def test_primary_under_budget() -> None:
    ctx = _make_ctx()
    for seed in range(30):
        primary, _ = select_narrative(ctx, ProgramType.CASE_FILE, Tier.EXTINCT, seed=seed)
        assert len(primary) <= 84, f"Primary too long ({len(primary)}): {primary!r}"


def test_narrative_ids_unique() -> None:
    lib = load_narrative_library()
    ids = [n["id"] for n in lib["narratives"]]
    assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"


def test_salt_decorrelates_from_hooks() -> None:
    assert _NARRATIVE_SALT != 0
    assert _NARRATIVE_SALT.bit_length() > 16
