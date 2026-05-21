"""Caption compositor — deterministic caption + pinned comment generator."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from nobodynamed_video.compose.lexicon import CaptionFrame, Lexicon, _render_simple
from nobodynamed_video.compose.state import CombinationState
from nobodynamed_video.models import ResolvedHook, VideoContext


class CaptionExhausted(Exception):
    """Raised when constraints cannot be satisfied within regeneration_attempts."""


@dataclass
class ComposedCaption:
    """Output of compose_caption()."""

    caption: str
    pinned_comment: str
    hashtag_set: list[str] = field(default_factory=list)


def combo_hash(tags: list[str]) -> str:
    """SHA-256 of sorted comma-joined tag names — order-independent."""
    return hashlib.sha256(",".join(sorted(tags)).encode()).hexdigest()


def _pick(seed_key: str, n: int) -> int:
    """Deterministic index in [0, n) using BLAKE2b of seed_key."""
    digest = hashlib.blake2b(seed_key.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % n


def _pick_frame(spec_id: str, frames: list[CaptionFrame]) -> CaptionFrame:
    """Select one frame deterministically by spec_id."""
    return frames[_pick(spec_id + "frame", len(frames))]


def _pick_words(spec_id: str, pool: list[str], count: int) -> list[str]:
    """Pick *count* distinct words from *pool* deterministically."""
    chosen: list[str] = []
    for i in range(count * 4):
        idx = _pick(f"{spec_id}emo{i}", len(pool))
        if pool[idx] not in chosen:
            chosen.append(pool[idx])
        if len(chosen) == count:
            break
    return chosen[:count]


def _build_body(frame_text: str, words: list[str]) -> str:
    """Append emotional words after the frame body.

    Multi-word phrases are appended as standalone sentences.
    Single-word adjectives become 'A {word} name.'
    """
    parts = [frame_text.rstrip(". ")]
    for w in words:
        if " " in w:
            parts.append(f"{w.capitalize()}.")
        else:
            parts.append(f"A {w} name.")
    return " ".join(parts)


def _pick_hashtags(
    spec_id: str,
    register: str,
    lexicon: Lexicon,
    state: CombinationState,
    attempt: int,
) -> list[str]:
    """Pick 3–5 hashtags: 1 core + 1 broad + 1–2 emotional + 0–1 trend."""
    core_pool = lexicon.hashtags_for(register, "core")
    broad_pool = lexicon.hashtags_for(register, "broad")
    emotional_pool = lexicon.hashtags_for(register, "emotional")
    trend_pool = [
        h
        for h in lexicon.hashtags_for(register, "trend")
        if h.max_uses_per_week is None or state.tag_uses_this_week(h.tag) < h.max_uses_per_week
    ]

    if not core_pool or not broad_pool or not emotional_pool:
        raise CaptionExhausted(f"Insufficient hashtag pool for register={register!r}")

    seed = f"{spec_id}tags{attempt}"
    core = core_pool[_pick(seed + "core", len(core_pool))].tag
    broad = broad_pool[_pick(seed + "broad", len(broad_pool))].tag

    # Pick first emotional tag (must differ from core and broad).
    emo1_candidates = [h.tag for h in emotional_pool if h.tag not in {core, broad}]
    if not emo1_candidates:
        emo1_candidates = [h.tag for h in emotional_pool]
    emo1 = emo1_candidates[_pick(seed + "emo0", len(emo1_candidates))]

    tags = [core, broad, emo1]

    # Try for a second emotional tag to reach 4 or 5.
    emo2_candidates = [h.tag for h in emotional_pool if h.tag not in set(tags)]
    if emo2_candidates:
        emo2 = emo2_candidates[_pick(seed + "emo1", len(emo2_candidates))]
        tags.append(emo2)

    # Optionally add a trend tag (target up to 5 total).
    if trend_pool and len(tags) < lexicon.constraints.hashtags_max:
        trend_candidates = [h.tag for h in trend_pool if h.tag not in set(tags)]
        if trend_candidates:
            tags.append(trend_candidates[_pick(seed + "trend", len(trend_candidates))])

    return tags


def _pick_pinned(spec_id: str, pillar: str, ctx: dict, lexicon: Lexicon) -> str | None:
    """Select a rendered pinned comment. Returns None if none are available."""
    patterns = lexicon.patterns_for(pillar, ctx)
    if not patterns:
        return None
    return patterns[_pick(spec_id + "pinned", len(patterns))]


def compose_caption(
    spec_id: str,
    hook: ResolvedHook,
    ctx: VideoContext,
    lexicon: Lexicon,
    state: CombinationState,
) -> ComposedCaption:
    """Compose caption, pinned comment, and hashtag set for spec_id.

    Deterministic by spec_id when the state DB is empty. Raises
    CaptionExhausted if constraints cannot be satisfied.
    """
    cfg = lexicon.constraints
    register = hook.voice_register
    pillar = hook.pillar
    ctx_dict = ctx.as_template_context()

    frames = lexicon.frames_for(pillar, ctx_dict)
    if not frames:
        body = hook.caption
    else:
        frame = _pick_frame(spec_id, frames)
        frame_text = _render_simple(frame.template, ctx_dict)
        word_pool = lexicon.words_for(register)
        word_count = cfg.emotional_words_min if len(frame_text) > 80 else cfg.emotional_words_max
        words = _pick_words(spec_id, word_pool, word_count) if word_pool else []
        body = _build_body(frame_text, words)

    pinned = _pick_pinned(spec_id, pillar, ctx_dict, lexicon)
    if pinned is None:
        pinned = "What name should we cover next?"
    if len(pinned) > cfg.pinned_max_chars:
        pinned = pinned[: cfg.pinned_max_chars - 1].rsplit(" ", 1)[0] + "?"

    for attempt in range(cfg.regeneration_attempts):
        tags = _pick_hashtags(spec_id, register, lexicon, state, attempt)
        h = combo_hash(tags)
        if state.is_used(h):
            continue

        hashtag_str = " " + " ".join(f"#{t}" for t in tags)
        caption = body + hashtag_str

        if len(caption) > cfg.caption_max_chars:
            max_body = cfg.caption_max_chars - len(hashtag_str)
            trimmed = body[:max_body].rsplit(" ", 1)[0]
            caption = trimmed + hashtag_str

        if len(caption) > cfg.caption_max_chars:
            continue

        state.record(h, tags, spec_id)
        return ComposedCaption(caption=caption, pinned_comment=pinned, hashtag_set=tags)

    raise CaptionExhausted(
        f"Could not satisfy caption constraints for spec_id={spec_id!r} after {cfg.regeneration_attempts} attempts."
    )
