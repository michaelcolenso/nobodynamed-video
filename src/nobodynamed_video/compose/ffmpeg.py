"""ffmpeg composition for a continuous global frame timeline.

The renderer writes one ``frame_%04d.png`` sequence. A single image input
removes scene-boundary failure modes and lets approved stories run anywhere
inside the 9-14 second editorial envelope.

Color: PNG frames are full-range sRGB. The RGB→YUV conversion is forced to
BT.709 limited range to match the stream tags — swscale's default matrix is
BT.601, which visibly shifts the brand crimson toward orange on every player
that honors the BT.709 tag.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from nobodynamed_video.exceptions import FfmpegFailed

# TikTok normalizes to roughly -14 LUFS; matching it avoids the platform
# re-gaining the narration. True peak is held below -1 dBTP.
AUDIO_TARGET_LUFS = -14.0
TRUE_PEAK_TARGET_DBTP = -1.0


def build_ffmpeg_cmd(
    frames_dir: Path,
    out_path: Path,
    fps: int = 30,
    total_duration: float = 11.0,
    audio_path: Path | None = None,
    narration_path: Path | None = None,
    audio_lufs: float = AUDIO_TARGET_LUFS,
) -> list[str]:
    """Return the ffmpeg argument list (does not execute)."""
    cmd: list[str] = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%04d.png"),
    ]

    next_input = 1
    narration_input: int | None = None
    bed_input: int | None = None
    silent_input: int | None = None
    if narration_path:
        cmd += ["-i", str(narration_path)]
        narration_input = next_input
        next_input += 1
    if audio_path:
        cmd += ["-stream_loop", "-1", "-i", str(audio_path)]
        bed_input = next_input
        next_input += 1
    if narration_input is None and bed_input is None:
        # Silent stereo AAC — required so TikTok on Android accepts the file.
        cmd += [
            "-f",
            "lavfi",
            "-t",
            str(total_duration),
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
        ]
        silent_input = next_input

    # ── Video filter graph ────────────────────────────────────────────────────
    # Explicit full-range sRGB → limited-range BT.709 conversion; must agree
    # with the color metadata tags below.
    filters = ["[0:v]scale=in_range=pc:out_range=tv:out_color_matrix=bt709," "format=yuv420p[v]"]
    loudnorm = f"loudnorm=I={audio_lufs}:LRA=7:TP={TRUE_PEAK_TARGET_DBTP}"
    if narration_input is not None and bed_input is not None:
        filters += [
            f"[{narration_input}:a]aresample=48000,apad," f"atrim=0:{total_duration}[voice]",
            f"[{bed_input}:a]aresample=48000,volume=0.10,apad," f"atrim=0:{total_duration}[bed]",
            f"[voice][bed]amix=inputs=2:duration=longest:normalize=0,{loudnorm}[a]",
        ]
    elif narration_input is not None:
        filters.append(
            f"[{narration_input}:a]aresample=48000,apad," f"atrim=0:{total_duration},{loudnorm}[a]"
        )
    elif bed_input is not None:
        filters.append(
            f"[{bed_input}:a]aresample=48000,apad," f"atrim=0:{total_duration},{loudnorm}[a]"
        )
    cmd += ["-filter_complex", "; ".join(filters)]
    cmd += ["-map", "[v]"]
    cmd += ["-map", "[a]" if silent_input is None else f"{silent_input}:a"]

    cmd += video_encode_args(fps)

    # ── Audio encode ──────────────────────────────────────────────────────────
    if silent_input is None:
        cmd += [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
        ]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "48000"]

    cmd += ["-t", str(total_duration)]
    cmd += [str(out_path)]
    return cmd


def video_encode_args(fps: int) -> list[str]:
    """H.264 master settings shared by every encode, including long-form assembly."""
    # The platform re-encodes on upload, so the master must be a rich,
    # high-bitrate source: true 10 Mbps CBR with bitstream filler. Near-static
    # flat-color scenes make quality-based modes (CRF, 1-pass ABR) collapse to
    # ~0.4–1 Mbps regardless of settings — the bits simply aren't needed
    # locally — but TikTok's re-encode preserves more with a rich source, so
    # we force the rate with nal-hrd=cbr:filler=1. tune animation: flat fills,
    # hard edges.
    return [
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-tune",
        "animation",
        "-b:v",
        "10M",
        "-minrate",
        "10M",
        "-maxrate",
        "10M",
        "-bufsize",
        "20M",
        "-x264-params",
        "nal-hrd=cbr:filler=1",
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


def build_concat_cmd(
    segments: list[Path],
    durations_s: list[float],
    out_path: Path,
    fps: int = 30,
    narrated: bool = True,
    audio_lufs: float = AUDIO_TARGET_LUFS,
) -> list[str]:
    """Join encoded segments into one master with a single loudness pass.

    Every segment comes out of ``build_ffmpeg_cmd`` with identical geometry, rate and
    BT.709 limited-range tags, so the concat filter needs no conversion; the joined
    video is re-encoded with the same master settings rather than stream-copied, which
    keeps one continuous CBR stream and exact frame timestamps across the cuts.
    """
    if not segments or len(segments) != len(durations_s):
        raise ValueError("concat requires one duration per segment")
    cmd: list[str] = ["ffmpeg", "-y"]
    for segment in segments:
        cmd += ["-i", str(segment)]
    # AAC packs 1024-sample frames, so a segment's audio can overrun its video by
    # up to ~21 ms; trimming each track to the video duration keeps the cuts in
    # sync instead of letting that overrun accumulate across chapters.
    parts = [
        f"[{index}:a]atrim=0:{duration},asetpts=PTS-STARTPTS[a{index}]"
        for index, duration in enumerate(durations_s)
    ]
    inputs = "".join(f"[{index}:v][a{index}]" for index in range(len(segments)))
    graph = "; ".join(parts) + f"; {inputs}concat=n={len(segments)}:v=1:a=1[v][cat]"
    if narrated:
        loudnorm = f"loudnorm=I={audio_lufs}:LRA=7:TP={TRUE_PEAK_TARGET_DBTP}"
        graph += f"; [cat]aresample=48000,{loudnorm},aresample=48000[a]"
    else:
        graph += "; [cat]anull[a]"
    cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]"]
    cmd += video_encode_args(fps)
    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    cmd += [str(out_path)]
    return cmd
