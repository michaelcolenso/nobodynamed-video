"""D1 preflight rejects changed annual observations before any rendering."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from ruamel.yaml import YAML

from scripts.verify_batch_data import approved_snapshots, verify


@pytest.mark.parametrize("batch", ["launch-six", "next-six", "viral-ten"])
def test_supported_batch_sources_are_approved(batch: str) -> None:
    snapshots = approved_snapshots(Path(f"batches/{batch}.yaml"))
    assert len(snapshots) == (10 if batch == "viral-ten" else 6)


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", [None, "count", "rank", "suppressed_year"])
async def test_current_d1_must_match_every_approved_observation(
    tmp_path: Path, damage: str | None
) -> None:
    batch = Path("batches/viral-ten.yaml")
    snapshots = approved_snapshots(batch)
    for snapshot in snapshots:
        current = snapshot.model_copy(deep=True)
        if current.name == "Taylor":
            point = next(p for p in current.observations if p.year == 2025)
            if damage == "count":
                point.count = 999
            elif damage == "rank":
                point.rank = 999
            elif damage == "suppressed_year":
                point.count = None
                point.rank = None
        (tmp_path / f"{current.name.lower()}-{current.sex.lower()}.json").write_text(
            current.model_dump_json()
        )
    with patch("scripts.verify_batch_data.generate", new_callable=AsyncMock):
        if damage:
            with pytest.raises(ValueError, match="Taylor: current D1 differs"):
                await verify(batch, tmp_path)
        else:
            await verify(batch, tmp_path)


def test_ci_verifies_then_renders_and_preserves_existing_releases() -> None:
    workflow = YAML(typ="safe").load(Path(".github/workflows/ci.yaml"))
    assert workflow["on"]["workflow_dispatch"]["inputs"]["batch"]["default"] == "none"
    job = workflow["jobs"]["batch"]
    assert "workflow_dispatch" in job["if"]
    assert "refs/heads/main" in job["if"]
    assert job["needs"] == "check"
    names = [step.get("name") for step in job["steps"]]
    gates = [
        "Verify approved stories and current D1 data",
        "Render verified batch",
        "Stage verified release",
        "Upload verified release",
        "Publish verified release to videos branch",
    ]
    assert [names.index(name) for name in gates] == sorted(names.index(name) for name in gates)
    for step in job["steps"]:
        assert not step.get("continue-on-error", False)
        if step.get("name") in gates:
            assert step.get("if", "success()") == "success()"
        assert "push -f" not in step.get("run", "")
    publisher = job["steps"][names.index(gates[-1])]["run"]
    assert "nobodynamed_video.publish_release" in publisher
    assert '"$BATCH_NAME"' in publisher
