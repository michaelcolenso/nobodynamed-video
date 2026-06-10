"""Async batch runner — renders a list of VideoSpecs with a concurrency limit."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from nobodynamed_video.compose.caption import CaptionExhausted, compose_caption
from nobodynamed_video.compose.ffmpeg import build_ffmpeg_cmd, get_ffmpeg_version, run_ffmpeg
from nobodynamed_video.compose.lexicon import Lexicon
from nobodynamed_video.compose.manifest import build_manifest, write_manifest
from nobodynamed_video.compose.state import CombinationState
from nobodynamed_video.models import VideoSpec
from nobodynamed_video.qc.checks import run_all_checks
from nobodynamed_video.qc.report import build_qc_report
from nobodynamed_video.render.frame_planner import plan_frames
from nobodynamed_video.render.golden import check_or_write_golden, sha256_bytes
from nobodynamed_video.render.programs import TOTAL_DURATION_S
from nobodynamed_video.render.satori_client import SatoriClient

console = Console()

_BATCH_CONCURRENCY = 2
_CAPTIONS_YAML = Path("fixtures/captions.yaml")
_STATE_DB = Path("state/used_combinations.db")
_RENDERER_SRC_DIR = Path("satori-service/src")


@lru_cache(maxsize=1)
def _renderer_digest() -> str:
    """Digest of the Satori renderer sources.

    Mixed into the frame cache key so template/renderer edits invalidate
    cached frames — keying on template *name* + props alone silently serves
    stale frames after a .tsx change.
    """
    digest = hashlib.sha256()
    if _RENDERER_SRC_DIR.exists():
        for path in sorted(_RENDERER_SRC_DIR.rglob("*.ts*")):
            digest.update(path.as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


async def render_spec(
    spec: VideoSpec,
    client: SatoriClient,
    out_dir: Path,
    lexicon: Lexicon,
    state: CombinationState,
    no_compose: bool = False,
    debug_safe: bool = False,
    audio_path: Path | None = None,
) -> dict[str, object]:
    """Render one VideoSpec: frames → caption → ffmpeg → manifest."""
    spec_out = out_dir / spec.id
    frames_dir = spec_out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    sha256_frames: dict[str, str] = {}
    scene_times: dict[str, float] = {}
    total_start = time.monotonic()

    for scene_kind, frame_idx, template, props in plan_frames(spec, spec.fps, debug_safe):
        png_path = frames_dir / f"{scene_kind}_{frame_idx:03d}.png"

        cache_key = hashlib.sha256(
            (_renderer_digest() + template + str(sorted(props.items()))).encode()
        ).hexdigest()
        cache_path = out_dir / ".cache" / f"{cache_key}.png"

        if cache_path.exists():
            png_bytes = cache_path.read_bytes()
        else:
            t_start = time.monotonic()
            png_bytes = await client.render(template, props)
            elapsed = time.monotonic() - t_start
            scene_times[scene_kind] = scene_times.get(scene_kind, 0.0) + elapsed
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(png_bytes)

        png_path.write_bytes(png_bytes)
        sha256_frames[png_path.name] = sha256_bytes(png_bytes)

    for scene_kind in ["hook", "reveal"]:
        first_file = frames_dir / f"{scene_kind}_000.png"
        if first_file.exists():
            check_or_write_golden(spec.id, f"{scene_kind}_f00", first_file.read_bytes())

    if no_compose:
        return {"id": spec.id, "frames": len(sha256_frames), "composed": False}

    caption: str | None = None
    pinned_comment: str | None = None
    hashtag_set: list[str] = []
    if spec.hook and spec.context:
        try:
            composed = compose_caption(spec.id, spec.hook, spec.context, lexicon, state)
            caption = composed.caption
            pinned_comment = composed.pinned_comment
            hashtag_set = composed.hashtag_set
        except CaptionExhausted as exc:
            console.print(f"[yellow]⚠[/yellow]  {spec.id}: caption exhausted — {exc}")

    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / f"{spec.id}.mp4"
    cmd = build_ffmpeg_cmd(
        frames_dir=frames_dir,
        out_path=mp4_path,
        fps=spec.fps,
        audio_path=audio_path,
    )
    # ffmpeg encodes can run 10-60s; a blocking subprocess.run here freezes the
    # event loop, starving the sibling render's in-flight HTTP awaits past their
    # read timeout (the CI failure mode: every odd spec died with an empty
    # ReadTimeout the instant its partner's encode finished).
    await asyncio.to_thread(run_ffmpeg, cmd)

    total_time = time.monotonic() - total_start
    satori_version = await client.get_version()
    ffmpeg_version = get_ffmpeg_version()

    manifest = build_manifest(
        spec_id=spec.id,
        frame_count=len(sha256_frames),
        duration_s=TOTAL_DURATION_S,
        output_path=str(mp4_path),
        sha256_frames=sha256_frames,
        satori_version=satori_version,
        ffmpeg_version=ffmpeg_version,
        scene_render_times_s=scene_times,
        total_render_time_s=total_time,
        program=spec.program.value if spec.program else None,
        hook_id=spec.hook.id if spec.hook else None,
        voice_register=spec.hook.voice_register if spec.hook else None,
        caption=caption,
        pinned_comment=pinned_comment,
        hashtag_set=hashtag_set,
    )
    write_manifest(manifest, out_dir)

    return {
        "id": spec.id,
        "frames": len(sha256_frames),
        "composed": True,
        "mp4": str(mp4_path),
        "duration_s": TOTAL_DURATION_S,
        "render_time_s": total_time,
        "caption": caption,
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
    """Run all specs concurrently, write summary JSON."""
    lexicon = Lexicon.from_yaml(_CAPTIONS_YAML)
    state = CombinationState(_STATE_DB)

    semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
    results: list[dict[str, object]] = []
    errors: list[tuple[str, Exception]] = []

    async with SatoriClient(satori_url) as client:

        async def _render_one(spec: VideoSpec) -> None:
            async with semaphore:
                try:
                    result = await render_spec(
                        spec,
                        client,
                        out_dir,
                        lexicon,
                        state,
                        no_compose,
                        debug_safe,
                        audio_path,
                    )
                    results.append(result)
                    console.print(f"[green]✓[/green] {spec.id}")
                except Exception as exc:
                    errors.append((spec.id, exc))
                    detail = escape(f"{type(exc).__name__}: {exc}")
                    console.print(f"[red]✗[/red] {spec.id}: {detail}")

        tasks = [asyncio.create_task(_render_one(s)) for s in specs]
        await asyncio.gather(*tasks)

    table = Table(title=f"Batch: {batch_name}")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Time (s)")
    for r in results:
        table.add_row(str(r["id"]), "ok", f"{r.get('render_time_s', 0):.1f}")
    for spec_id, exc in errors:
        detail = escape(f"{type(exc).__name__}: {exc}")
        table.add_row(spec_id, f"[red]FAILED: {detail}[/red]", "—")
    console.print(table)

    qc_results = []
    for r in results:
        if r.get("composed"):
            qc = run_all_checks(r, out_dir)
            qc_results.append(qc)
            qc_issues: list[dict[str, str]] = []
            for issue in qc.issues:
                sev, code, msg = issue.severity, issue.code, issue.message
                qc_issues.append({"severity": sev, "code": code, "message": msg})
            r["qc"] = {"passed": qc.passed, "issues": qc_issues}

    if qc_results:
        report_path = build_qc_report(batch_name, qc_results, out_dir)
        console.print(f"[cyan]QC report:[/cyan] {report_path}")

    summary = {
        "batch": batch_name,
        "total": len(specs),
        "succeeded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": [{"id": sid, "error": f"{type(exc).__name__}: {exc}"} for sid, exc in errors],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_json = json.dumps(summary, indent=2, default=str) + "\n"
    (out_dir / f"{batch_name}.summary.json").write_text(summary_json)

    if errors:
        raise SystemExit(f"{len(errors)} video(s) failed in batch '{batch_name}'")
