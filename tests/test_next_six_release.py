"""Release-safety checks for the approved next-six 2025 stories."""

from pathlib import Path

from nobodynamed_video.editorial.story import evaluate_story, load_story

NEXT_SIX = Path("stories/next-2025")
EXPECTED = {
    "rihanna-2025",
    "miley-2025",
    "aaliyah-2025",
    "elsa-2025",
    "leia-2025",
    "atlas-2025",
}


def test_next_six_are_approved_snapshot_bound_and_publishable() -> None:
    paths = sorted(NEXT_SIX.glob("*.yaml"))
    assert {path.stem for path in paths} == EXPECTED

    for path in paths:
        story = load_story(path)
        evaluation = evaluate_story(story)
        assert evaluation.publishable, f"{story.id}: {evaluation.blockers}"
        assert story.approved_by == "michaelcolenso"
        assert story.approved_at is not None
        assert story.approved_content_sha256
        assert story.data_snapshot and story.data_snapshot.startswith("data/ssa-2025/")
        assert story.data_sha256
