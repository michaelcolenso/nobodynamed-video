"""Post-render quality checks for composed video outputs."""

from __future__ import annotations

import json
import re
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

_EXPECTED_WIDTH = 1080
_EXPECTED_HEIGHT = 1920
_MIN_DURATION_S = 9.0
_MAX_DURATION_S = 14.0
_STREAM_DURATION_TOLERANCE_S = 0.05
_EXPECTED_FPS = "30/1"
_EXPECTED_COLOR = {
    "color_space": "bt709",
    "color_primaries": "bt709",
    "color_transfer": "bt709",
    "color_range": "tv",
}
_FROZEN_CHECK_DEPTH = 10
# Cover check: flag the first frame if ≥98% of pixels sit below luma 32
# (limited range) — i.e. nothing but background. Frame 0 is the default
# TikTok cover, so it must carry readable content.
_COVER_BLACK_AMOUNT = 98
_COVER_BLACK_THRESHOLD = 32


@dataclass
class QCIssue:
    """A single quality check finding with severity, code, and message."""

    severity: Literal["error", "warning"]
    code: str
    message: str


@dataclass
class QCResult:
    """Aggregated quality check outcome for one rendered video."""

    spec_id: str
    passed: bool
    issues: list[QCIssue]
    keyframe_paths: list[Path] = field(default_factory=list)


def _check_frame_count(frames_dir: Path, expected_frames: int) -> list[QCIssue]:
    count = len(list(frames_dir.glob("*.png")))
    if count != expected_frames:
        msg = f"expected {expected_frames} frames, found {count}"
        return [QCIssue("error", "FRAME_COUNT", msg)]
    return []


def _check_frozen_frames(sha256_frames: dict[str, str], expected_frames: int) -> list[QCIssue]:
    issues: list[QCIssue] = []
    depth = min(_FROZEN_CHECK_DEPTH, expected_frames - 1)
    for i in range(depth):
        a = sha256_frames.get(f"frame_{i:04d}.png")
        b = sha256_frames.get(f"frame_{i + 1:04d}.png")
        if a and b and a == b:
            msg = f"opening frames {i} and {i + 1} are identical"
            issues.append(QCIssue("warning", "FROZEN_FRAMES", msg))
    return issues


def _check_dimensions(frames_dir: Path) -> list[QCIssue]:
    sample = frames_dir / "frame_0000.png"
    if not sample.exists():
        return [QCIssue("error", "BAD_DIMENSIONS", "frame_0000.png missing")]
    with sample.open("rb") as f:
        f.read(16)  # 8-byte PNG sig + 4-byte IHDR length + 4-byte "IHDR"
        width, height = struct.unpack(">II", f.read(8))
    if width != _EXPECTED_WIDTH or height != _EXPECTED_HEIGHT:
        msg = f"expected {_EXPECTED_WIDTH}x{_EXPECTED_HEIGHT}, got {width}x{height}"
        return [QCIssue("error", "BAD_DIMENSIONS", msg)]
    return []


