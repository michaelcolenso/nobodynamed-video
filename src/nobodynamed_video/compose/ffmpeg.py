"""ffmpeg composition — concatenates the frame sequence and encodes for upload.

The 540 frames are one continuous shared-canvas program, so scenes are joined
with a straight concat (no xfade): crossfading a continuous animation against
itself only produces double-exposure ghosting, shortens the video stream by
0.2 s per transition, and shifts every authored timing earlier in the output.
Concat keeps the stream at exactly 540 frames / 18.000 s.

Color: PNG frames are full-range sRGB. The RGB→YUV conversion is forced to
BT.709 limited range to match the stream tags — swscale's default matrix is
BT.601, which visibly shifts the brand crimson toward orange on every player
that honors the BT.709 tag.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from nobodynamed_video.exceptions import FfmpegFailed
from nobodynamed_video.render.frame_planner import SCENE_ORDER

# TikTok normalizes to roughly -14 LUFS; matching it avoids the platform
# re-gaining (and pumping) a quiet bed.
AUDIO_TARGET_LUFS = -14.0


def build_ffmpeg_cmd(
    frames_dir: Path,
    out_path: Path,
    fps: int = 30,
    total_duration: float = 18.0,
    audio_path: Path | None = None,
    audio_lufs: float = AUDIO_TARGET_LUFS,
    subtitle_path: Path | None = None,
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
            "anullsrc=channel_layout=stereo:sample_rate=48000",
        ]
        audio_input_index = len(SCENE_ORDER)

    # ── Video filter graph ────────────────────────────────────────────────────
    scene_labels = "".join(f"[{i}:v]" for i in range(len(SCENE_ORDER)))
    concat = f"{scene_labels}concat=n={len(SCENE_ORDER)}:v=1:a=0[vcat]"
    # Explicit full-range sRGB → limited-range BT.709 conversion; must agree
    # with the color metadata tags below.
    filters = "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p"
    if subtitle_path:
        escaped = str(subtitle_path.resolve()).replace("\\", "\\\\").replace(":", "\\:")
        escaped = escaped.replace("'", "\\'")
        filters += f",subtitles=filename='{escaped}'"
    to_bt709 = f"[vcat]{filters}[v]"
    cmd += ["-filter_complex", "; ".join([concat, to_bt709])]
    cmd += ["-map", "[v]", "-map", f"{audio_input_index}:a"]

    # ── Video encode ──────────────────────────────────────────────────────────
    # The platform re-encodes on upload, so the master should be visually
    # transparent: CRF 17 + slow + tune animation (flat fills, hard edges).
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "17",
        "-tune",
        "animation",
        "-profile:v",
        "high",
        "-level",
        "4.2",
        "-g",
        str(fps * 2),
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
        "-color_range",
        "tv",
    ]

    # ── Audio encode ──────────────────────────────────────────────────────────
    if audio_path:
        cmd += [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-af",
            f"loudnorm=I={audio_lufs}:LRA=11:TP=-1.0",
        ]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "48000"]

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
