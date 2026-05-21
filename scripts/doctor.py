"""Pre-flight doctor — verifies all required dependencies and services."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


def _check(label: str, ok: bool, fix: str) -> bool:
    if ok:
        console.print(f"[green]✓[/green]  {label}")
    else:
        console.print(f"[red]✗[/red]  {label}")
        console.print(f"    [dim]Fix: {fix}[/dim]")
    return ok


def check_python() -> bool:
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 12
    return _check(
        f"Python >= 3.12  (found {v.major}.{v.minor}.{v.micro})",
        ok,
        "Install Python 3.12+ via pyenv or your system package manager",
    )


def check_node() -> bool:
    try:
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        version = result.stdout.strip()
        major = int(version.lstrip("v").split(".")[0])
        ok = major >= 20
        return _check(
            f"Node >= 20  (found {version})",
            ok,
            "Install Node 20+ via nvm: nvm install 20 && nvm use 20",
        )
    except Exception:
        return _check("Node >= 20", False, "Install Node 20+ via nvm: https://github.com/nvm-sh/nvm")


def check_ffmpeg() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        line = result.stdout.splitlines()[0] if result.stdout else ""
        parts = line.split()
        if len(parts) >= 3:
            ver_str = parts[2].lstrip("n")
            major = int(ver_str.split(".")[0])
            ok = major >= 6
            return _check(
                f"ffmpeg >= 6  (found {parts[2]})",
                ok,
                "Install ffmpeg 6+: brew install ffmpeg  or  apt install ffmpeg",
            )
        return _check("ffmpeg >= 6", False, "Install ffmpeg 6+: brew install ffmpeg")
    except Exception:
        return _check("ffmpeg >= 6", False, "Install ffmpeg 6+: brew install ffmpeg")


def check_fonts() -> bool:
    font_dir = Path("satori-service/fonts")
    black = font_dir / "SourceSerif4-Black.ttf"
    regular = font_dir / "SourceSerif4-Regular.ttf"
    ok = black.exists() and regular.exists()
    return _check(
        "Source Serif 4 fonts present",
        ok,
        "Download from Google Fonts (SIL OFL) and place in satori-service/fonts/",
    )


def check_satori() -> bool:
    import httpx
    from nobodynamed_video.config import get_settings

    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.satori_url}/health", timeout=3.0)
        ok = resp.status_code == 200 and resp.json().get("status") == "ok"
        return _check(
            f"Satori sidecar at {settings.satori_url}",
            ok,
            "Start it: cd satori-service && pnpm dev",
        )
    except Exception:
        return _check(
            f"Satori sidecar at {settings.satori_url}",
            False,
            "Start it: cd satori-service && pnpm dev",
        )


def check_d1() -> bool:
    from nobodynamed_video.config import get_settings

    settings = get_settings()
    if settings.use_sqlite:
        ok = settings.sqlite_fixture.exists()
        return _check(
            f"SQLite fixture at {settings.sqlite_fixture}",
            ok,
            "Run: python scripts/build_fixture.py",
        )
    import httpx
    try:
        resp = httpx.post(
            settings.d1_url,
            json={"sql": "SELECT 1", "params": []},
            headers={"Authorization": f"Bearer {settings.get_d1_token()}"},
            timeout=5.0,
        )
        ok = resp.status_code == 200
        return _check(
            "D1 database reachable",
            ok,
            "Check D1_URL and D1_TOKEN in .env — token may have expired",
        )
    except Exception:
        return _check(
            "D1 database reachable",
            False,
            "Check D1_URL and D1_TOKEN in .env — token may have expired",
        )


def run_doctor() -> None:
    console.rule("[bold]nbn doctor[/bold]")
    checks = [
        check_python(),
        check_node(),
        check_ffmpeg(),
        check_fonts(),
        check_satori(),
        check_d1(),
    ]
    console.rule()
    if all(checks):
        console.print("[green bold]All checks passed. You're good to render.[/green bold]")
    else:
        failed = checks.count(False)
        console.print(f"[red bold]{failed} check(s) failed. Fix the issues above and re-run.[/red bold]")
        raise SystemExit(1)


if __name__ == "__main__":
    run_doctor()
