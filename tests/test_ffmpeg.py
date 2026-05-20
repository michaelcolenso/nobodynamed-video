"""Tests for ffmpeg command generation — asserts the generated argument list."""

from pathlib import Path

import pytest

from nobodynamed_video.compose.ffmpeg import (
    XFADE_DURATION,
    _xfade_offsets,
    build_ffmpeg_cmd,
)


def test_xfade_offsets_count() -> None:
    offsets = _xfade_offsets()
    # 4 scenes → 3 transitions.
    assert len(offsets) == 3


def test_xfade_offset_first() -> None:
    # hook=3.0s → first transition starts at 3.0 - 0.2 = 2.8
    offsets = _xfade_offsets()
    assert abs(offsets[0] - 2.8) < 1e-6


def test_xfade_offset_second() -> None:
    # hook(3) + reveal(6) = 9.0 → offset = 9.0 - 0.2 = 8.8
    offsets = _xfade_offsets()
    assert abs(offsets[1] - 8.8) < 1e-6


def test_xfade_offset_third() -> None:
    # hook(3) + reveal(6) + narrative(6) = 15.0 → offset = 15.0 - 0.2 = 14.8
    offsets = _xfade_offsets()
    assert abs(offsets[2] - 14.8) < 1e-6


def test_build_ffmpeg_cmd_has_four_inputs() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    # Four scene inputs + one audio input.
    assert cmd.count("-i") == 5


def test_build_ffmpeg_cmd_starts_with_ffmpeg() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    assert cmd[0] == "ffmpeg"
    assert cmd[1] == "-y"


def test_build_ffmpeg_cmd_contains_libx264() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    assert "libx264" in cmd


def test_build_ffmpeg_cmd_contains_yuv420p() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    assert "yuv420p" in cmd


def test_build_ffmpeg_cmd_contains_faststart() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    assert "+faststart" in cmd


def test_build_ffmpeg_cmd_output_path() -> None:
    out = Path("out/bertha-2024.mp4")
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), out)
    assert str(out) == cmd[-1]


def test_build_ffmpeg_cmd_total_duration() -> None:
    cmd = build_ffmpeg_cmd(
        Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"), total_duration=18.0
    )
    # -t 18.0 should appear near the end.
    t_idx = [i for i, v in enumerate(cmd) if v == "-t"]
    assert any(cmd[i + 1] == "18.0" for i in t_idx)


def test_build_ffmpeg_cmd_silent_audio() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    assert "anullsrc" in " ".join(cmd)


def test_build_ffmpeg_cmd_with_audio_bed() -> None:
    cmd = build_ffmpeg_cmd(
        Path("out/bertha-2024/frames"),
        Path("out/bertha-2024.mp4"),
        audio_path=Path("fixtures/silence-pad.wav"),
    )
    assert "fixtures/silence-pad.wav" in cmd
    assert "loudnorm" in " ".join(cmd)


def test_build_ffmpeg_cmd_filter_complex_has_xfade() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    fc_idx = cmd.index("-filter_complex")
    fc = cmd[fc_idx + 1]
    assert fc.count("xfade") == 3


def test_build_ffmpeg_cmd_bt709_colorspace() -> None:
    cmd = build_ffmpeg_cmd(Path("out/bertha-2024/frames"), Path("out/bertha-2024.mp4"))
    assert "bt709" in cmd
