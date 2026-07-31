from nobodynamed_video.qc.checks import (
    _EXPECTED_FRAMES,
    _EXPECTED_STREAM_DURATION_S,
    _check_frozen_frames,
)
from nobodynamed_video.render.frame_planner import total_frame_count
from nobodynamed_video.render.programs import TOTAL_DURATION_S


def test_qc_expectations_follow_canonical_program() -> None:
    assert total_frame_count() == _EXPECTED_FRAMES
    assert TOTAL_DURATION_S == _EXPECTED_STREAM_DURATION_S


def test_frozen_check_allows_a_single_identical_pair() -> None:
    hashes = {f"hook_{index:03d}.png": str(index) for index in range(11)}
    hashes["hook_001.png"] = hashes["hook_000.png"]

    assert _check_frozen_frames(hashes) == []


def test_frozen_check_flags_a_frozen_opening_window() -> None:
    hashes = {f"hook_{index:03d}.png": "same" for index in range(11)}

    issues = _check_frozen_frames(hashes)

    assert len(issues) == 1
    assert issues[0].code == "FROZEN_FRAMES"
