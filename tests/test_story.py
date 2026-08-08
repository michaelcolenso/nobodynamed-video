"""Editorial story gate and reviewed-copy regression tests."""

from pathlib import Path

from nobodynamed_video.compose.caption import compose_story_caption
from nobodynamed_video.editorial.story import evaluate_story, load_story
from nobodynamed_video.models import StoryStatus

STORIES = Path("stories")


def test_all_pilot_stories_clear_publish_gate() -> None:
    for path in sorted(STORIES.glob("*.yaml")):
        evaluation = evaluate_story(load_story(path))
        assert evaluation.publishable, (path, evaluation.blockers)
        assert evaluation.score >= 75


def test_draft_story_is_rejected_even_when_copy_is_strong() -> None:
    story = load_story(STORIES / "bertha-2024.yaml").model_copy(
        update={"status": StoryStatus.DRAFT, "approved_by": None, "approved_at": None}
    )
    evaluation = evaluate_story(story)
    assert not evaluation.publishable
    assert "story has not been approved" in evaluation.blockers


def test_cultural_story_requires_two_external_sources() -> None:
    story = load_story(STORIES / "alexa-2024.yaml")
    ssa_only = [source for source in story.evidence if source.kind.value == "ssa"]
    evaluation = evaluate_story(story.model_copy(update={"evidence": ssa_only}))
    assert not evaluation.publishable
    assert any("two non-SSA" in blocker for blocker in evaluation.blockers)


def test_story_caption_is_reviewed_copy_plus_two_to_four_tags() -> None:
    story = load_story(STORIES / "hazel-2024.yaml")
    caption = compose_story_caption(story)
    assert caption.caption.startswith(story.social_caption)
    assert 2 <= len(caption.hashtag_set) <= 4
    assert "timeless" not in caption.caption.lower()
    assert "quietly" not in caption.caption.lower()
