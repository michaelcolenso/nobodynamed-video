"""Tests for narrative scene copy selection."""

from __future__ import annotations

from nobodynamed_video.data.narratives import (
    _FALLBACK,
    _NARRATIVE_SALT,
    load_narrative_library,
    select_narrative,
)
from nobodynamed_video.models import (
    ProgramType,
    ResolvedCulturalEvent,
    Tier,
    VideoContext,
)


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
    if defaults.get("killing_event") and "cultural_event" not in overrides:
        defaults["cultural_event"] = ResolvedCulturalEvent(
            name=str(defaults["name"]),
            sex=str(defaults["sex"]),
            killing_event=str(defaults["killing_event"]),
            event_year=int(defaults.get("event_year") or 2000),
            evidence="test evidence",
            validated=True,
            observed_decline_pct=30,
        )
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
    event = ResolvedCulturalEvent(
        name="Karen",
        sex="F",
        killing_event="the meme",
        event_year=2018,
        evidence="test evidence",
        validated=True,
        observed_decline_pct=40,
    )
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


def _all_selections(
    ctx: VideoContext, program: ProgramType, tier: Tier, seeds: int = 100
) -> set[tuple[str, str | None]]:
    return {select_narrative(ctx, program, tier, seed=s) for s in range(seeds)}


def test_stable_reveal_never_claims_stability_for_collapsed_name() -> None:
    # Walter: 18,000 births at the 1920 peak, 180 now. STABLE only means the
    # *recent* trend is flat — "held the line" / "steady since the 1920s" must
    # be unreachable, and the collapse-then-plateau variant must tell the
    # truthful version of the story.
    ctx = _make_ctx(
        name="Walter",
        tier=Tier.STABLE,
        current_count=180,
        peak_year=1920,
        peak_count=18000,
        peak_decade=1920,
        rank_at_peak=11,
        current_rank=9999,
        years_since_peak=104,
        decline_pct=99,
        trough_year=2013,
        trough_count=160,
    )
    selections = _all_selections(ctx, ProgramType.CASE_FILE, Tier.STABLE)
    joined = " | ".join(p + " " + (s or "") for p, s in selections)
    assert "held the line" not in joined
    assert "Stability is the rarest" not in joined
    assert "Steady since" not in joined
    assert _FALLBACK not in selections, "collapsed-but-flat names must keep real copy"
    assert "found its floor" in joined


def test_stable_reveal_held_the_line_requires_low_decline() -> None:
    # A genuinely steady name (Henry-shaped) keeps the held-the-line copy and
    # never gets the collapse framing.
    ctx = _make_ctx(
        name="Henry",
        tier=Tier.STABLE,
        current_count=9000,
        current_rank=9,
        rank_at_peak=5,
        peak_year=2010,
        peak_decade=2010,
        years_since_peak=14,
        decline_pct=8,
        trough_year=1994,
        trough_count=4000,
    )
    primaries = {p for p, _ in _all_selections(ctx, ProgramType.CASE_FILE, Tier.STABLE)}
    assert any("held the line" in p for p in primaries)
    assert all("found its floor" not in p for p in primaries)
    assert all(
        "stopped being dominant" not in p for p in primaries
    ), "a current top-10 name is still dominant"


def test_cultural_reveal_matches_event_timing() -> None:
    # Alexa-shaped: at its peak when the event hit. "Already fading" is false
    # and must be unreachable; the at-peak variant applies.
    at_peak = _make_ctx(
        name="Alexa",
        tier=Tier.CRITICAL,
        killing_event="Amazon Echo",
        event_year=2014,
        peak_year=2015,
        peak_decade=2010,
        peak_to_event_years=-1,
        event_decline_pct=3,
        decline_pct=91,
    )
    primaries = {p for p, _ in _all_selections(at_peak, ProgramType.CULTURAL_EVENT, Tier.CRITICAL)}
    assert all("already fading" not in p for p in primaries)
    assert any("was at its peak when" in p for p in primaries)

    # Karen-shaped: 99% off peak by the event year. The fading variants apply,
    # the at-peak variant must not.
    fading = _make_ctx(
        name="Karen",
        tier=Tier.DECLINING,
        killing_event="the meme",
        event_year=2018,
        peak_year=1965,
        peak_decade=1960,
        peak_to_event_years=53,
        event_decline_pct=99,
        decline_pct=99,
    )
    primaries = {p for p, _ in _all_selections(fading, ProgramType.CULTURAL_EVENT, Tier.DECLINING)}
    assert any("already fading" in p for p in primaries)
    assert all("was at its peak when" not in p for p in primaries)


