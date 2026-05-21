"""Tests for hook rendering and selection."""

from nobodynamed_video.data.hooks import render_hook_template, resolve_hook
from nobodynamed_video.models import ProgramType, ResolvedHook, Tier, VideoContext


def make_context() -> VideoContext:
    return VideoContext(
        name="Karen",
        sex="F",
        first_letter="K",
        tier=Tier.DECLINING,
        current_year=2024,
        current_count=186,
        current_rank=9999,
        current_decade=2020,
        peak_year=1965,
        peak_count=32873,
        peak_decade=1960,
        rank_at_peak=3,
        trough_year=1880,
        trough_count=10,
        years_since_peak=59,
        trough_to_now_years=144,
        decline_pct=99,
        rise_pct=0,
        year_range=144,
        start_year=1880,
        avg_age=62,
        generation_at_peak="Boomer",
        last_top_1000_year=2024,
        last_top_10_year=1969,
        top10_years=6,
        killing_event="the meme",
        collapse_year=2019,
        program=ProgramType.CULTURAL_EVENT,
        hook=ResolvedHook(
            id="placeholder",
            pillar="cultural-collapse",
            voice_register="cultural",
            headline="placeholder",
            subhead="placeholder",
            pinned_comment="placeholder",
            caption="placeholder",
        ),
    )


def test_render_hook_template_applies_filters() -> None:
    ctx = make_context().as_template_context()
    text = render_hook_template("Peak {{ peak_count | thousands }} in {{ peak_year }}.", ctx)
    assert text == "Peak 32,873 in 1965."


def test_resolve_hook_filters_on_required_var() -> None:
    context = make_context().model_copy(update={"hook": None})
    library = {
        "hooks": [
            {
                "id": "cult",
                "pillar": "cultural-collapse",
                "register": "cultural",
                "compatible_tiers": ["declining"],
                "requires_var": "killing_event",
                "headline": "What killed {{ name }}?",
                "subhead": "Peak {{ peak_year }}. Today: {{ current_count }}.",
                "pinned_comment": "How?",
                "caption": "{{ name }} is a cultural story.",
            }
        ]
    }
    hook = resolve_hook(context, style="cultural-collapse", spec_seed=1, library=library)
    assert hook.id == "cult"
    assert hook.headline == "What killed Karen?"
