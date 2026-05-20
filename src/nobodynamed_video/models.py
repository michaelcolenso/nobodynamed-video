"""Pydantic models for the nobodynamed video pipeline."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, PositiveInt


class Tier(str, Enum):
    EXTINCT = "extinct"
    CRITICAL = "critical"
    DECLINING = "declining"
    STABLE = "stable"
    RISING = "rising"
    RESURRECTED = "resurrected"


class YearCount(BaseModel):
    year: int = Field(ge=1880, le=2100)
    count: int = Field(ge=0)


class NameRecord(BaseModel):
    name: str
    sex: str = Field(pattern=r"^[MF]$")
    series: list[YearCount]
    peak_year: int
    peak_count: PositiveInt
    current_year: int
    current_count: int


class Scene(BaseModel):
    kind: str
    duration_s: float
    template: str
    static_props: dict  # type: ignore[type-arg]


class VideoSpec(BaseModel):
    id: str
    record: NameRecord
    tier: Tier
    scenes: list[Scene]
    fps: int = 30
    seed: int


class RenderManifest(BaseModel):
    spec_id: str
    rendered_at: datetime
    frame_count: int
    duration_s: float
    output_path: str
    sha256_frames: dict[str, str]
    satori_version: str
    ffmpeg_version: str
    scene_render_times_s: dict[str, float] = Field(default_factory=dict)
    total_render_time_s: float = 0.0
