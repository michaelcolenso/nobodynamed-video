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
    debug_safe: bool = typer.Option(False, help="Overlay TikTok safe-area guides"),
    audio: Optional[Path] = typer.Option(None, help="Optional audio bed (.wav/.mp3/.aac)"),
    force: bool = typer.Option(False, help="Override blocklist"),
    update_goldens: bool = typer.Option(False, hidden=True),
    burn_captions: bool = typer.Option(False, help="Burn approved copy into the MP4"),
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
            release_dir=settings.release_dir,
            update_goldens=update_goldens,
            burn_captions=burn_captions,
        )

    asyncio.run(_run())


@app.command()
def batch(
    spec: Path = typer.Argument(..., help="Path to batch YAML spec"),
    force: bool = typer.Option(False, help="Override blocklist"),
    audio: Optional[Path] = typer.Option(None, help="Optional audio bed"),
    burn_captions: bool = typer.Option(False, help="Burn approved copy into the MP4"),
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
            release_dir=settings.release_dir,
            burn_captions=burn_captions,
        )

    asyncio.run(_run())


@app.command()
def preview(
    spec_id: str = typer.Option(..., help="Spec ID, e.g. bertha-2024"),
    scene: str = typer.Option(..., help="Scene name: hook|reveal|narrative|cta"),
    frame: int = typer.Option(0, help="Frame index within the scene"),
    spec_file: Path = typer.Option(Path("batches/smoke.yaml"), help="Batch YAML spec file"),
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
    import importlib.util
    from pathlib import Path

    # The nbn entry point sets sys.path[0] to .venv/bin, not the project
    # root.  Load doctor.py from the repo root (relative to this file).
    repo_root = Path(__file__).resolve().parent.parent.parent
    doctor_path = repo_root / "scripts" / "doctor.py"
    spec = importlib.util.spec_from_file_location("doctor", doctor_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    run_doctor = mod.run_doctor
    run_doctor()


@app.command()
def smoke() -> None:
    """Render the Bertha smoke test video."""
    typer.echo("Running smoke test: batches/smoke.yaml")
    render(
        spec=Path("batches/smoke.yaml"),
        no_compose=False,
        debug_safe=False,
        audio=None,
        force=False,
        update_goldens=False,
        burn_captions=False,
    )


data_app = typer.Typer(name="data", help="Import and validate SSA data.")
app.add_typer(data_app)


@data_app.command("doctor")
def data_doctor() -> None:
    """Validate source provenance and readiness for the active data mode."""
    from nobodynamed_video.data.d1_source import D1Source
    from nobodynamed_video.data.doctor import inspect_data
    from nobodynamed_video.data.sqlite_source import SqliteSource

    settings = get_settings()

    async def _run() -> None:
        source: SqliteSource | D1Source
        if settings.use_sqlite:
            source = SqliteSource(settings.sqlite_fixture)
        else:
            source = D1Source(settings.d1_url, settings.get_d1_token())
        result = await inspect_data(source, settings.data_mode)
        console.print(f"Mode: {settings.data_mode.value}")
        console.print(f"Latest dataset year: {result.latest_year or 'unknown'}")
        if result.provenance:
            console.print(f"Source: {result.provenance.source}")
            console.print(f"Synthetic: {result.provenance.synthetic}")
        for warning in result.warnings:
            console.print(f"[yellow]WARNING[/yellow] {warning}")
        for error in result.errors:
            console.print(f"[red]ERROR[/red] {error}")
        if not result.passed:
            raise typer.Exit(1)

    asyncio.run(_run())


goldens_app = typer.Typer(name="goldens", help="Review and explicitly update golden frames.")
app.add_typer(goldens_app)


@goldens_app.command("update")
def goldens_update(
    spec: Path = typer.Option(Path("batches/smoke.yaml"), help="Reviewed spec to render"),
) -> None:
    """Render and replace goldens; never called by CI."""
    render(
        spec=spec,
        no_compose=False,
        debug_safe=False,
        audio=None,
        force=False,
        update_goldens=True,
        burn_captions=False,
    )


ops_app = typer.Typer(name="ops", help="Publishing ledger, queue, and analytics.")
app.add_typer(ops_app)


def _ledger() -> object:
    from nobodynamed_video.operations.ledger import PublishingLedger

    return PublishingLedger(Path("state/publishing.db"))


@ops_app.command("record-publish")
def record_publish(
    spec_id: str,
    platform: str,
    external_id: str,
    video_format: str = "fast",
    url: Optional[str] = None,
    hook_id: Optional[str] = None,
    experiment: Optional[str] = None,
) -> None:
    """Record a completed manual or API publication."""
    from nobodynamed_video.operations.ledger import PublishingLedger

    ledger = _ledger()
    assert isinstance(ledger, PublishingLedger)
    ledger.record_publication(
        spec_id, platform, external_id, url, video_format, hook_id, experiment
    )
    console.print(f"[green]Recorded[/green] {platform}/{external_id}")


@ops_app.command("import-metrics")
def import_metrics(path: Path) -> None:
    """Import a portable CSV export of post-performance metrics."""
    from nobodynamed_video.operations.ledger import PublishingLedger

    ledger = _ledger()
    assert isinstance(ledger, PublishingLedger)
    count = ledger.import_metrics_csv(path)
    console.print(f"[green]Imported[/green] {count} metric row(s)")


@ops_app.command("enqueue")
def enqueue(
    name: str,
    sex: str,
    video_format: str = "fast",
    hook_style: Optional[str] = None,
    experiment: Optional[str] = None,
    source: str = "manual",
) -> None:
    """Add an item to the source-agnostic content queue."""
    from nobodynamed_video.operations.ledger import PublishingLedger

    ledger = _ledger()
    assert isinstance(ledger, PublishingLedger)
    queue_id = ledger.enqueue(name, sex, video_format, hook_style, experiment, source)
    console.print(f"[green]Queued[/green] item {queue_id}: {name}/{sex}")


captions_app = typer.Typer(name="captions", help="Manage caption combination state.")
app.add_typer(captions_app)


@captions_app.command("stats")
def captions_stats() -> None:
    """Print used vs available combination counts."""
    from nobodynamed_video.compose.state import CombinationState

    state = CombinationState(Path("state/used_combinations.db"))
    s = state.stats()
    console.print(f"Combinations recorded: {s['combos']}")
    console.print(f"Total uses:            {s['uses']}")


@captions_app.command("deprecate")
def captions_deprecate(
    tag: str = typer.Argument(..., help="Hashtag to mark inactive in captions.yaml"),
) -> None:
    """Mark a hashtag as inactive so it won't be selected for new captions."""
    from ruamel.yaml import YAML

    path = Path("fixtures/captions.yaml")
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(path.read_text())
    changed = 0
    for _category, entries in data.get("hashtags", {}).items():
        for entry in entries:
            if entry.get("tag") == tag and entry.get("active", True):
                entry["active"] = False
                changed += 1
    if changed:
        with path.open("w") as fh:
            yaml.dump(data, fh)
        console.print(f"[green]Deprecated:[/green] #{tag}")
    else:
        console.print(f"[yellow]Not found or already inactive:[/yellow] #{tag}")


@captions_app.command("reset")
def captions_reset(
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually wipe state."),
) -> None:
    """Wipe all recorded hashtag combinations from state DB."""
    from nobodynamed_video.compose.state import CombinationState

    if not confirm:
        console.print("[red]Pass --confirm to wipe the state DB.[/red]")
        raise typer.Exit(1)
    state = CombinationState(Path("state/used_combinations.db"))
    state.reset()
    console.print("[green]State DB wiped.[/green]")
