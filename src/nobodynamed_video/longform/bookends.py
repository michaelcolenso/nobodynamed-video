"""Hyperframe program for the narrated title cards that open and close an episode."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from nobodynamed_video.compose.narration_pacing import PACED_OVERSHOOT_TOLERANCE_S
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.longform.spec import RosterEntry
from nobodynamed_video.models import LongFormBookend, WordTiming
from nobodynamed_video.render.hyperframes import Hyperframe, sample_scalar_track
from nobodynamed_video.render.motion import ease_out_cubic, lerp, smootherstep
from nobodynamed_video.render.programs import caption_state

# Narration plus a short hold so the last caption group can finish reading.
BOOKEND_TAIL_S = 0.9
MIN_BOOKEND_S = 3.0
MAX_BOOKEND_S = 10.0
# Preview renders have no narration; estimate a documentary read rate.
PREVIEW_WORDS_PER_S = 2.6

ACCENT = (Hyperframe(0.0, 0.0, ease_out_cubic), Hyperframe(0.8, 1.0))
SETTLE = (Hyperframe(0.0, 0.0, ease_out_cubic), Hyperframe(0.85, 1.0))
FADE_IN = (Hyperframe(0.0, 0.0, smootherstep), Hyperframe(0.5, 1.0))
RULE = (Hyperframe(0.2, 0.0, smootherstep), Hyperframe(1.0, 1.0))
SUBHEAD = (Hyperframe(0.4, 0.0, smootherstep), Hyperframe(1.0, 1.0))
FOOTER = (Hyperframe(0.8, 0.0, smootherstep), Hyperframe(1.4, 1.0))
ROSTER_START_S = 0.9
ROSTER_STAGGER_S = 0.18
ROSTER_FADE_S = 0.45
TOTALS_START_S = 0.5
TOTALS_STAGGER_S = 0.45
TOTALS_FADE_S = 0.4
TOTALS_GROW_S = 0.9


# Longest narration a card can carry without cutting audio or captions.
MAX_BOOKEND_NARRATION_S = MAX_BOOKEND_S - BOOKEND_TAIL_S
# Pace-fit target, kept below the limit by more than atempo's allowed overshoot so
# every narration the fit accepts also fits the card.
BOOKEND_FIT_TARGET_S = MAX_BOOKEND_NARRATION_S - PACED_OVERSHOOT_TOLERANCE_S - 0.05


def bookend_duration(bookend: LongFormBookend, narration_s: float | None, fps: int) -> float:
    """Card length for its narration; overlong narration is rejected, never truncated."""
    spoken = narration_s if narration_s is not None else bookend.word_count / PREVIEW_WORDS_PER_S
    if spoken > MAX_BOOKEND_NARRATION_S + 1e-6:
        raise StoryQualityError(
            f"title card narration needs {spoken:.2f}s; "
            f"the {MAX_BOOKEND_S:.0f}s card holds {MAX_BOOKEND_NARRATION_S:.2f}s"
        )
    duration = max(spoken + BOOKEND_TAIL_S, MIN_BOOKEND_S)
    return round(duration * fps) / fps


def _latest(count: int | None) -> str:
    return "<5" if count is None else f"{count:,}"


def roster_rows(roster: Sequence[RosterEntry]) -> list[dict[str, Any]]:
    return [
        {
            "name": entry.name,
            "detail": (
                f"{entry.peak_count:,} in {entry.peak_year} → "
                f"{_latest(entry.latest_count)} in {entry.latest_year}"
            ),
            # A suppressed year is only known to be under five, so no percentage.
            "value": "<5" if entry.decline_pct is None else f"−{entry.decline_pct}%",
        }
        for entry in roster
    ]


def sample_bookend_frame(
    bookend: LongFormBookend,
    t: float,
    *,
    opening: bool,
    roster: Sequence[RosterEntry],
    totals: Sequence[tuple[int, int]] = (),
    words: Sequence[WordTiming] = (),
    debug_safe: bool = False,
) -> dict[str, Any]:
    """Props for one ``title`` template frame at ``t`` seconds into the card.

    The opening card is the episode cover, so its headline and roster are fully
    opaque on frame zero and only settle; the closing card follows a chapter and
    brings its content in.
    """
    settle = sample_scalar_track(SETTLE, t)
    headline_alpha = 1.0 if opening else sample_scalar_track(FADE_IN, t)
    rows = roster_rows(roster) if bookend.show_roster else []
    for index, row in enumerate(rows):
        start = ROSTER_START_S + ROSTER_STAGGER_S * index
        reveal = smootherstep((t - start) / ROSTER_FADE_S)
        alpha = 1.0 if opening else reveal
        row["alpha"] = round(alpha, 6)
        row["offset_x"] = round((1.0 - alpha) * 24.0, 6)
        row["rule_progress"] = round(reveal, 6)
    bars: list[dict[str, Any]] = []
    if bookend.show_totals and totals:
        largest = max(total for _, total in totals) or 1
        for index, (year, total) in enumerate(totals):
            start = TOTALS_START_S + TOTALS_STAGGER_S * index
            grow = smootherstep((t - start) / TOTALS_GROW_S)
            bars.append(
                {
                    "label": str(year),
                    "value": f"{total:,}",
                    "fraction": round(grow * total / largest, 6),
                    "tone": "crimson" if index == len(totals) - 1 else "amber",
                    "alpha": round(smootherstep((t - start) / TOTALS_FADE_S), 6),
                }
            )
    captions = caption_state(words, t)
    return {
        "kicker": bookend.kicker,
        "headline": bookend.headline,
        "subhead": bookend.subhead,
        "accent_progress": round(sample_scalar_track(ACCENT, t), 6),
        "headline_alpha": round(headline_alpha, 6),
        "headline_offset_y": round(lerp(0.0, -10.0, settle), 6),
        "subhead_alpha": round(1.0 if opening else sample_scalar_track(SUBHEAD, t), 6),
        "rule_progress": round(sample_scalar_track(RULE, t), 6),
        "roster": rows,
        "totals": bars,
        "captions": {"alpha": captions["alpha"], "text": captions["text"]},
        "footer": {
            "alpha": round(sample_scalar_track(FOOTER, t), 6),
            "site": "nobodynamed.com",
            "cta": "Follow for the history behind names",
            "disclosure": "AI NARRATION",
        },
        "debug_safe": debug_safe,
    }