def test_return_notice_growth_claims_require_growth() -> None:
    # A resurrected name that came back years ago and flattened: no "% growth"
    # copy may render, but the result must not be the bland fallback either.
    ctx = _make_ctx(
        name="Eleanor",
        tier=Tier.RESURRECTED,
        rise_pct=0,
        trough_count=20,
        trough_year=1999,
        current_count=900,
        peak_year=2024,
        peak_decade=2020,
        years_since_peak=0,
        decline_pct=0,
    )
    selections = _all_selections(ctx, ProgramType.RETURN_NOTICE, Tier.RESURRECTED)
    assert _FALLBACK not in selections
    for primary, supporting in selections:
        assert "%" not in primary + " " + (supporting or "")


def test_no_program_tier_combination_starves_to_fallback() -> None:
    # Adversarial-but-tier-consistent contexts: every production program/tier
    # pairing must keep at least one provably-true variant viable.
    cases = [
        (_make_ctx(tier=Tier.EXTINCT, current_count=0), ProgramType.CASE_FILE, Tier.EXTINCT),
        (
            _make_ctx(tier=Tier.CRITICAL, current_count=18, decline_pct=99),
            ProgramType.CASE_FILE,
            Tier.CRITICAL,
        ),
        (
            _make_ctx(tier=Tier.DECLINING, current_count=400, decline_pct=88),
            ProgramType.CASE_FILE,
            Tier.DECLINING,
        ),
        # Stable, mid-decline, too common for the "quietly" line: rank guard
        # variant must catch it.
        (
            _make_ctx(
                tier=Tier.STABLE,
                decline_pct=40,
                current_count=2500,
                current_rank=200,
                rank_at_peak=60,
                years_since_peak=30,
            ),
            ProgramType.CASE_FILE,
            Tier.STABLE,
        ),
        # Stable, mid-decline, rare and never highly ranked.
        (
            _make_ctx(
                tier=Tier.STABLE,
                decline_pct=45,
                current_count=400,
                current_rank=9999,
                rank_at_peak=9999,
                years_since_peak=60,
            ),
            ProgramType.CASE_FILE,
            Tier.STABLE,
        ),
        # Rising with no dormant past (new-name shape).
        (
            _make_ctx(
                tier=Tier.RISING,
                rise_pct=25,
                trough_count=3000,
                current_count=9000,
                years_since_peak=0,
                decline_pct=0,
            ),
            ProgramType.CASE_FILE,
            Tier.RISING,
        ),
        # Resurrected that re-peaked now with a flat recent trend.
        (
            _make_ctx(
                tier=Tier.RESURRECTED,
                rise_pct=0,
                trough_count=20,
                years_since_peak=0,
                decline_pct=0,
            ),
            ProgramType.CASE_FILE,
            Tier.RESURRECTED,
        ),
        (
            _make_ctx(
                tier=Tier.RISING,
                rise_pct=25,
                trough_count=3000,
                years_since_peak=0,
                decline_pct=0,
            ),
            ProgramType.RETURN_NOTICE,
            Tier.RISING,
        ),
        # Cultural event with no derivable event timing: only the timing-free
        # variant is provable, and it must exist.
        (
            _make_ctx(
                tier=Tier.DECLINING,
                killing_event="the meme",
                peak_to_event_years=None,
                event_decline_pct=None,
            ),
            ProgramType.CULTURAL_EVENT,
            Tier.DECLINING,
        ),
        (
            _make_ctx(
                tier=Tier.EXTINCT,
                current_count=0,
                killing_event="the hurricane",
                peak_to_event_years=None,
                event_decline_pct=None,
            ),
            ProgramType.CULTURAL_EVENT,
            Tier.EXTINCT,
        ),
    ]
    for ctx, program, tier in cases:
        selections = _all_selections(ctx, program, tier, seeds=20)
        assert (
            _FALLBACK not in selections
        ), f"fallback reached for program={program.value} tier={tier.value} name={ctx.name}"


def test_requires_data_keys_are_real_context_fields() -> None:
    lib = load_narrative_library()
    fields = set(VideoContext.model_fields)
    for narr in lib["narratives"]:  # type: ignore[union-attr]
        guards = narr.get("requires_data") or {}
        for key in guards:
            assert key in fields, f"{narr['id']} guards unknown context field {key!r}"
