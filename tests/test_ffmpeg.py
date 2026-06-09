"""Tests for ffmpeg command generation — asserts the generated argument list."""

from pathlib import Path

from nobodynamed_video.compose.ffmpeg import build_ffmpeg_cmd

FRAMES = Path("out/bertha-2024/frames")
OUT = Path("out/bertha-2024.mp4")


def _filter_complex(cmd: list[str]) -> str:
    return cmd[cmd.index("-filter_complex") + 1]


def test_build_ffmpeg_cmd_has_five_inputs() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    # Four scene inputs + one audio input.
    assert cmd.count("-i") == 5


def test_build_ffmpeg_cmd_starts_with_ffmpeg() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    assert cmd[0] == "ffmpeg"
    assert cmd[1] == "-y"


def test_filter_complex_concatenates_all_scenes() -> None:
    fc = _filter_complex(build_ffmpeg_cmd(FRAMES, OUT))
    assert "concat=n=4:v=1:a=0" in fc


def test_filter_complex_has_no_xfade() -> None:
    # The program is one continuous animation: crossfading it against itself
    # ghosts the picture and trims 0.2 s per transition off the stream.
    fc = _filter_complex(build_ffmpeg_cmd(FRAMES, OUT))
    assert "xfade" not in fc


def test_filter_complex_forces_bt709_limited_conversion() -> None:
    # swscale defaults to a BT.601 matrix; the stream is tagged BT.709, so the
    # conversion must be forced to match or colors shift on playback.
    fc = _filter_complex(build_ffmpeg_cmd(FRAMES, OUT))
    assert "out_color_matrix=bt709" in fc
    assert "in_range=pc" in fc
    assert "out_range=tv" in fc
    assert "yuv420p" in fc


def test_build_ffmpeg_cmd_contains_libx264() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    assert "libx264" in cmd


def test_build_ffmpeg_cmd_encode_quality() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    assert cmd[cmd.index("-crf") + 1] == "17"
    assert cmd[cmd.index("-preset") + 1] == "slow"
    assert cmd[cmd.index("-tune") + 1] == "animation"
    assert cmd[cmd.index("-profile:v") + 1] == "high"


def test_build_ffmpeg_cmd_contains_yuv420p() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    assert "yuv420p" in cmd


def test_build_ffmpeg_cmd_contains_faststart() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    assert "+faststart" in cmd


def test_build_ffmpeg_cmd_color_metadata() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    assert cmd[cmd.index("-colorspace") + 1] == "bt709"
    assert cmd[cmd.index("-color_primaries") + 1] == "bt709"
    assert cmd[cmd.index("-color_trc") + 1] == "bt709"
    assert cmd[cmd.index("-color_range") + 1] == "tv"


def test_build_ffmpeg_cmd_output_path() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    assert str(OUT) == cmd[-1]


def test_build_ffmpeg_cmd_total_duration() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT, total_duration=18.0)
    t_idx = [i for i, v in enumerate(cmd) if v == "-t"]
    assert any(cmd[i + 1] == "18.0" for i in t_idx)


def test_build_ffmpeg_cmd_silent_audio_48k() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT)
    joined = " ".join(cmd)
    assert "anullsrc" in joined
    assert "sample_rate=48000" in joined


def test_build_ffmpeg_cmd_with_audio_bed() -> None:
    cmd = build_ffmpeg_cmd(FRAMES, OUT, audio_path=Path("fixtures/bed.wav"))
    joined = " ".join(cmd)
    assert "fixtures/bed.wav" in cmd
    # TikTok normalizes to ≈ -14 LUFS; the bed should already sit there.
    assert "loudnorm=I=-14.0" in joined
    assert cmd[cmd.index("-b:a") + 1] == "192k"
    assert cmd[cmd.index("-ar") + 1] == "48000"
