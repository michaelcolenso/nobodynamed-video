"""Frame planner tests — verifies exact frame counts and prop structure."""

from nobodynamed_video.data.classifier import classify
from nobodynamed_video.models import NameRecord, Tier, YearCount
from nobodynamed_video.render.frame_planner import (
    SCENE_ORDER,
    frame_count,
    plan_frames,
    total_frame_count,
)
from nobodynamed_video.seed import spec_seed


def make_bertha_spec() -> object:
    """Build a minimal VideoSpec for Bertha-2024 suitable for frame planning."""
    from nobodynamed_video.models import VideoSpec, Scene

    series = [
        YearCount(year=1910, count=5000),
        YearCount(year=1940, count=2000),
        YearCount(year=1980, count=60),
        YearCount(year=2000, count=30),
        YearCount(year=2024, count=9),
    ]
    record = NameRecord(
        name="Bertha",
        sex="F",
        series=series,
        peak_year=1910,
        peak_count=5000,
        current_year=2024,
        current_count=9,
    )
    tier = classify(record)
    scenes = [
        Scene(kind="hook",      duration_s=3.0,  template="hook",      static_props={}),
        Scene(kind="reveal",    duration_s=6.0,  template="reveal",    static_props={}),
        Scene(kind="narrative", duration_s=6.0,  template="narrative", static_props={}),
        Scene(kind="cta",       duration_s=3.0,  template="cta",       static_props={}),
    ]
    return VideoSpec(
        id="bertha-2024",
        record=record,
        tier=tier,
        scenes=scenes,
        fps=30,
        seed=spec_seed("bertha-2024"),
    )


# ── Frame count assertions ────────────────────────────────────────────────────

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
    assert SCENE_ORDER == ["hook", "reveal", "narrative", "cta"]


# ── plan_frames produces exactly 540 frames for Bertha ───────────────────────

def test_plan_frames_total_count() -> None:
    spec = make_bertha_spec()
    frames = list(plan_frames(spec, fps=30))  # type: ignore[arg-type]
    assert len(frames) == 540


def test_plan_frames_scene_distribution() -> None:
    spec = make_bertha_spec()
    counts: dict[str, int] = {}
    for scene_kind, _idx, _tpl, _props in plan_frames(spec, fps=30):  # type: ignore[arg-type]
        counts[scene_kind] = counts.get(scene_kind, 0) + 1
    assert counts["hook"] == 90
    assert counts["reveal"] == 180
    assert counts["narrative"] == 180
    assert counts["cta"] == 90


# ── Props structure sanity checks ─────────────────────────────────────────────

def test_hook_props_have_required_keys() -> None:
    spec = make_bertha_spec()
    first_hook = next(
        props for sk, _i, _t, props in plan_frames(spec, fps=30)  # type: ignore[arg-type]
        if sk == "hook"
    )
    assert "name" in first_hook
    assert "tier" in first_hook
    assert "headline_chars_visible" in first_hook
    assert "subhead_alpha" in first_hook


def test_reveal_props_have_required_keys() -> None:
    spec = make_bertha_spec()
    first_reveal = next(
        props for sk, _i, _t, props in plan_frames(spec, fps=30)  # type: ignore[arg-type]
        if sk == "reveal"
    )
    assert "chart_draw_progress" in first_reveal
    assert "dot_visible" in first_reveal
    assert "count_value" in first_reveal
    assert "series" in first_reveal


def test_narrative_kb_scale_increases() -> None:
    spec = make_bertha_spec()
    narrative_frames = [
        props for sk, _i, _t, props in plan_frames(spec, fps=30)  # type: ignore[arg-type]
        if sk == "narrative"
    ]
    scales = [p["kb_scale"] for p in narrative_frames]
    # Ken Burns scale should be non-decreasing overall (ease_in_out_cubic is monotonic).
    assert scales[0] <= scales[-1]
    assert scales[0] >= 1.00
    assert scales[-1] <= 1.04 + 1e-6


def test_hook_type_on_monotonic() -> None:
    spec = make_bertha_spec()
    hook_frames = [
        props for sk, _i, _t, props in plan_frames(spec, fps=30)  # type: ignore[arg-type]
        if sk == "hook"
    ]
    chars = [p["headline_chars_visible"] for p in hook_frames]
    assert all(chars[i] <= chars[i + 1] for i in range(len(chars) - 1))


def test_reveal_chart_progress_monotonic() -> None:
    spec = make_bertha_spec()
    reveal_frames = [
        props for sk, _i, _t, props in plan_frames(spec, fps=30)  # type: ignore[arg-type]
        if sk == "reveal"
    ]
    progs = [p["chart_draw_progress"] for p in reveal_frames]
    assert all(progs[i] <= progs[i + 1] for i in range(len(progs) - 1))


def test_deterministic_narrative_seed() -> None:
    """Identical specs must produce identical Ken Burns values."""
    spec = make_bertha_spec()
    frames_a = list(plan_frames(spec, fps=30))  # type: ignore[arg-type]
    frames_b = list(plan_frames(spec, fps=30))  # type: ignore[arg-type]
    scales_a = [p["kb_scale"] for _, _, _, p in frames_a if _ == "narrative"]
    scales_b = [p["kb_scale"] for _, _, _, p in frames_b if _ == "narrative"]
    assert scales_a == scales_b
