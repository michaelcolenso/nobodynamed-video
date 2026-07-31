from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from nobodynamed_video.batch.runner import _frame_cache_key, _FrameCache


class FakeSatoriClient:
    def __init__(self) -> None:
        self.calls = 0

    async def render(self, template: str, props: dict[str, Any]) -> bytes:
        self.calls += 1
        await asyncio.sleep(0.01)
        return b"\x89PNG\r\n\x1a\nrendered"


def test_frame_cache_key_is_independent_of_mapping_order() -> None:
    first = _frame_cache_key("canvas", {"alpha": 1, "nested": {"x": 2, "y": 3}})
    second = _frame_cache_key("canvas", {"nested": {"y": 3, "x": 2}, "alpha": 1})

    assert first == second


@pytest.mark.asyncio
async def test_frame_cache_deduplicates_concurrent_renders(tmp_path: Path) -> None:
    cache = _FrameCache(tmp_path / "cache")
    client = FakeSatoriClient()
    first = tmp_path / "frames" / "first.png"
    second = tmp_path / "frames" / "second.png"
    first.parent.mkdir()

    results = await asyncio.gather(
        cache.materialize(client, "canvas", {"frame": 1}, first),  # type: ignore[arg-type]
        cache.materialize(client, "canvas", {"frame": 1}, second),  # type: ignore[arg-type]
    )

    assert client.calls == 1
    assert first.read_bytes() == second.read_bytes() == results[0][0]
    assert sum(render_time > 0 for _, render_time in results) == 1
