"""Post-render quality checks for composed video outputs."""

from __future__ import annotations

import json
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

_EXPECTED_FRAMES = 540
_EXPECTED_WIDTH = 1080
_EXPECTED_HEIGHT = 1920
_MIN_DURATION_S = 17.9
# With straight concat composition the video stream must carry every frame:
# 540 frames / 30 fps = 18.0 s exactly (xfade used to silently trim 0.6 s).
_EXPECTED_STREAM_DURATION_S = 18.0
_STREAM_DURATION_TOLERANCE_S = 0.05
_EXPECTED_FPS = "30/1"
_EXPECTED_COLOR = {
    "color_space": "bt709",
    "color_primaries": "bt709",
    "color_transfer": "bt709",
    "color_range": "tv",
}
_SCENE_FRAME_COUNTS = {"hook": 90, "reveal": 180, "narrative": 180, "cta": 90}
_FROZEN_CHECK_DEPTH = 10
# Cover check: flag the first frame if ≥98% of pixels sit below luma 32
# (limited range) — i.e. nothing but background. Frame 0 is the default
# TikTok cover, so it must carry readable content.
_COVER_BLACK_AMOUNT = 99
_COVER_BLACK_THRESHOLD = 32

KEYFRAME_NAMES = [
    "hook_000.png",
    "hook_045.png",
    "reveal_000.png",
    "reveal_090.png",
    "narrative_000.png",
    "narrative_090.png",
    "cta_000.png",
    "cta_089.png",
]


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


def _check_frame_count(frames_dir: Path, expected_frames: int = _EXPECTED_FRAMES) -> list[QCIssue]:
    count = len(list(frames_dir.glob("*.png")))
    if count != expected_frames:
        msg = f"expected {expected_frames} frames, found {count}"
        return [QCIssue("error", "FRAME_COUNT", msg)]
    return []


def _check_frozen_frames(
    sha256_frames: dict[str, str], scene_frame_counts: dict[str, int] | None = None
) -> list[QCIssue]:
    issues: list[QCIssue] = []
    for scene, total in (scene_frame_counts or _SCENE_FRAME_COUNTS).items():
        depth = min(_FROZEN_CHECK_DEPTH, total - 1)
        for i in range(depth):
            a = sha256_frames.get(f"{scene}_{i:03d}.png")
            b = sha256_frames.get(f"{scene}_{i + 1:03d}.png")
            if a and b and a == b:
                msg = f"{scene} frames {i} and {i + 1} are identical"
                issues.append(QCIssue("warning", "FROZEN_FRAMES", msg))
    return issues


def _check_dimensions(frames_dir: Path) -> list[QCIssue]:
    sample = frames_dir / "hook_000.png"
    if not sample.exists():
        return [QCIssue("error", "BAD_DIMENSIONS", "hook_000.png missing")]
    with sample.open("rb") as f:
        f.read(16)  # 8-byte PNG sig + 4-byte IHDR length + 4-byte "IHDR"
        width, height = struct.unpack(">II", f.read(8))
    if width != _EXPECTED_WIDTH or height != _EXPECTED_HEIGHT:
        msg = f"expected {_EXPECTED_WIDTH}x{_EXPECTED_HEIGHT}, got {width}x{height}"
        return [QCIssue("error", "BAD_DIMENSIONS", msg)]
    return []


def _check_mp4(
    mp4_path: Path,
    expected_frames: int = _EXPECTED_FRAMES,
    expected_duration: float = _EXPECTED_STREAM_DURATION_S,
    expected_fps: int = 30,
) -> list[QCIssue]:
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
    expected_fps_fraction = f"{expected_fps}/1"
    if fps != expected_fps_fraction:
        issues.append(QCIssue("error", "MP4_INVALID", f"unexpected frame rate: {fps}"))

    # Container duration — the user-facing length.
    fmt = data.get("format", {})
    fmt_duration = fmt.get("duration") if isinstance(fmt, dict) else None
    duration = float(str(fmt_duration if fmt_duration is not None else video.get("duration", 0)))
    minimum_duration = expected_duration - _STREAM_DURATION_TOLERANCE_S
    if duration < minimum_duration:
        msg = f"duration {duration:.2f}s < {minimum_duration:.2f}s"
        issues.append(QCIssue("error", "MP4_INVALID", msg))

    # Video stream duration — concat composition must carry all 540 frames to
    # exactly 18.0 s; a short stream means trimmed/overlapped frames and a
    # frozen tail padded out by the audio track.
    stream_duration = video.get("duration")
    if stream_duration is not None:
        drift = abs(float(str(stream_duration)) - expected_duration)
        if drift > _STREAM_DURATION_TOLERANCE_S:
            msg = (
                f"video stream {float(str(stream_duration)):.2f}s != "
                f"{expected_duration}s (frozen tail or dropped frames)"
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
    cover = frames_dir / "hook_000.png"
    if not cover.exists():
        return [QCIssue("error", "BLACK_COVER", "hook_000.png missing")]
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


def run_all_checks(result: dict[str, object], out_dir: Path) -> QCResult:
    """Run all quality checks for a single succeeded, composed render result."""
    spec_id = str(result["id"])
    mp4_path = Path(str(result["mp4"]))
    frames_dir = out_dir / spec_id / "frames"
    manifest_path = out_dir / f"{spec_id}.json"

    sha256_frames: dict[str, str] = {}
    expected_duration = float(str(result.get("duration_s", _EXPECTED_STREAM_DURATION_S)))
    expected_fps = int(str(result.get("fps", 30)))
    expected_frames = round(expected_duration * expected_fps)
    raw_scene_counts = result.get("scene_frame_counts", _SCENE_FRAME_COUNTS)
    scene_counts = (
        {str(k): int(v) for k, v in raw_scene_counts.items()}
        if isinstance(raw_scene_counts, dict)
        else _SCENE_FRAME_COUNTS
    )
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text())
            raw = manifest_data.get("sha256_frames", {})
            if isinstance(raw, dict):
                sha256_frames = {str(k): str(v) for k, v in raw.items()}
        except Exception:
            pass

    issues: list[QCIssue] = []
    issues += _check_frame_count(frames_dir, expected_frames)
    issues += _check_frozen_frames(sha256_frames, scene_counts)
    issues += _check_dimensions(frames_dir)
    issues += _check_cover_frame(frames_dir)
    issues += _check_mp4(mp4_path, expected_frames, expected_duration, expected_fps)
    issues += _check_black_frames(mp4_path)

    passed = not any(i.severity == "error" for i in issues)
    keyframe_paths = [frames_dir / name for name in KEYFRAME_NAMES if (frames_dir / name).exists()]
    return QCResult(spec_id=spec_id, passed=passed, issues=issues, keyframe_paths=keyframe_paths)
