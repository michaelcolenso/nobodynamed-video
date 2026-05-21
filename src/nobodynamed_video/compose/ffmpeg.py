"""ffmpeg composition — builds the concat + crossfade filter graph and runs it."""

from __future__ import annotations

import subprocess
from pathlib import Path

from nobodynamed_video.exceptions import FfmpegFailed
from nobodynamed_video.render.frame_planner import SCENE_DURATIONS, SCENE_ORDER

XFADE_DURATION = 0.2  # seconds — crossfade between adjacent scenes


def _xfade_offsets() -> list[float]:
    """Compute xfade offset values (start-of-transition) between scenes.

    Each xfade is applied to an already-blended stream whose length is
    shortened by XFADE_DURATION for each prior transition.  The offset for
    transition i must account for all i prior xfades:

      offset_i = cumulative_scene_duration_through_i - XFADE_DURATION * (i + 1)

    Results match ARCHITECTURE.md: 2.8, 8.6, 14.4.
    """
    offsets = []
    cumulative = 0.0
    for i, kind in enumerate(SCENE_ORDER[:-1]):
        cumulative += SCENE_DURATIONS[kind]
        offsets.append(round(cumulative - XFADE_DURATION * (i + 1), 6))
    return offsets


def build_ffmpeg_cmd(
    frames_dir: Path,
    out_path: Path,
    fps: int = 30,
    total_duration: float = 18.0,
    audio_path: Path | None = None,
    audio_lufs: float = -22.0,
) -> list[str]:
    """Return the ffmpeg argument list (does not execute)."""
    cmd: list[str] = ["ffmpeg", "-y"]

    # ── Scene frame sequence inputs ───────────────────────────────────────────
    for kind in SCENE_ORDER:
        cmd += ["-framerate", str(fps), "-i", str(frames_dir / f"{kind}_%03d.png")]

    # ── Audio input ───────────────────────────────────────────────────────────
    if audio_path:
        cmd += ["-i", str(audio_path)]
        audio_input_index = len(SCENE_ORDER)
    else:
        # Silent stereo AAC — required so TikTok on Android accepts the file.
        cmd += [
            "-f",
            "lavfi",
            "-t",
            str(total_duration),
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
        ]
        audio_input_index = len(SCENE_ORDER)

    # ── Video filter graph ────────────────────────────────────────────────────
    offsets = _xfade_offsets()
    # offset_0 = end_of_hook - xfade = 3.0 - 0.2 = 2.8
    # offset_1 = end_of_reveal - xfade = 9.0 - 0.2 = 8.8  (cumulative: 3+6=9)
    # offset_2 = end_of_narrative - xfade = 15.0 - 0.2 = 14.8

    xfade_parts: list[str] = []
    in_label = "[0:v]"
    for i, offset in enumerate(offsets):
        next_label = f"[v{i}{i + 1}]"
        xfade_parts.append(
            f"{in_label}[{i + 1}:v]xfade=transition=fade:duration={XFADE_DURATION}:offset={offset}{next_label}"
        )
        in_label = next_label

    # Final: add format + color space metadata, emit as [v]
    final_filter = f"{in_label}format=yuv420p[v]"
    filter_complex = "; ".join([*xfade_parts, final_filter])

    cmd += ["-filter_complex", filter_complex]
    cmd += ["-map", "[v]", "-map", f"{audio_input_index}:a"]

    # ── Video encode ──────────────────────────────────────────────────────────
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        # Color metadata so crimson looks correct on iPhone.
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
    ]

    # ── Audio encode ──────────────────────────────────────────────────────────
    if audio_path:
        cmd += [
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-af",
            f"loudnorm=I={audio_lufs}:LRA=11:TP=-1.5",
        ]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]

    cmd += ["-t", str(total_duration)]
    cmd += [str(out_path)]
    return cmd


def run_ffmpeg(cmd: list[str]) -> None:
    """Execute the ffmpeg command; raise FfmpegFailed if it exits non-zero."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegFailed(f"ffmpeg exited {result.returncode}:\n{result.stderr[-3000:]}")


def get_ffmpeg_version() -> str:
    """Return the installed ffmpeg version string, or 'unknown' on failure."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        # "ffmpeg version 6.0 ..." → "6.0"
        parts = first_line.split()
        if len(parts) >= 3 and parts[0] == "ffmpeg":
            return parts[2]
        return first_line[:40]
    except Exception:
        return "unknown"
