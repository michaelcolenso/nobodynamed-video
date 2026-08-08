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


class StoryKind(str, Enum):
    """Editorial shapes that receive distinct pacing and visual treatment."""

    ONE_HIT = "one_hit"
    CULTURAL_RUPTURE = "cultural_rupture"
    LONG_DECLINE = "long_decline"
    COMEBACK = "comeback"


class StoryStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class EvidenceKind(str, Enum):
    SSA = "ssa"
    PRIMARY = "primary"
    REPORTING = "reporting"
    ACADEMIC = "academic"


class ScriptBeatKind(str, Enum):
    HOOK = "hook"
    REVEAL = "reveal"
    PROOF = "proof"
    TURN = "turn"
    LOOP = "loop"


class EvidenceSource(BaseModel):
    label: str = Field(min_length=3, max_length=100)
    url: str = Field(min_length=8, max_length=500)
    kind: EvidenceKind
    supports: str = Field(min_length=8, max_length=240)


class ScriptBeat(BaseModel):
    kind: ScriptBeatKind
    text: str = Field(min_length=2, max_length=180)


class StorySpec(BaseModel):
    """A reviewed editorial premise, not merely a render configuration."""

    id: str
    name: str
    sex: str = Field(pattern=r"^[MF]$")
    story_kind: StoryKind
    thesis: str = Field(min_length=12, max_length=180)
    headline: str = Field(min_length=4, max_length=60)
    subhead: str = Field(min_length=4, max_length=70)
    takeaway: str = Field(min_length=8, max_length=80)
    support: str = Field(min_length=4, max_length=70)
    script_beats: list[ScriptBeat] = Field(min_length=3, max_length=6)
    evidence: list[EvidenceSource] = Field(min_length=1)
    visual_anchors: list[str] = Field(min_length=2, max_length=5)
    social_caption: str = Field(min_length=8, max_length=130)
    hashtags: list[str] = Field(min_length=2, max_length=4)
    share_prompt: str = Field(min_length=8, max_length=100)
    target_duration_s: float = Field(default=11.0, ge=9.0, le=14.0)
    voice: str | None = Field(default=None, min_length=2, max_length=80)
    voice_instructions: str = Field(min_length=12, max_length=300)
    status: StoryStatus = StoryStatus.DRAFT
    quality_score: int = Field(default=0, ge=0, le=100)
    approved_by: str | None = None
    approved_at: datetime | None = None

    @property
    def narration_text(self) -> str:
        return " ".join(beat.text.strip() for beat in self.script_beats)

    @property
    def narration_word_count(self) -> int:
        return len(self.narration_text.split())


class WordTiming(BaseModel):
    word: str
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)


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
    story: StorySpec | None = None
    duration_s: float = Field(default=11.0, ge=9.0, le=14.0)
    word_timings: list[WordTiming] = Field(default_factory=list)


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
    story_kind: str | None = None
    story_score: int | None = None
    story_thesis: str | None = None
    script: str | None = None
    word_timings: list[WordTiming] = Field(default_factory=list)
    narration_provider: str | None = None
    narration_model: str | None = None
    narration_voice: str | None = None
    narration_path: str | None = None
    ai_voice_disclosure: str | None = None
    loudness_target_lufs: float | None = None
    true_peak_target_dbtp: float | None = None
