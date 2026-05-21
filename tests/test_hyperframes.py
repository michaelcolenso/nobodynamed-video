"""Tests for scalar hyperframe tracks."""

import pytest
from nobodynamed_video.render.hyperframes import Hyperframe, sample_scalar_track
from nobodynamed_video.render.motion import ease_out_quart


def test_sample_scalar_track_clamps_before_first_keyframe() -> None:
    track = (Hyperframe(1.0, 10.0), Hyperframe(2.0, 20.0))
    assert sample_scalar_track(track, 0.5) == pytest.approx(10.0)


def test_sample_scalar_track_clamps_after_last_keyframe() -> None:
    track = (Hyperframe(1.0, 10.0), Hyperframe(2.0, 20.0))
    assert sample_scalar_track(track, 3.0) == pytest.approx(20.0)


def test_sample_scalar_track_interpolates_linearly() -> None:
    track = (Hyperframe(0.0, 0.0), Hyperframe(4.0, 1.0))
    assert sample_scalar_track(track, 2.0) == pytest.approx(0.5)


def test_sample_scalar_track_uses_segment_easing() -> None:
    track = (Hyperframe(0.0, 0.0, ease_out_quart), Hyperframe(1.0, 1.0))
    assert sample_scalar_track(track, 0.25) > 0.5


def test_sample_scalar_track_requires_frames() -> None:
    with pytest.raises(ValueError):
        sample_scalar_track((), 0.0)
