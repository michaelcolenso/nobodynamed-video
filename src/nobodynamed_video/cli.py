"""Typer CLI — nbn render / batch / preview / doctor / smoke."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from nobodynamed_video.batch.runner import run_batch
from nobodynamed_video.batch.spec import load_specs
from nobodynamed_video.config import get_settings
from nobodynamed_video.render.frame_planner import plan_frames
from nobodynamed_video.render.satori_client import SatoriClient

app = typer.Typer(name="nbn", help="nobodynamed video pipeline")
console = Console()


@app.command()
def render(
    spec: Path = typer.Option(..., help="Path to batch YAML spec"),
    no_compose: bool = typer.Option(False, help="Render frames only, skip ffmpeg"),
    debug_safe: bool = typer.Option(False, "--debug-safe", help="Overlay TikTok safe-area guides"),
    audio: Optional[Path] = typer.Option(None, help="Optional audio bed (.wav/.mp3/.aac)"),
    force: bool = typer.Option(False, help="Override blocklist"),
) -> None:
    """Render all videos defined in the YAML spec."""
    settings = get_settings()

    async def _run() -> None:
        specs = await load_specs(spec, force=force)
        await run_batch(
            specs=specs,
            satori_url=settings.satori_url,
            out_dir=settings.out_dir,
            batch_name=spec.stem,
            no_compose=no_compose,
            debug_safe=debug_safe,
            audio_path=audio,
        )

    asyncio.run(_run())


@app.command()
def batch(
    spec: Path = typer.Argument(..., help="Path to batch YAML spec"),
    force: bool = typer.Option(False, help="Override blocklist"),
    audio: Optional[Path] = typer.Option(None, help="Optional audio bed"),
) -> None:
    """Render a full batch from YAML."""
    settings = get_settings()

    async def _run() -> None:
        specs = await load_specs(spec, force=force)
        await run_batch(
            specs=specs,
            satori_url=settings.satori_url,
            out_dir=settings.out_dir,
            batch_name=spec.stem,
            audio_path=audio,
        )

    asyncio.run(_run())


@app.command()
def preview(
    spec_id: str = typer.Option(..., help="Spec ID, e.g. bertha-2024"),
    scene: str = typer.Option(..., help="Scene name: hook|reveal|narrative|cta"),
    frame: int = typer.Option(0, help="Frame index within the scene"),
    spec_file: Path = typer.Option(Path("batches/smoke.yaml"), "--spec", help="Batch YAML"),
) -> None:
    """Render a single frame and open it in the system viewer."""
    settings = get_settings()

    async def _run() -> None:
        specs = await load_specs(spec_file)
        matching = [s for s in specs if s.id == spec_id]
        if not matching:
            console.print(f"[red]No spec with id '{spec_id}' in {spec_file}[/red]")
            raise typer.Exit(1)
        target_spec = matching[0]

        # Find the requested frame.
        for sk, idx, tpl, props in plan_frames(target_spec, target_spec.fps):
            if sk == scene and idx == frame:
                async with SatoriClient(settings.satori_url) as client:
                    png = await client.render(tpl, props)
                out_path = settings.out_dir / target_spec.id / f"preview_{scene}_{frame:03d}.png"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(png)
                console.print(f"Saved: {out_path}")
                # Open in system viewer.
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.run([opener, str(out_path)], check=False)
                return

        console.print(f"[red]Frame {frame} not found in scene '{scene}'[/red]")
        raise typer.Exit(1)

    asyncio.run(_run())


@app.command()
def doctor() -> None:
    """Pre-flight check: Python, Node, ffmpeg, Satori, fonts, D1."""
    from scripts.doctor import run_doctor  # type: ignore[import]
    run_doctor()


@app.command()
def smoke() -> None:
    """Render the Bertha smoke test video."""
    typer.echo("Running smoke test: batches/smoke.yaml")
    ctx = typer.get_current_context()
    ctx.invoke(render, spec=Path("batches/smoke.yaml"))
