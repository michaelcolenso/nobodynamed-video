"""Tests for editorial context derivation."""

import pytest
from nobodynamed_video.data.ctx import build_base_context, finalize_video_context
from nobodynamed_video.models import NameRecord, ResolvedHook, Tier, VideoContext, YearCount


class FakeSource:
    async def get_rank(self, name: str, sex: str, year: int) -> int:
        return {1910: 8, 1940: 44, 2024: 9999}.get(year, 9999)

    async def get_last_top_year(self, name: str, sex: str, threshold: int) -> int | None:
        return 1940 if threshold == 10 else 2024

    async def count_years_in_top(self, name: str, sex: str, threshold: int) -> int:
        return 3


@pytest.mark.asyncio
async def test_build_base_context_derives_core_stats() -> None:
    record = NameRecord(
        name="Bertha",
        sex="F",
        series=[
            YearCount(year=1880, count=39),
            YearCount(year=1910, count=5000),
            YearCount(year=1940, count=2000),
            YearCount(year=2024, count=29),
        ],
        peak_year=1910,
        peak_count=5000,
        current_year=2024,
        current_count=29,
    )
    ctx = await build_base_context(FakeSource(), record, Tier.CRITICAL, 2024, {})
    assert ctx.first_letter == "B"
    assert ctx.peak_decade == 1910
    assert ctx.current_rank == 9999
    assert ctx.rank_at_peak == 8
    assert ctx.decline_pct > 0


def test_finalize_video_context_sets_program_and_hook() -> None:
    base = VideoContext(
        name="Hazel",
        sex="F",
        first_letter="H",
        tier=Tier.RESURRECTED,
        current_year=2024,
        current_count=5000,
        current_rank=18,
        current_decade=2020,
        peak_year=2024,
        peak_count=5000,
        peak_decade=2020,
        rank_at_peak=18,
        trough_year=1977,
        trough_count=18,
        years_since_peak=0,
        trough_to_now_years=47,
        decline_pct=0,
        rise_pct=240,
        year_range=144,
        start_year=1880,
        avg_age=38,
        generation_at_peak="Gen Alpha",
    )
    hook = ResolvedHook(
        id="res",
        pillar="resurrection",
        voice_register="hopeful",
        headline="Hazel was almost extinct.",
        subhead="Now it is back.",
        pinned_comment="Do you know a Hazel?",
        caption="Hazel came back.",
    )
    ctx = finalize_video_context(base, hook)
    assert ctx.program is not None
    assert ctx.hook is not None
    assert ctx.narrative_text
