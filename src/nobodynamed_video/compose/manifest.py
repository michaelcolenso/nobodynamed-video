"""Writes RenderManifest JSON next to the output MP4."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from nobodynamed_video.models import RenderManifest, WordTiming


def write_manifest(manifest: RenderManifest, out_dir: Path) -> Path:
    """Serialise manifest to JSON at out_dir/<spec_id>.json."""
    path = out_dir / f"{manifest.spec_id}.json"
    path.write_text(manifest.model_dump_json(indent=2) + "\n")
    return path


def build_manifest(
    spec_id: str,
    frame_count: int,
    duration_s: float,
    output_path: str,
    sha256_frames: dict[str, str],
    satori_version: str,
    ffmpeg_version: str,
    scene_render_times_s: dict[str, float] | None = None,
    total_render_time_s: float = 0.0,
    program: str | None = None,
    hook_id: str | None = None,
    voice_register: str | None = None,
    caption: str | None = None,
    pinned_comment: str | None = None,
    hashtag_set: list[str] | None = None,
    story_kind: str | None = None,
    story_score: int | None = None,
    story_thesis: str | None = None,
    script: str | None = None,
    word_timings: list[WordTiming] | None = None,
    narration_provider: str | None = None,
    narration_model: str | None = None,
    narration_voice: str | None = None,
    narration_path: str | None = None,
    ai_voice_disclosure: str | None = None,
    loudness_target_lufs: float | None = None,
    true_peak_target_dbtp: float | None = None,
) -> RenderManifest:
    """Build a RenderManifest from render outputs."""
    return RenderManifest(
        spec_id=spec_id,
        rendered_at=datetime.now(tz=UTC),
        frame_count=frame_count,
        duration_s=duration_s,
        output_path=output_path,
        sha256_frames=sha256_frames,
        satori_version=satori_version,
        ffmpeg_version=ffmpeg_version,
        scene_render_times_s=scene_render_times_s or {},
        total_render_time_s=total_render_time_s,
        program=program,
        hook_id=hook_id,
        voice_register=voice_register,
        caption=caption,
        pinned_comment=pinned_comment,
        hashtag_set=hashtag_set or [],
        story_kind=story_kind,
        story_score=story_score,
        story_thesis=story_thesis,
        script=script,
        word_timings=word_timings or [],
        narration_provider=narration_provider,
        narration_model=narration_model,
        narration_voice=narration_voice,
        narration_path=narration_path,
        ai_voice_disclosure=ai_voice_disclosure,
        loudness_target_lufs=loudness_target_lufs,
        true_peak_target_dbtp=true_peak_target_dbtp,
    )
