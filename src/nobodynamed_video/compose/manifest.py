"""Writes RenderManifest JSON next to the output MP4."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
) -> RenderManifest:
    return RenderManifest(
        spec_id=spec_id,
        rendered_at=datetime.now(tz=timezone.utc),
        frame_count=frame_count,
        duration_s=duration_s,
        output_path=output_path,
        sha256_frames=sha256_frames,
        satori_version=satori_version,
        ffmpeg_version=ffmpeg_version,
        scene_render_times_s=scene_render_times_s or {},
        total_render_time_s=total_render_time_s,
    )
