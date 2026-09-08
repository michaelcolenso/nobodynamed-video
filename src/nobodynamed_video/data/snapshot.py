"""Pinned SSA observations for releases; synthetic fixtures are never a release source."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from nobodynamed_video.data.records import build_name_record
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.models import NameRecord, StorySpec


class Observation(BaseModel):
    year: int = Field(ge=1880, le=2100)
    count: int | None = Field(default=None, ge=5)
    rank: int | None = Field(default=None, ge=1)


class Snapshot(BaseModel):
    schema_version: Literal[1] = 1
    source_url: Literal["https://www.ssa.gov/oact/babynames/names.zip"]
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at: datetime
    name: str
    sex: Literal["M", "F"]
    latest_year: int = Field(ge=1880, le=2100)
    observations: list[Observation]

    @model_validator(mode="after")
    def complete_series(self) -> Snapshot:
        if [p.year for p in self.observations] != list(range(1880, self.latest_year + 1)):
            raise ValueError("snapshot must cover every year once, from 1880 to latest_year")
        if any((p.count is None) != (p.rank is None) for p in self.observations):
            raise ValueError("reported counts and ranks must both be present or absent")
        if not any(p.count is not None for p in self.observations):
            raise ValueError("snapshot has no reported counts")
        return self


def verified_snapshot(story: StorySpec) -> Snapshot:
    if not story.data_snapshot or not story.data_sha256:
        raise StoryQualityError("release story requires a pinned SSA data snapshot and SHA256")
    try:
        data = Path(story.data_snapshot).read_bytes()
        if hashlib.sha256(data).hexdigest() != story.data_sha256:
            raise ValueError("snapshot SHA256 mismatch")
        snapshot = Snapshot.model_validate_json(data)
        if (snapshot.name, snapshot.sex) != (story.name, story.sex):
            raise ValueError("snapshot name/sex differs from story")
        if not story.count_claims:
            raise ValueError("story must declare its annual count claims")
        observed = {p.year: p.count for p in snapshot.observations}
        for claim in story.count_claims:
            if claim.year not in observed or observed[claim.year] != claim.count:
                raise ValueError(f"count claim for {claim.year} disagrees with SSA snapshot")
        return snapshot
    except (OSError, ValueError) as exc:
        raise StoryQualityError(f"{story.id}: {exc}") from exc


class SnapshotSource:
    """Ranks were computed against ALL national rows, not just the selected names."""

    def __init__(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot

    async def get_record(self, name: str, sex: str, year: int) -> NameRecord:
        if (name, sex, year) != (self.snapshot.name, self.snapshot.sex, self.snapshot.latest_year):
            raise StoryQualityError("record request does not match pinned snapshot")
        return build_name_record(
            name,
            sex,
            year,
            ((p.year, p.count) for p in self.snapshot.observations if p.count is not None),
        )

    async def get_rank(self, name: str, sex: str, year: int) -> int:
        return next((p.rank or 9999 for p in self.snapshot.observations if p.year == year), 9999)

    async def get_last_top_year(self, name: str, sex: str, threshold: int) -> int | None:
        return max(
            (
                p.year
                for p in self.snapshot.observations
                if p.rank is not None and p.rank <= threshold
            ),
            default=None,
        )

    async def count_years_in_top(self, name: str, sex: str, threshold: int) -> int:
        return sum(p.rank is not None and p.rank <= threshold for p in self.snapshot.observations)

    async def find_comparison_name(
        self,
        name: str,
        sex: str,
        peak_count: int,
        current_count: int,
        peak_year: int,
        latest_year: int,
    ) -> str | None:
        # No arbitrary reference name from an incomplete subset of the national data.
        return None
