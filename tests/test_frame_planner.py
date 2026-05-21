"""Frame planner tests — verifies shared-canvas planning over fixed frame buckets."""

from nobodynamed_video.data.classifier import classify
from nobodynamed_video.models import (
    NameRecord,
    ProgramType,
    ResolvedHook,
    Scene,
    VideoContext,
    VideoSpec,
    YearCount,
)
from nobodynamed_video.render.frame_planner import (
    SCENE_ORDER,
    frame_count,
    plan_frames,
    total_frame_count,
)
from nobodynamed_video.seed import spec_seed


def make_bertha_spec() -> VideoSpec:
    series = [
        YearCount(year=1880, count=39),
        YearCount(year=1910, count=5000),
        YearCount(year=1940, count=2000),
        YearCount(year=1980, count=60),
        YearCount(year=2000, count=30),
        YearCount(year=2024, count=29),
    ]
    record = NameRecord(
        name="Bertha",
        sex="F",
        series=series,
        peak_year=1910,
        peak_count=5000,
        current_year=2024,
        current_count=29,
    )
    tier = classify(record)
    scenes = [
        Scene(kind="hook", duration_s=3.0, template="hook", static_props={}),
        Scene(kind="reveal", duration_s=6.0, template="reveal", static_props={}),
        Scene(kind="narrative", duration_s=6.0, template="narrative", static_props={}),
        Scene(kind="cta", duration_s=3.0, template="cta", static_props={}),
    ]
    hook = ResolvedHook(
        id="ext-001-only-n-last-year",
        pillar="extinction-watch",
        voice_register="morbid",
        headline="Only 29 babies were named Bertha last year.",
        subhead="In 1910, there were 5,000.",
        pinned_comment="Do you know a Bertha under 30?",
        caption="Bertha is on the brink.",
    )
    context = VideoContext(
        name="Bertha",
        sex="F",
        first_letter="B",
        tier=tier,
        current_year=2024,
        current_count=29,
        current_rank=9999,
        current_decade=2020,
        peak_year=1910,
        peak_count=5000,
        peak_decade=1910,
        rank_at_peak=8,
        trough_year=1880,
        trough_count=39,
        years_since_peak=114,
        trough_to_now_years=144,
        decline_pct=99,
        rise_pct=12,
        year_range=144,
        start_year=1880,
        avg_age=71,
        generation_at_peak="Greatest",
        top10_years=3,
        program=ProgramType.CASE_FILE,
        hook=hook,
        narrative_text="Bertha now survives mostly as inherited memory.",
        supporting_text="Current births: 29.",
    )
    return VideoSpec(
        id="bertha-2024",
        record=record,
        tier=tier,
        scenes=scenes,
        fps=30,
        seed=spec_seed("bertha-2024"),
        program=ProgramType.CASE_FILE,
        hook=hook,
        context=context,
    )


def test_hook_frame_count() -> None:
    assert frame_count("hook", fps=30) == 90


def test_reveal_frame_count() -> None:
    assert frame_count("reveal", fps=30) == 180


def test_narrative_frame_count() -> None:
    assert frame_count("narrative", fps=30) == 180


def test_cta_frame_count() -> None:
    assert frame_count("cta", fps=30) == 90


def test_total_frame_count() -> None:
    assert total_frame_count(fps=30) == 540


def test_scene_order() -> None:
    assert ["hook", "reveal", "narrative", "cta"] == SCENE_ORDER


def test_plan_frames_total_count() -> None:
    spec = make_bertha_spec()
    frames = list(plan_frames(spec, fps=30))
    assert len(frames) == 540


def test_plan_frames_scene_distribution() -> None:
    spec = make_bertha_spec()
    counts: dict[str, int] = {}
    for scene_kind, _idx, _tpl, _props in plan_frames(spec, fps=30):
        counts[scene_kind] = counts.get(scene_kind, 0) + 1
    assert counts["hook"] == 90
    assert counts["reveal"] == 180
    assert counts["narrative"] == 180
    assert counts["cta"] == 90


def test_plan_frames_use_shared_canvas_template() -> None:
    spec = make_bertha_spec()
    first = next(iter(plan_frames(spec, fps=30)))
    assert first[2] == "canvas"


def test_canvas_props_have_required_blocks() -> None:
    spec = make_bertha_spec()
    props = next(props for _scene, _idx, _tpl, props in plan_frames(spec, fps=30))
    assert "header" in props
    assert "diagnosis" in props
    assert "chart" in props
    assert "stats" in props
    assert "narrative" in props
    assert "footer" in props


def test_recompose_progress_increases_after_dot_lands() -> None:
    spec = make_bertha_spec()
    frames = [props for _scene, _idx, _tpl, props in plan_frames(spec, fps=30)]
    pre_land = frames[245]["chart"]["layout_progress"]
    later = frames[290]["chart"]["layout_progress"]
    assert pre_land <= later


def test_narrative_alpha_appears_in_second_half() -> None:
    spec = make_bertha_spec()
    frames = [props for _scene, _idx, _tpl, props in plan_frames(spec, fps=30)]
    first_half = frames[180]["narrative"]["alpha"]
    second_half = frames[330]["narrative"]["alpha"]
    assert first_half <= second_half
