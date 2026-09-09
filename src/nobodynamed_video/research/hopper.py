"""Data-first candidate ranking for the NobodyNamed story hopper."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from nobodynamed_video.data.classifier import classify
from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.models import NameRecord


@dataclass(frozen=True)
class HopperCandidate:
    name: str
    sex: str
    hypothesis: str


@dataclass(frozen=True)
class HopperMetrics:
    name: str
    sex: str
    hypothesis: str
    latest_year: int
    latest_count: int
    first_reported_year: int
    peak_year: int
    peak_count: int
    peak_to_latest: float
    recent_change_5y: float
    recent_change_10y: float
    max_one_year_shock: float
    max_shock_year: int | None
    longest_internal_gap: int
    half_peak_width: int
    tier: str
    archetypes: list[str]
    curiosity_score: float


def load_candidates(path: Path) -> list[HopperCandidate]:
    yaml = YAML(typ="safe")
    raw = yaml.load(path.read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("candidates"), list):
        raise ValueError("hopper YAML must contain a candidates list")
    candidates: list[HopperCandidate] = []
    seen: set[tuple[str, str]] = set()
    for item in raw["candidates"]:
        if not isinstance(item, dict):
            raise ValueError("each hopper candidate must be a mapping")
        name = str(item.get("name", "")).strip()
        sex = str(item.get("sex", "")).strip().upper()
        hypothesis = str(item.get("hypothesis", "unspecified")).strip()
        if not name or sex not in {"M", "F"}:
            raise ValueError(f"invalid hopper candidate: {item!r}")
        key = (name.casefold(), sex)
        if key in seen:
            raise ValueError(f"duplicate hopper candidate: {name}/{sex}")
        seen.add(key)
        candidates.append(HopperCandidate(name=name, sex=sex, hypothesis=hypothesis))
    return candidates


def _count_years_ago(record: NameRecord, years: int) -> int:
    target = record.current_year - years
    point = next((yc for yc in record.series if yc.year == target), None)
    return point.count if point is not None else 0


def _fractional_change(current: int, previous: int) -> float:
    return (current - previous) / max(previous, 5)


def _longest_internal_gap(record: NameRecord) -> int:
    positive_years = [yc.year for yc in record.series if yc.count > 0]
    if len(positive_years) < 2:
        return 0
    return max(
        (right - left - 1 for left, right in zip(positive_years, positive_years[1:], strict=False)),
        default=0,
    )


def _max_one_year_shock(record: NameRecord) -> tuple[float, int | None]:
    best = 0.0
    best_year: int | None = None
    for previous, current in zip(record.series, record.series[1:], strict=False):
        if previous.count == 0 and current.count == 0:
            continue
        shock = abs(current.count - previous.count) / max(previous.count, 5)
        if shock > best:
            best = shock
            best_year = current.year
    return best, best_year


def _half_peak_width(record: NameRecord) -> int:
    threshold = record.peak_count / 2
    return sum(1 for yc in record.series if yc.count >= threshold)


def _archetypes(
    record: NameRecord,
    first_year: int,
    recent5: float,
    gap: int,
    half_peak_width: int,
    hypothesis: str,
) -> list[str]:
    tags: list[str] = []
    ratio = record.peak_count / max(record.current_count, 1)
    if first_year >= 1990:
        tags.append("modern-debut")
    elif first_year >= 1950:
        tags.append("late-debut")
    if ratio >= 10 and record.peak_count >= 500:
        tags.append("collapse")
    if recent5 >= 0.5:
        tags.append("recent-surge")
    elif recent5 <= -0.5:
        tags.append("recent-drop")
    if gap >= 10:
        tags.append("disappearance-gap")
    if half_peak_width <= 4:
        tags.append("narrow-spike")
    if hypothesis == "gender-shift":
        tags.append("gender-shift")
    return tags or ["long-curve"]


def score_record(candidate: HopperCandidate, record: NameRecord) -> HopperMetrics:
    positives = [yc for yc in record.series if yc.count > 0]
    if not positives:
        raise ValueError(f"{record.name}/{record.sex} has no positive SSA observations")

    first_year = positives[0].year
    count5 = _count_years_ago(record, 5)
    count10 = _count_years_ago(record, 10)
    recent5 = _fractional_change(record.current_count, count5)
    recent10 = _fractional_change(record.current_count, count10)
    shock, shock_year = _max_one_year_shock(record)
    gap = _longest_internal_gap(record)
    half_peak_width = _half_peak_width(record)
    peak_to_latest = record.peak_count / max(record.current_count, 1)

    collapse_points = min(
        25.0,
        max(
            0.0,
            math.log10((record.peak_count + 5) / (record.current_count + 5)) * 12.0,
        ),
    )
    recent_points = min(20.0, abs(recent5) * 8.0)
    shock_points = min(20.0, math.log10(1.0 + shock) * 8.0)
    gap_points = min(10.0, gap / 2.0)
    if first_year >= 1990:
        debut_points = 10.0
    elif first_year >= 1970:
        debut_points = 7.0
    elif first_year >= 1950:
        debut_points = 4.0
    else:
        debut_points = 0.0
    if half_peak_width <= 3:
        shape_points = 10.0
    elif half_peak_width <= 6:
        shape_points = 7.0
    elif half_peak_width <= 10:
        shape_points = 4.0
    else:
        shape_points = 0.0
    scale_points = min(
        5.0,
        max(0.0, math.log10(max(record.peak_count, 1)) / 4.0 * 5.0),
    )
    score = round(
        collapse_points
        + recent_points
        + shock_points
        + gap_points
        + debut_points
        + shape_points
        + scale_points,
        1,
    )
    return HopperMetrics(
        name=record.name,
        sex=record.sex,
        hypothesis=candidate.hypothesis,
        latest_year=record.current_year,
        latest_count=record.current_count,
        first_reported_year=first_year,
        peak_year=record.peak_year,
        peak_count=record.peak_count,
        peak_to_latest=round(peak_to_latest, 2),
        recent_change_5y=round(recent5, 3),
        recent_change_10y=round(recent10, 3),
        max_one_year_shock=round(shock, 3),
        max_shock_year=shock_year,
        longest_internal_gap=gap,
        half_peak_width=half_peak_width,
        tier=classify(record).value,
        archetypes=_archetypes(
            record,
            first_year,
            recent5,
            gap,
            half_peak_width,
            candidate.hypothesis,
        ),
        curiosity_score=score,
    )


async def analyze_candidates(
    candidates: list[HopperCandidate],
    source: D1Source,
    requested_year: int = 2025,
) -> tuple[int, list[HopperMetrics], list[dict[str, str]]]:
    latest_rows = await source.query_rows(
        "SELECT MAX(year) AS latest_year FROM name_years",
        [],
    )
    if not latest_rows or latest_rows[0].get("latest_year") is None:
        raise ValueError("D1 did not report a latest SSA year")
    available_year = int(str(latest_rows[0]["latest_year"]))
    reference_year = min(requested_year, available_year)

    results: list[HopperMetrics] = []
    errors: list[dict[str, str]] = []
    for candidate in candidates:
        try:
            record = await source.get_record(candidate.name, candidate.sex, reference_year)
            results.append(score_record(candidate, record))
        except Exception as exc:
            errors.append(
                {
                    "name": candidate.name,
                    "sex": candidate.sex,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    results.sort(key=lambda item: (-item.curiosity_score, item.name.casefold(), item.sex))
    return reference_year, results, errors


def _pct(value: float) -> str:
    return f"{value * 100:+.0f}%"


def render_markdown(
    reference_year: int,
    candidates: list[HopperCandidate],
    results: list[HopperMetrics],
    errors: list[dict[str, str]],
) -> str:
    header = (
        "| # | Name | Sex | Score | Tier | First | Peak | Latest | Peak/latest | "
        "5y | Shock | Gap | Signals | Hypothesis |"
    )
    lines = [
        "# NobodyNamed Hopper Analysis",
        "",
        f"SSA reference year: **{reference_year}**",
        f"Candidate series requested: **{len(candidates)}**",
        f"Series scored: **{len(results)}**",
        f"Series with retrieval errors: **{len(errors)}**",
        "",
        "The curiosity score is a discovery heuristic, not an editorial approval score. "
        "It rewards collapse, recent movement, abrupt annual shocks, disappearance gaps, "
        "late debuts, narrow peaks, and enough scale to make the curve legible.",
        "",
        "## Ranked candidates",
        "",
        header,
        "|---:|---|:---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for index, item in enumerate(results, start=1):
        shock = f"{item.max_one_year_shock:.1f}x"
        if item.max_shock_year is not None:
            shock += f" ({item.max_shock_year})"
        lines.append(
            f"| {index} | {item.name} | {item.sex} | {item.curiosity_score:.1f} | "
            f"{item.tier} | {item.first_reported_year} | "
            f"{item.peak_count:,} ({item.peak_year}) | {item.latest_count:,} | "
            f"{item.peak_to_latest:.1f}x | {_pct(item.recent_change_5y)} | {shock} | "
            f"{item.longest_internal_gap}y | {', '.join(item.archetypes)} | "
            f"{item.hypothesis} |"
        )

    paired: dict[str, list[HopperMetrics]] = defaultdict(list)
    for item in results:
        paired[item.name.casefold()].append(item)
    gender_pairs = [items for items in paired.values() if len({item.sex for item in items}) == 2]
    if gender_pairs:
        lines.extend(["", "## Paired-sex candidates", ""])
        for items in sorted(gender_pairs, key=lambda pair: pair[0].name.casefold()):
            by_sex = {item.sex: item for item in items}
            male = by_sex["M"]
            female = by_sex["F"]
            total = male.latest_count + female.latest_count
            female_share = female.latest_count / total if total else 0.0
            lines.append(
                f"- **{female.name}:** {reference_year} reported counts "
                f"M {male.latest_count:,} / F {female.latest_count:,}; "
                f"female share {female_share:.0%}. "
                f"Peak years M {male.peak_year}, F {female.peak_year}."
            )

    if errors:
        lines.extend(["", "## Retrieval errors", ""])
        for error in errors:
            lines.append(f"- {error['name']}/{error['sex']}: {error['error']}")
    lines.append("")
    return "\n".join(lines)


def write_report(
    output_dir: Path,
    reference_year: int,
    candidates: list[HopperCandidate],
    results: list[HopperMetrics],
    errors: list[dict[str, str]],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hopper-ranked.json"
    markdown_path = output_dir / "hopper-ranked.md"
    payload: dict[str, Any] = {
        "reference_year": reference_year,
        "candidate_series": len(candidates),
        "scored": len(results),
        "errors": errors,
        "results": [asdict(item) for item in results],
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    markdown_path.write_text(render_markdown(reference_year, candidates, results, errors))
    return json_path, markdown_path
