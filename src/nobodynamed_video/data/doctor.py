"""Data readiness checks shared by the CLI and publication gate."""

from __future__ import annotations

from dataclasses import dataclass, field

from nobodynamed_video.data.source import DataSource
from nobodynamed_video.models import DataMode, DataProvenance


@dataclass
class DataDoctorResult:
    passed: bool
    latest_year: int | None
    provenance: DataProvenance | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def inspect_data(source: DataSource, mode: DataMode) -> DataDoctorResult:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        year = await source.latest_year()
        provenance = await source.provenance()
    except Exception as exc:
        return DataDoctorResult(False, None, None, [f"Cannot inspect data source: {exc}"])

    if provenance.dataset_year != year:
        errors.append(
            f"Provenance year {provenance.dataset_year} does not match newest row year {year}"
        )
    if year < 1880:
        errors.append(f"Invalid latest dataset year: {year}")
    if provenance.synthetic:
        message = "Dataset is synthetic and is permitted only for tests/previews"
        if mode == DataMode.PUBLISH:
            errors.append(message)
        else:
            warnings.append(message)
    if mode == DataMode.PUBLISH:
        if not provenance.source_url:
            errors.append("Publish data must include a source URL")
        if not provenance.sha256 and provenance.source != "US Social Security Administration":
            errors.append("Publish data must include an archive checksum")

    return DataDoctorResult(not errors, year, provenance, errors, warnings)


async def require_publishable(source: DataSource, mode: DataMode) -> tuple[int, DataProvenance]:
    result = await inspect_data(source, mode)
    if not result.passed or result.latest_year is None or result.provenance is None:
        raise RuntimeError("Data publication gate failed: " + "; ".join(result.errors))
    return result.latest_year, result.provenance
