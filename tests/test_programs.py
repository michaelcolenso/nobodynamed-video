"""Tests for sample_program_frame card motion: stagger, spring, counters."""

from nobodynamed_video.models import (
    NameRecord,
    ProgramType,
    ResolvedHook,
    Tier,
    VideoContext,
    VideoSpec,
    YearCount,
)
from nobodynamed_video.render.programs import (
    CARD_IN_S,
    CARD_STAGGER_S,
    CARD_START_T,
    COUNTER_IN_S,
    CTA_DELAY_S,
    NARRATIVE_DELAY_S,
    SUPPORT_DELAY_S,
    sample_program_frame,
)


def _spec() -> VideoSpec:
    series = [YearCount(year=y, count=0) for y in range(1880, 1960)]
    rise = zip(range(1960, 1977), range(200, 5000, 283), strict=True)
    series += [YearCount(year=y, count=c) for y, c in rise]
    series.append(YearCount(year=1977, count=5000))
    series += [
        YearCount(year=y, count=max(0, 5000 - (y - 1977) * 120))
        for y in range(1978, 2024)
    ]
    series.append(YearCount(year=2024, count=42))
    record = NameRecord(
        name="Bertha",
        sex="F",
        series=series,
        peak_year=1977,
        peak_count=5000,
        current_year=2024,
        current_count=42,
    )
    hook = ResolvedHook(
        id="h1",
        pillar="p",
        voice_register="case_file",
        headline="Headline",
        subhead="Subhead",
        pinned_comment="",
        caption="",
    )
    ctx = VideoContext(
        name="Bertha",
        sex="F",
        first_letter="B",
        tier=Tier.CRITICAL,
        current_year=2024,
        current_count=42,
        current_rank=9999,
        current_decade=2020,
        peak_year=1977,
        peak_count=5000,
        peak_decade=1970,
        rank_at_peak=10,
        trough_year=2024,
        trough_count=42,
        years_since_peak=47,
        trough_to_now_years=0,
        decline_pct=99,
        rise_pct=0,
        year_range=144,
        start_year=1960,
        avg_age=70,
        generation_at_peak="Boomer",
        program=ProgramType.CASE_FILE,
        narrative_text="narrative",
        supporting_text="support",
    )
    return VideoSpec(
        id="bertha-test",
        record=record,
        tier=Tier.CRITICAL,
        scenes=[],
        seed=1,
        program=ProgramType.CASE_FILE,
        hook=hook,
        context=ctx,
    )


def test_card_stagger_is_exactly_80ms() -> None:
    spec = _spec()
    # Between card 0 and card 1 entrances: card 0 has started, card 1 has not.
    frame = sample_program_frame(spec, CARD_START_T + CARD_STAGGER_S * 0.5)
    alphas = frame["stats"]["card_alphas"]
    assert alphas[0] > 0.0
    assert alphas[1] == 0.0
    assert alphas[2] == 0.0
    # Between card 1 and card 2.
    frame = sample_program_frame(spec, CARD_START_T + CARD_STAGGER_S * 1.5)
    alphas = frame["stats"]["card_alphas"]
    assert alphas[1] > 0.0
    assert alphas[2] == 0.0
    assert CARD_STAGGER_S == 0.08


def test_card_spring_rise_overshoots_and_settles() -> None:
    spec = _spec()
    offsets = [
        sample_program_frame(spec, CARD_START_T + CARD_IN_S * f)["stats"]["card_offsets"][0]
        for f in [i / 20 for i in range(0, 21)]
    ]
    # 12px rise: starts 12px low, springs slightly PAST the resting position
    # (negative offset = overshoot), then settles to exactly 0.
    assert offsets[0] == 12.0
    assert min(offsets) < 0.0
    assert offsets[-1] == 0.0


def test_counters_roll_up_with_deceleration() -> None:
    spec = _spec()
    # PEAK BIRTHS is card index 1; its counter runs from its staggered start.
    start = CARD_START_T + CARD_STAGGER_S
    at_start = sample_program_frame(spec, start)["stats"]["card_values"][1]
    mid = sample_program_frame(spec, start + COUNTER_IN_S / 2)["stats"]["card_values"][1]
    done = sample_program_frame(spec, start + COUNTER_IN_S)["stats"]["card_values"][1]
    assert at_start == "0"
    assert 0 < int(mid.replace(",", "")) < 5000
    assert done == "5,000"
    # Deceleration: second half covers less ground than the first half.
    mid_v = int(mid.replace(",", ""))
    assert mid_v > 5000 - mid_v
    # CURRENT card (index 2) also rolls; PEAK YEAR (index 0) stays static.
    cur_done = sample_program_frame(spec, CARD_START_T + 2 * CARD_STAGGER_S + COUNTER_IN_S)
    assert cur_done["stats"]["card_values"][2] == "42"
    assert cur_done["stats"]["card_values"][0] == "1977"


def test_narrative_and_cta_anchor_to_card_start() -> None:
    spec = _spec()
    # User-specified reveal beats relative to CARD_START_T: narrative at
    # +300ms, URL/CTA footer at +450ms.
    assert NARRATIVE_DELAY_S == 0.300
    assert CTA_DELAY_S == 0.450
    narrative_start = CARD_START_T + NARRATIVE_DELAY_S
    footer_start = CARD_START_T + CTA_DELAY_S
    # Tracks use standard Hyperframe semantics: exactly 0 at the start frame,
    # rising immediately after, fully in once the fade completes.
    assert sample_program_frame(spec, narrative_start)["narrative"]["alpha"] == 0.0
    assert sample_program_frame(spec, footer_start)["footer"]["alpha"] == 0.0
    assert 0.0 < sample_program_frame(spec, narrative_start + 0.05)["narrative"]["alpha"] < 1.0
    assert 0.0 < sample_program_frame(spec, footer_start + 0.05)["footer"]["alpha"] < 1.0
    # Narrative precedes the CTA: it is already fading in when the footer starts.
    assert sample_program_frame(spec, footer_start)["narrative"]["alpha"] > 0.0
    # Both are fully visible well before the endcard hold.
    done = sample_program_frame(spec, CARD_START_T + 1.2)
    assert done["narrative"]["alpha"] == 1.0
    assert done["footer"]["alpha"] == 1.0


def test_support_rides_with_narrative_beat() -> None:
    spec = _spec()
    # Support rides the narrative beat (+300ms), not the CTA (+450ms), so the
    # supporting line is already fading in while the footer appears — this,
    # combined with the raised narrative block in canvas.tsx, keeps the
    # supporting text clear of the footer for 2-line content.
    assert SUPPORT_DELAY_S == NARRATIVE_DELAY_S == 0.300
    assert SUPPORT_DELAY_S < CTA_DELAY_S
    support_start = CARD_START_T + SUPPORT_DELAY_S
    assert sample_program_frame(spec, support_start)["narrative"]["support_alpha"] == 0.0
    assert (
        0.0
        < sample_program_frame(spec, support_start + 0.05)["narrative"]["support_alpha"]
        < 1.0
    )
    # Support is mid-fade when the footer starts, and fully in before it ends.
    assert sample_program_frame(spec, CARD_START_T + CTA_DELAY_S)["narrative"]["support_alpha"] > 0.0
    assert sample_program_frame(spec, CARD_START_T + 1.2)["narrative"]["support_alpha"] == 1.0
