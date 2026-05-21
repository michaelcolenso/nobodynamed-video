"""Writes RenderManifest JSON next to the output MP4."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from nobodynamed_video.models import RenderManifest


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
    )
