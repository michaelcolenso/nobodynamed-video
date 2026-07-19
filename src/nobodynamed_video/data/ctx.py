"""Build render-time editorial context from a NameRecord and supporting data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from nobodynamed_video.data.classifier import classify_dimensions
from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.data.hooks import pillar_to_program
from nobodynamed_video.data.narratives import select_narrative
from nobodynamed_video.data.sqlite_source import SqliteSource
from nobodynamed_video.models import (
    ClaimEvidence,
    DataMode,
    NameRecord,
    ObservationStatus,
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
    pct = _round_pct(((record.peak_count - record.current_count) / record.peak_count) * 100)
    # A name with surviving births is never a 100% decline (that reads as extinction);
    # rounding 99.8% → 100% would contradict the live count, so cap just below.
    if record.current_count > 0 and pct >= 100:
        pct = 99
    return pct


def _generation_for_year(year: int) -> str:
    for start, end, label in _GENERATION_LABELS:
        if start <= year <= end:
            return label
    return "Unknown"


def _find_trough(record: NameRecord) -> tuple[int, int]:
    # A comeback trough must occur at or after the historical peak. Using the
    # global minimum can put the "trough" before the rise being described.
    nonzero = [
        point
        for point in record.series
        if point.year >= record.peak_year
        and point.status == ObservationStatus.OBSERVED
        and point.count > 0
    ]
    if not nonzero:
        return record.peak_year, record.peak_count
    trough = min(nonzero, key=lambda point: (point.count, point.year))
    return trough.year, trough.count


def _count_in_year(record: NameRecord, year: int) -> int | None:
    for point in record.series:
        if point.year == year and point.status == ObservationStatus.OBSERVED:
            return point.count
    return None


def _event_decline_pct(record: NameRecord, event: ResolvedCulturalEvent | None) -> int | None:
    """How far below peak the name already was in the event year (0–100).

    Lets copy distinguish "was already fading when the event hit" (large value)
    from "was at its peak when the event hit" (near zero). None without an event.
    """
    if event is None or record.peak_count <= 0:
        return None
    count_at_event = _count_in_year(record, event.event_year)
    if count_at_event is None:
        return None
    return _round_pct(((record.peak_count - count_at_event) / record.peak_count) * 100)


def _find_last_top_year(rows: list[tuple[int, int]], threshold: int) -> int | None:
    eligible = [year for year, rank in rows if rank <= threshold]
    return max(eligible) if eligible else None


def _find_top10_years(rows: list[tuple[int, int]]) -> int:
    return sum(1 for _year, rank in rows if rank <= 10)


def _find_rise_year(record: NameRecord) -> int | None:
    for prev, current in zip(record.series, record.series[1:], strict=False):
        if (
            current.year - prev.year != 1
            or prev.status != ObservationStatus.OBSERVED
            or current.status != ObservationStatus.OBSERVED
            or prev.count <= 0
        ):
            continue
        change = (current.count - prev.count) / prev.count
        if change > 0.30:
            return current.year
    return None


def _find_collapse_year(record: NameRecord) -> int | None:
    for prev, current in zip(record.series, record.series[1:], strict=False):
        if (
            current.year - prev.year != 1
            or prev.status != ObservationStatus.OBSERVED
            or current.status != ObservationStatus.OBSERVED
            or prev.count <= 0
        ):
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
    allowed_confidence = {"high", "medium", "low"}
    for entry in raw.get("events", []):
        missing = [
            key
            for key in ("name", "sex", "killing_event", "event_year", "confidence", "evidence")
            if not entry.get(key)
        ]
        if missing:
            raise ValueError(f"Cultural event missing required fields {missing}: {entry!r}")
        if entry["confidence"] not in allowed_confidence:
            raise ValueError(f"Invalid cultural-event confidence: {entry['confidence']!r}")
        if len(str(entry["killing_event"])) > 30:
            raise ValueError(f"Cultural-event label exceeds 30 characters: {entry['name']}")
        key = (str(entry["name"]).lower(), str(entry["sex"]))
        if key in result:
            raise ValueError(f"Duplicate cultural event: {key}")
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
    confidence = str(raw.get("confidence", "unknown"))
    if confidence == "low":
        return None
    start = _count_in_year(record, int(raw["event_year"]))
    window = 5 if confidence == "high" else 10
    after = [
        point.count
        for point in record.series
        if int(raw["event_year"]) < point.year <= int(raw["event_year"]) + window
        and point.status == ObservationStatus.OBSERVED
    ]
    if start is None or not after or start <= 0:
        return None
    decline = _round_pct(((start - min(after)) / start) * 100)
    minimum = 30 if confidence == "high" else 15
    if decline < minimum:
        return None
    return ResolvedCulturalEvent(
        name=record.name,
        sex=record.sex,
        killing_event=killing_event,
        event_year=int(raw["event_year"]),
        collapse_year=(int(raw["collapse_year"]) if raw.get("collapse_year") is not None else None),
        moment_length=(int(raw["moment_length"]) if raw.get("moment_length") is not None else None),
        confidence=confidence,
        evidence=str(raw["evidence"]),
        validated=True,
        observed_decline_pct=decline,
    )


def _build_claims(
    record: NameRecord, tier: Tier, event: ResolvedCulturalEvent | None
) -> list[ClaimEvidence]:
    provenance = record.provenance
    source = provenance.source if provenance else "unknown"
    source_url = provenance.source_url if provenance else None
    claims = [
        ClaimEvidence(
            claim_id="historical-peak",
            text=(
                f"{record.name} peaked at {record.peak_count:,} recorded births "
                f"in {record.peak_year}."
            ),
            kind="ssa_observation",
            source=source,
            source_url=source_url,
            fields={"peak_year": record.peak_year, "peak_count": record.peak_count},
        )
    ]
    if record.current_status == ObservationStatus.OBSERVED:
        claims.append(
            ClaimEvidence(
                claim_id="current-count",
                text=(
                    f"SSA recorded {record.current_count:,} births named {record.name} "
                    f"in {record.current_year}."
                ),
                kind="ssa_observation",
                source=source,
                source_url=source_url,
                fields={"year": record.current_year, "count": record.current_count},
            )
        )
    else:
        claims.append(
            ClaimEvidence(
                claim_id="current-suppression",
                text=(
                    f"{record.name} has no published SSA row in {record.current_year}; "
                    "SSA suppresses counts below five."
                ),
                kind="suppression_limit",
                source=source,
                source_url=source_url,
                fields={"year": record.current_year, "status": record.current_status.value},
            )
        )
    claims.append(
        ClaimEvidence(
            claim_id="classification",
            text=f"The renderer's conservative legacy label is {tier.value}.",
            kind="derived",
            source="nobodynamed-video classifier",
            fields={"tier": tier.value},
        )
    )
    if event:
        claims.append(
            ClaimEvidence(
                claim_id="cultural-event",
                text=(
                    f"The curated event '{event.killing_event}' is associated with a "
                    f"{event.observed_decline_pct}% observed decline window."
                ),
                kind="curated_association",
                source="fixtures/cultural_events.yaml",
                fields={
                    "event_year": event.event_year,
                    "confidence": event.confidence,
                    "observed_decline_pct": event.observed_decline_pct,
                },
            )
        )
    return claims


async def build_base_context(
    source: SqliteSource | D1Source,
    record: NameRecord,
    tier: Tier,
    current_year: int,
    events: dict[tuple[str, str], dict[str, Any]] | None = None,
    data_mode: DataMode = DataMode.TEST,
) -> VideoContext:
    peak_decade = record.peak_year // 10 * 10
    current_decade = current_year // 10 * 10
    trough_year, trough_count = _find_trough(record)
    decline_pct = _compute_decline_pct(record)
    rise_pct = _compute_rise_pct(record)
    current_rank = (
        await source.get_rank(record.name, record.sex, record.current_year)
        if record.current_status == ObservationStatus.OBSERVED
        else 9999
    )
    rank_at_peak = await source.get_rank(record.name, record.sex, record.peak_year)
    last_top_1000_year = await source.get_last_top_year(record.name, record.sex, 1000)
    last_top_10_year = await source.get_last_top_year(record.name, record.sex, 10)
    top10_years = await source.count_years_in_top(record.name, record.sex, 10)
    comparison_name = await source.find_comparison_name(
        record.name,
        record.sex,
        record.peak_count,
        record.current_count,
        record.peak_year,
        current_year,
    )
    event = _resolve_event(events if events is not None else load_cultural_events(), record)
    classification = classify_dimensions(record)
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
        classification=classification,
        data_mode=data_mode,
        current_status=record.current_status,
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
        avg_age=None,
        generation_at_peak=_generation_for_year(record.peak_year),
        last_top_1000_year=last_top_1000_year,
        last_top_10_year=last_top_10_year,
        top10_years=top10_years,
        killing_event=event.killing_event if event else None,
        comparison_name=comparison_name,
        comparison_reason=(
            f"At {record.name}'s {record.peak_year} peak it had more recorded births than "
            f"{comparison_name}; in {current_year}, {comparison_name} had more."
            if comparison_name
            else None
        ),
        moment_length=moment_length,
        collapse_year=collapse_year,
        rise_year=rise_year,
        event_year=event.event_year if event else None,
        peak_to_event_years=(event.event_year - record.peak_year) if event else None,
        event_decline_pct=_event_decline_pct(record, event),
        claims=_build_claims(record, tier, event),
        cultural_event=event,
    )


def finalize_video_context(base: VideoContext, hook: ResolvedHook, seed: int = 0) -> VideoContext:
    program = pillar_to_program(hook.pillar)
    narrative_text, supporting_text = select_narrative(base, program, base.tier, seed)
    return base.model_copy(
        update={
            "program": program,
            "hook": hook,
            "narrative_text": narrative_text,
            "supporting_text": supporting_text,
        }
    )