def _check_mp4(mp4_path: Path, expected_frames: int, expected_duration_s: float) -> list[QCIssue]:
    if not mp4_path.exists():
        return [QCIssue("error", "MP4_INVALID", "MP4 file not found")]
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(mp4_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data: dict[str, object] = json.loads(proc.stdout)
    except Exception as exc:
        return [QCIssue("error", "MP4_INVALID", f"ffprobe failed: {exc}")]

    streams = data.get("streams", [])
    assert isinstance(streams, list)
    video = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"),
        None,
    )
    if video is None:
        return [QCIssue("error", "MP4_INVALID", "no video stream found")]

    issues: list[QCIssue] = []
    codec = video.get("codec_name")
    if codec != "h264":
        issues.append(QCIssue("error", "MP4_INVALID", f"unexpected codec: {codec}"))
    w, h = video.get("width"), video.get("height")
    if w != _EXPECTED_WIDTH or h != _EXPECTED_HEIGHT:
        issues.append(QCIssue("error", "MP4_INVALID", f"unexpected resolution: {w}x{h}"))

    fps = video.get("r_frame_rate")
    if fps != _EXPECTED_FPS:
        issues.append(QCIssue("error", "MP4_INVALID", f"unexpected frame rate: {fps}"))

    # Container duration — the user-facing length.
    fmt = data.get("format", {})
    fmt_duration = fmt.get("duration") if isinstance(fmt, dict) else None
    duration = float(str(fmt_duration if fmt_duration is not None else video.get("duration", 0)))
    if duration < _MIN_DURATION_S - _STREAM_DURATION_TOLERANCE_S:
        msg = f"duration {duration:.2f}s < {_MIN_DURATION_S}s"
        issues.append(QCIssue("error", "MP4_INVALID", msg))
    if duration > _MAX_DURATION_S + _STREAM_DURATION_TOLERANCE_S:
        msg = f"duration {duration:.2f}s > {_MAX_DURATION_S}s"
        issues.append(QCIssue("error", "MP4_INVALID", msg))

    # Video stream duration — concat composition must carry all 540 frames to
    # exactly 18.0 s; a short stream means trimmed/overlapped frames and a
    # frozen tail padded out by the audio track.
    stream_duration = video.get("duration")
    if stream_duration is not None:
        drift = abs(float(str(stream_duration)) - expected_duration_s)
        if drift > _STREAM_DURATION_TOLERANCE_S:
            msg = (
                f"video stream {float(str(stream_duration)):.2f}s != "
                f"{expected_duration_s}s (frozen tail or dropped frames)"
            )
            issues.append(QCIssue("error", "MP4_INVALID", msg))
    nb_frames = video.get("nb_frames")
    if nb_frames is not None and str(nb_frames) != str(expected_frames):
        msg = f"video stream has {nb_frames} frames, expected {expected_frames}"
        issues.append(QCIssue("error", "MP4_INVALID", msg))

    # Color metadata — untagged or mismatched tags shift the brand colors on
    # players that assume defaults.
    for key, expected in _EXPECTED_COLOR.items():
        actual = video.get(key)
        if actual != expected:
            msg = f"{key} is {actual!r}, expected {expected!r}"
            issues.append(QCIssue("warning", "COLOR_METADATA", msg))

    audio = next(
        (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"),
        None,
    )
    if audio is None:
        msg = "no audio stream — TikTok on Android rejects silent-track-less files"
        issues.append(QCIssue("error", "MP4_INVALID", msg))
    return issues


def _check_cover_frame(frames_dir: Path) -> list[QCIssue]:
    """Frame 0 is the default TikTok cover — it must not be (near-)black."""
    cover = frames_dir / "frame_0000.png"
    if not cover.exists():
        return [QCIssue("error", "BLACK_COVER", "frame_0000.png missing")]
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-f",
                "lavfi",
                "-i",
                f"movie={cover},"
                f"blackframe=amount={_COVER_BLACK_AMOUNT}:threshold={_COVER_BLACK_THRESHOLD}",
                "-show_entries",
                "frame_tags=lavfi.blackframe.pblack",
                "-print_format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except Exception as exc:
        return [QCIssue("warning", "BLACK_COVER", f"blackframe probe failed: {exc}")]

    frames = data.get("frames", [])
    assert isinstance(frames, list)
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        tags = frame.get("tags", {})
        if isinstance(tags, dict) and "lavfi.blackframe.pblack" in tags:
            pblack = tags.get("lavfi.blackframe.pblack", "?")
            msg = f"cover frame is {pblack}% black — default thumbnail would be empty"
            return [QCIssue("error", "BLACK_COVER", msg)]
    return []


def _check_black_frames(mp4_path: Path) -> list[QCIssue]:
    if not mp4_path.exists():
        return []
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-f",
                "lavfi",
                "-i",
                f"movie={mp4_path},blackdetect=d=0.1:pix_th=0.90[out0]",
                "-show_entries",
                "tags",
                "-print_format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except Exception as exc:
        return [QCIssue("warning", "BLACK_FRAMES", f"blackdetect probe failed: {exc}")]

    frames = data.get("frames", [])
    assert isinstance(frames, list)
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        tags = frame.get("tags", {})
        if isinstance(tags, dict) and "lavfi.black_start" in tags:
            start = tags.get("lavfi.black_start", "?")
            end = tags.get("lavfi.black_end", "?")
            return [QCIssue("error", "BLACK_FRAMES", f"black segment {start}s–{end}s")]
    return []


def _check_audio_loudness(mp4_path: Path) -> list[QCIssue]:
    """Measure the encoded narration master rather than trusting filter intent."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(mp4_path),
                "-af",
                "loudnorm=I=-14:LRA=7:TP=-1:print_format=json",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        matches = re.findall(r"\{\s*\"input_i\".*?\}", proc.stderr, flags=re.DOTALL)
        if not matches:
            raise ValueError("loudnorm summary missing")
        measured = json.loads(matches[-1])
        integrated = float(measured["input_i"])
        true_peak = float(measured["input_tp"])
    except Exception as exc:
        return [QCIssue("warning", "AUDIO_LEVELS", f"loudness probe failed: {exc}")]

    issues: list[QCIssue] = []
    if abs(integrated - (-14.0)) > 1.5:
        issues.append(
            QCIssue(
                "warning",
                "AUDIO_LEVELS",
                f"integrated loudness is {integrated:.1f} LUFS, target -14 LUFS",
            )
        )
    if true_peak > -0.5:
        issues.append(
            QCIssue(
                "warning",
                "AUDIO_LEVELS",
                f"true peak is {true_peak:.1f} dBTP, target at or below -1 dBTP",
            )
        )
    return issues


def _check_editorial_manifest(manifest: dict[str, object]) -> list[QCIssue]:
    if not manifest.get("story_kind"):
        return []
    issues: list[QCIssue] = []
    score = int(str(manifest.get("story_score") or 0))
    if score < 75:
        issues.append(QCIssue("error", "STORY_GATE", f"story score is {score}, expected 75+"))
    if not manifest.get("script") or not manifest.get("word_timings"):
        issues.append(QCIssue("error", "NARRATION", "script or word timings missing"))
    if not manifest.get("narration_provider"):
        issues.append(QCIssue("error", "NARRATION", "approved story has no narration provider"))
    if manifest.get("ai_voice_disclosure") != "AI-generated narration":
        issues.append(QCIssue("error", "AI_DISCLOSURE", "AI voice disclosure missing"))
    return issues


def _keyframe_names(frame_count: int) -> list[str]:
    indices = {
        0,
        round(frame_count * 0.08),
        round(frame_count * 0.35),
        round(frame_count * 0.55),
        round(frame_count * 0.75),
        round(frame_count * 0.90),
        max(frame_count - 1, 0),
    }
    return [f"frame_{index:04d}.png" for index in sorted(indices)]


def run_all_checks(result: dict[str, object], out_dir: Path) -> QCResult:
    """Run all quality checks for a single succeeded, composed render result."""
    spec_id = str(result["id"])
    mp4_path = Path(str(result["mp4"]))
    frames_dir = out_dir / spec_id / "frames"
    manifest_path = out_dir / f"{spec_id}.json"

    sha256_frames: dict[str, str] = {}
    manifest_data: dict[str, object] = {}
    if manifest_path.exists():
        try:
            raw_manifest = json.loads(manifest_path.read_text())
            if isinstance(raw_manifest, dict):
                manifest_data = raw_manifest
            raw = manifest_data.get("sha256_frames", {})
            if isinstance(raw, dict):
                sha256_frames = {str(k): str(v) for k, v in raw.items()}
        except Exception:
            pass

    expected_frames = int(str(manifest_data.get("frame_count") or result.get("frames") or 0))
    expected_duration = float(
        str(manifest_data.get("duration_s") or result.get("duration_s") or 11.0)
    )

    issues: list[QCIssue] = []
    issues += _check_frame_count(frames_dir, expected_frames)
    issues += _check_frozen_frames(sha256_frames, expected_frames)
    issues += _check_dimensions(frames_dir)
    issues += _check_cover_frame(frames_dir)
    issues += _check_mp4(mp4_path, expected_frames, expected_duration)
    issues += _check_black_frames(mp4_path)
    issues += _check_editorial_manifest(manifest_data)
    if manifest_data.get("narration_provider"):
        issues += _check_audio_loudness(mp4_path)

    passed = not any(i.severity == "error" for i in issues)
    keyframe_paths = [
        frames_dir / name
        for name in _keyframe_names(expected_frames)
        if (frames_dir / name).exists()
    ]
    return QCResult(spec_id=spec_id, passed=passed, issues=issues, keyframe_paths=keyframe_paths)
