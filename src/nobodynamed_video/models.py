"""Pydantic models for the nobodynamed video pipeline."""

from datetime import datetime
from enum import Enum
from typing import Any

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


class ProgramType(str, Enum):
    CASE_FILE = "case_file"
    RETURN_NOTICE = "return_notice"
    CULTURAL_EVENT = "cultural_event"


class ResolvedCulturalEvent(BaseModel):
    name: str
    sex: str
    killing_event: str
    event_year: int
    collapse_year: int | None = None
    moment_length: int | None = None
    confidence: str = "unknown"


class ResolvedHook(BaseModel):
    id: str
    pillar: str
    voice_register: str
    headline: str
    subhead: str
    pinned_comment: str
    caption: str
    requires_var: str | None = None


class VideoContext(BaseModel):
    name: str
    sex: str
    first_letter: str
    tier: Tier
    current_year: int
    current_count: int
    current_rank: int
    current_decade: int
    peak_year: int
    peak_count: int
    peak_decade: int
    rank_at_peak: int
    trough_year: int
    trough_count: int
    years_since_peak: int
    trough_to_now_years: int
    decline_pct: int
    rise_pct: int
    year_range: int
    start_year: int
    avg_age: int
    generation_at_peak: str
    last_top_1000_year: int | None = None
    last_top_10_year: int | None = None
    top10_years: int = 0
    killing_event: str | None = None
    comparison_name: str | None = None
    moment_length: int | None = None
    collapse_year: int | None = None
    rise_year: int | None = None
    event_year: int | None = None
    peak_to_event_years: int | None = None
    event_decline_pct: int | None = None
    program: ProgramType | None = None
    hook: ResolvedHook | None = None
    narrative_text: str = ""
    supporting_text: str | None = None
    cultural_event: ResolvedCulturalEvent | None = None

    def as_template_context(self) -> dict[str, Any]:
        return self.model_dump()


class VideoSpec(BaseModel):
    id: str
    record: NameRecord
    tier: Tier
    scenes: list[Scene]
    fps: int = 30
    seed: int
    program: ProgramType = ProgramType.CASE_FILE
    hook: ResolvedHook | None = None
    context: VideoContext | None = None


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
    program: str | None = None
    hook_id: str | None = None
    voice_register: str | None = None
    caption: str | None = None
    pinned_comment: str | None = None
    hashtag_set: list[str] = Field(default_factory=list)
