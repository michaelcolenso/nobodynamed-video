"""Tests for hook rendering and selection."""

import pytest
from nobodynamed_video.data.hooks import (
    load_hook_library,
    passes_data_guards,
    render_hook_template,
    resolve_hook,
)
from nobodynamed_video.exceptions import HookResolutionError
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


def test_passes_data_guards_bounds() -> None:
    ctx = {"decline_pct": 99, "rank_at_peak": 3, "event_decline_pct": None}
    assert passes_data_guards(None, ctx)
    assert passes_data_guards({"decline_pct": {"min": 50}}, ctx)
    assert not passes_data_guards({"decline_pct": {"max": 30}}, ctx)
    assert passes_data_guards({"decline_pct": {"min": 50, "max": 99}}, ctx)
    # None and missing values fail closed: copy never attaches to a name whose
    # data cannot prove its claim.
    assert not passes_data_guards({"event_decline_pct": {"min": 0}}, ctx)
    assert not passes_data_guards({"missing_var": {"min": 0}}, ctx)


def test_passes_data_guards_rejects_bad_specs() -> None:
    with pytest.raises(HookResolutionError):
        passes_data_guards({"decline_pct": {"between": 1}}, {"decline_pct": 5})
    with pytest.raises(HookResolutionError):
        passes_data_guards({"decline_pct": 5}, {"decline_pct": 5})


def test_resolve_hook_filters_on_requires_data() -> None:
    context = make_context().model_copy(update={"hook": None})  # decline_pct=99
    base = {
        "pillar": "cultural-collapse",
        "register": "cultural",
        "compatible_tiers": ["declining"],
        "requires_var": "killing_event",
        "headline": "h",
        "subhead": "s",
        "pinned_comment": "p?",
        "caption": "c",
    }
    library = {
        "hooks": [
            {**base, "id": "guarded", "requires_data": {"decline_pct": {"max": 30}}},
            {**base, "id": "open"},
        ]
    }
    for seed in range(20):
        hook = resolve_hook(context, style="cultural-collapse", spec_seed=seed, library=library)
        assert hook.id == "open"


def test_hook_requires_data_keys_are_real_context_fields() -> None:
    lib = load_hook_library()
    fields = set(VideoContext.model_fields)
    for hook in lib["hooks"]:  # type: ignore[union-attr]
        guards = hook.get("requires_data") or {}
        for key in guards:
            assert key in fields, f"{hook['id']} guards unknown context field {key!r}"
