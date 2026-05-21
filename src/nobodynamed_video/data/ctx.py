"""Build render-time editorial context from a NameRecord and supporting data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.data.hooks import pillar_to_program
from nobodynamed_video.data.sqlite_source import SqliteSource
from nobodynamed_video.models import (
    NameRecord,
    ProgramType,
    ResolvedCulturalEvent,
    ResolvedHook,
    Tier,
    VideoContext,
)

CULTURAL_EVENTS_PATH = Path("fixtures/cultural_events.yaml")
_GENERATION_LABELS = (
    (1901, 1927, "Greatest"),
    (1928, 1945, "Silent"),
    (1946, 1964, "Boomer"),
    (1965, 1980, "Gen X"),
    (1981, 1996, "Millennial"),
    (1997, 2012, "Gen Z"),
    (2013, 2030, "Gen Alpha"),
)


def _round_pct(value: float) -> int:
    return max(0, round(value))


def _compute_rise_pct(record: NameRecord) -> int:
    nonzero = [point for point in record.series if point.count > 0]
    if len(nonzero) < 2:
        return 0
    recent = nonzero[-min(6, len(nonzero)) :]
    base = recent[0].count
    end = recent[-1].count
    if base <= 0:
        return 0
    return _round_pct(((end - base) / base) * 100)


def _compute_decline_pct(record: NameRecord) -> int:
    if record.peak_count <= 0:
        return 0
    return _round_pct(((record.peak_count - record.current_count) / record.peak_count) * 100)


def _weighted_mean_year(record: NameRecord) -> float:
    total = sum(point.count for point in record.series if point.count > 0)
    if total <= 0:
        return float(record.current_year)
    weighted = sum(point.year * point.count for point in record.series if point.count > 0)
    return weighted / total


def _generation_for_year(year: int) -> str:
    for start, end, label in _GENERATION_LABELS:
        if start <= year <= end:
            return label
    return "Unknown"


def _find_trough(record: NameRecord) -> tuple[int, int]:
    nonzero = [point for point in record.series if point.count > 0]
    trough = min(nonzero, key=lambda point: (point.count, point.year))
    return trough.year, trough.count


def _find_last_top_year(rows: list[tuple[int, int]], threshold: int) -> int | None:
    eligible = [year for year, rank in rows if rank <= threshold]
    return max(eligible) if eligible else None


def _find_top10_years(rows: list[tuple[int, int]]) -> int:
    return sum(1 for _year, rank in rows if rank <= 10)


def _find_rise_year(record: NameRecord) -> int | None:
    for prev, current in zip(record.series, record.series[1:], strict=False):
        if prev.count <= 0:
            continue
        change = (current.count - prev.count) / prev.count
        if change > 0.30:
            return current.year
    return None


def _find_collapse_year(record: NameRecord) -> int | None:
    for prev, current in zip(record.series, record.series[1:], strict=False):
        if prev.count <= 0:
            continue
        change = (current.count - prev.count) / prev.count
        if change <= -0.30:
            return current.year
    return None


def load_cultural_events(
    path: Path = CULTURAL_EVENTS_PATH,
) -> dict[tuple[str, str], dict[str, Any]]:
    yaml = YAML(typ="safe")
    raw = yaml.load(path.read_text())
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in raw.get("events", []):
        key = (str(entry["name"]).lower(), str(entry["sex"]))
        result[key] = dict(entry)
    return result


def _resolve_event(
    events: dict[tuple[str, str], dict[str, Any]], record: NameRecord
) -> ResolvedCulturalEvent | None:
    raw = events.get((record.name.lower(), record.sex))
    if raw is None:
        return None
    killing_event = str(raw.get("killing_event", "")).strip()
    if not killing_event:
        return None
    return ResolvedCulturalEvent(
        name=record.name,
        sex=record.sex,
        killing_event=killing_event,
        event_year=int(raw["event_year"]),
        collapse_year=(
            int(raw["collapse_year"]) if raw.get("collapse_year") is not None else None
        ),
        moment_length=(
            int(raw["moment_length"]) if raw.get("moment_length") is not None else None
        ),
        confidence=str(raw.get("confidence", "unknown")),
    )


def build_narrative_text(
    program: ProgramType,
    tier: Tier,
    name: str,
    peak_year: int,
    current_count: int,
    event: ResolvedCulturalEvent | None,
    decline_pct: int,
    rise_pct: int,
) -> tuple[str, str | None]:
    if program == ProgramType.CULTURAL_EVENT and event is not None:
        primary = f"{name} was already moving. {event.killing_event} accelerated the decline."
        supporting = f"Down {decline_pct}% from its peak, with the break visible in the record."
        return primary, supporting
    if program == ProgramType.RETURN_NOTICE:
        primary = f"{name} fell almost out of circulation and then returned."
        supporting = f"Up {rise_pct}% over the last five years."
        return primary, supporting
    if tier == Tier.STABLE:
        primary = f"{name} never disappeared. It just stopped being dominant."
        supporting = f"Peak usage came in {peak_year}, but the name remained durable."
        return primary, supporting
    if tier == Tier.DECLINING:
        primary = f"{name} is no longer reproducing at anything like its former scale."
        supporting = f"It is down {decline_pct}% from peak."
        return primary, supporting
    if tier in (Tier.CRITICAL, Tier.EXTINCT):
        primary = f"{name} now survives mostly as inherited memory."
        supporting = f"Current births: {current_count}."
        return primary, supporting
    primary = f"{name} is back in circulation after a long period of dormancy."
    supporting = f"Peak year: {peak_year}."
    return primary, supporting


async def build_base_context(
    source: SqliteSource | D1Source,
    record: NameRecord,
    tier: Tier,
    current_year: int,
    events: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> VideoContext:
    peak_decade = record.peak_year // 10 * 10
    current_decade = current_year // 10 * 10
    trough_year, trough_count = _find_trough(record)
    avg_age = round(current_year - _weighted_mean_year(record))
    decline_pct = _compute_decline_pct(record)
    rise_pct = _compute_rise_pct(record)
    current_rank = await source.get_rank(record.name, record.sex, record.current_year)
    rank_at_peak = await source.get_rank(record.name, record.sex, record.peak_year)
    last_top_1000_year = await source.get_last_top_year(record.name, record.sex, 1000)
    last_top_10_year = await source.get_last_top_year(record.name, record.sex, 10)
    top10_years = await source.count_years_in_top(record.name, record.sex, 10)
    event = _resolve_event(events or load_cultural_events(), record)
    collapse_year = (
        event.collapse_year
        if event and event.collapse_year is not None
        else _find_collapse_year(record)
    )
    rise_year = _find_rise_year(record)
    moment_length = (
        event.moment_length
        if event and event.moment_length is not None
        else (
            collapse_year - rise_year
            if collapse_year is not None and rise_year is not None
            else None
        )
    )
    return VideoContext(
        name=record.name,
        sex=record.sex,
        first_letter=record.name[0].upper(),
        tier=tier,
        current_year=current_year,
        current_count=record.current_count,
        current_rank=current_rank,
        current_decade=current_decade,
        peak_year=record.peak_year,
        peak_count=record.peak_count,
        peak_decade=peak_decade,
        rank_at_peak=rank_at_peak,
        trough_year=trough_year,
        trough_count=trough_count,
        years_since_peak=current_year - record.peak_year,
        trough_to_now_years=current_year - trough_year,
        decline_pct=decline_pct,
        rise_pct=rise_pct,
        year_range=record.series[-1].year - record.series[0].year,
        start_year=record.series[0].year,
        avg_age=avg_age,
        generation_at_peak=_generation_for_year(record.peak_year),
        last_top_1000_year=last_top_1000_year,
        last_top_10_year=last_top_10_year,
        top10_years=top10_years,
        killing_event=event.killing_event if event else None,
        comparison_name=None,
        moment_length=moment_length,
        collapse_year=collapse_year,
        rise_year=rise_year,
        event_year=event.event_year if event else None,
        cultural_event=event,
    )


def finalize_video_context(base: VideoContext, hook: ResolvedHook) -> VideoContext:
    program = pillar_to_program(hook.pillar)
    narrative_text, supporting_text = build_narrative_text(
        program,
        base.tier,
        base.name,
        base.peak_year,
        base.current_count,
        base.cultural_event,
        base.decline_pct,
        base.rise_pct,
    )
    return base.model_copy(
        update={
            "program": program,
            "hook": hook,
            "narrative_text": narrative_text,
            "supporting_text": supporting_text,
        }
    )
