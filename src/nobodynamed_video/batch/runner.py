"""Async batch runner — renders a list of VideoSpecs with a concurrency limit."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from nobodynamed_video.compose.ffmpeg import build_ffmpeg_cmd, get_ffmpeg_version, run_ffmpeg
from nobodynamed_video.compose.manifest import build_manifest, write_manifest
from nobodynamed_video.config import get_settings
from nobodynamed_video.models import VideoSpec
from nobodynamed_video.render.frame_planner import plan_frames, total_frame_count
from nobodynamed_video.render.golden import check_or_write_golden, sha256_bytes
from nobodynamed_video.render.satori_client import SatoriClient

console = Console()

_BATCH_CONCURRENCY = 2  # ffmpeg encodes are CPU-heavy


async def render_spec(
    spec: VideoSpec,
    client: SatoriClient,
    out_dir: Path,
    no_compose: bool = False,
    debug_safe: bool = False,
    audio_path: Path | None = None,
) -> dict[str, object]:
    settings = get_settings()
    spec_out = out_dir / spec.id
    frames_dir = spec_out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    sha256_frames: dict[str, str] = {}
    scene_times: dict[str, float] = {}
    total_start = time.monotonic()

    # Render all frames.
    for scene_kind, frame_idx, template, props in plan_frames(spec, spec.fps, debug_safe):
        png_path = frames_dir / f"{scene_kind}_{frame_idx:03d}.png"

        # Check frame cache first.
        import hashlib
        cache_key = hashlib.sha256(
            (template + str(sorted(props.items()))).encode()
        ).hexdigest()
        cache_path = out_dir / ".cache" / f"{cache_key}.png"

        if cache_path.exists():
            png_bytes = cache_path.read_bytes()
        else:
            t_start = time.monotonic()
            png_bytes = await client.render(template, props)
            scene_times[scene_kind] = scene_times.get(scene_kind, 0.0) + (
                time.monotonic() - t_start
            )
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(png_bytes)

        png_path.write_bytes(png_bytes)
        fname = png_path.name
        sha256_frames[fname] = sha256_bytes(png_bytes)

    # Check first frame of each scene against golden hashes.
    for scene_kind in ["hook", "reveal"]:
        first_file = frames_dir / f"{scene_kind}_000.png"
        if first_file.exists():
            check_or_write_golden(spec.id, f"{scene_kind}_f00", first_file.read_bytes())

    if no_compose:
        return {"id": spec.id, "frames": len(sha256_frames), "composed": False}

    # Compose with ffmpeg.
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / f"{spec.id}.mp4"
    cmd = build_ffmpeg_cmd(
        frames_dir=frames_dir,
        out_path=mp4_path,
        fps=spec.fps,
        audio_path=audio_path,
    )
    run_ffmpeg(cmd)

    total_time = time.monotonic() - total_start
    satori_version = await client.get_version()
    ffmpeg_version = get_ffmpeg_version()

    manifest = build_manifest(
        spec_id=spec.id,
        frame_count=len(sha256_frames),
        duration_s=18.0,
        output_path=str(mp4_path),
        sha256_frames=sha256_frames,
        satori_version=satori_version,
        ffmpeg_version=ffmpeg_version,
        scene_render_times_s=scene_times,
        total_render_time_s=total_time,
    )
    write_manifest(manifest, out_dir)

    return {
        "id": spec.id,
        "frames": len(sha256_frames),
        "composed": True,
        "mp4": str(mp4_path),
        "duration_s": total_time,
    }


async def run_batch(
    specs: list[VideoSpec],
    satori_url: str,
    out_dir: Path,
    batch_name: str = "batch",
    no_compose: bool = False,
    debug_safe: bool = False,
    audio_path: Path | None = None,
) -> None:
    semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
    results: list[dict[str, object]] = []
    errors: list[tuple[str, Exception]] = []

    async with SatoriClient(satori_url) as client:

        async def _render_one(spec: VideoSpec) -> None:
            async with semaphore:
                try:
                    result = await render_spec(
                        spec, client, out_dir, no_compose, debug_safe, audio_path
                    )
                    results.append(result)
                    console.print(f"[green]✓[/green] {spec.id}")
                except Exception as exc:
                    errors.append((spec.id, exc))
                    console.print(f"[red]✗[/red] {spec.id}: {exc}")

        tasks = [asyncio.create_task(_render_one(s)) for s in specs]
        await asyncio.gather(*tasks)

    # Summary table.
    table = Table(title=f"Batch: {batch_name}")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Time (s)")
    for r in results:
        table.add_row(str(r["id"]), "ok", f"{r.get('duration_s', 0):.1f}")
    for spec_id, exc in errors:
        table.add_row(spec_id, f"[red]FAILED: {exc}[/red]", "—")
    console.print(table)

    # Batch summary JSON.
    summary = {
        "batch": batch_name,
        "total": len(specs),
        "succeeded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": [{"id": sid, "error": str(exc)} for sid, exc in errors],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{batch_name}.summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n"
    )

    if errors:
        raise SystemExit(f"{len(errors)} video(s) failed in batch '{batch_name}'")
