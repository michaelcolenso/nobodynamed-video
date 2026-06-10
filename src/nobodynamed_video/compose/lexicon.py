"""Lexicon — loads fixtures/captions.yaml and provides typed query methods."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_TEMPLATE_VAR = re.compile(r"\{\{\s*([\w|. ]+)\s*\}\}")
_FILTER_RE = re.compile(r"\|.*")


@dataclass
class Constraints:
    """Runtime-enforced limits for caption composition."""

    caption_max_chars: int = 150
    emotional_words_min: int = 2
    emotional_words_max: int = 3
    hashtags_min: int = 3
    hashtags_max: int = 5
    min_core_hashtags: int = 1
    pinned_max_chars: int = 100
    regeneration_attempts: int = 50


@dataclass
class HashtagEntry:
    """One tag from the hashtag pool."""

    tag: str
    category: str
    registers: list[str]
    active: bool
    max_uses_per_week: int | None = None


@dataclass
class CaptionFrame:
    """One caption body template."""

    id: str
    template: str
    requires_vars: list[str]


def _render_simple(template: str, ctx: dict[str, Any]) -> str:
    """Render {{ var }} and {{ var | filter }} templates using ctx."""

    def replace(m: re.Match[str]) -> str:
        expr = m.group(1)
        parts = [p.strip() for p in expr.split("|")]
        value = ctx.get(parts[0].strip())
        if value is None:
            return "{{MISSING}}"
        for flt in parts[1:]:
            flt = flt.strip()
            if flt == "thousands":
                value = f"{int(value):,}"
        return str(value)

    return _TEMPLATE_VAR.sub(replace, template).strip()


class Lexicon:
    """Typed access to fixtures/captions.yaml."""

    def __init__(
        self,
        constraints: Constraints,
        hashtags_by_category: dict[str, list[HashtagEntry]],
        emotional_words: dict[str, list[str]],
        pinned_patterns_raw: dict[str, list[str]],
        caption_frames_raw: dict[str, list[CaptionFrame]],
    ) -> None:
        """Initialize Lexicon with parsed caption data."""
        self.constraints = constraints
        self._hashtags = hashtags_by_category
        self._words = emotional_words
        self._pinned_raw = pinned_patterns_raw
        self._frames = caption_frames_raw

    @classmethod
    def from_yaml(cls, path: Path) -> Lexicon:
        """Load and parse captions.yaml."""
        yaml = YAML(typ="safe")
        raw: dict[str, Any] = yaml.load(path.read_text())

        c = raw.get("constraints", {})
        constraints = Constraints(
            caption_max_chars=int(c.get("caption_max_chars", 150)),
            emotional_words_min=int(c.get("emotional_words_min", 2)),
            emotional_words_max=int(c.get("emotional_words_max", 3)),
            hashtags_min=int(c.get("hashtags_min", 3)),
            hashtags_max=int(c.get("hashtags_max", 5)),
            min_core_hashtags=int(c.get("min_core_hashtags", 1)),
            pinned_max_chars=int(c.get("pinned_max_chars", 100)),
            regeneration_attempts=int(c.get("regeneration_attempts", 50)),
        )

        hashtags_by_category: dict[str, list[HashtagEntry]] = {}
        for category, entries in raw.get("hashtags", {}).items():
            hashtags_by_category[category] = [
                HashtagEntry(
                    tag=str(e["tag"]),
                    category=category,
                    registers=list(e.get("registers", [])),
                    active=bool(e.get("active", True)),
                    max_uses_per_week=e.get("max_uses_per_week"),
                )
                for e in entries
            ]

        emotional_words: dict[str, list[str]] = {
            reg: [str(w) for w in words] for reg, words in raw.get("emotional_words", {}).items()
        }

        pinned_patterns_raw: dict[str, list[str]] = {
            pillar: [str(p) for p in patterns]
            for pillar, patterns in raw.get("pinned_patterns", {}).items()
        }

        caption_frames_raw: dict[str, list[CaptionFrame]] = {}
        for pillar, frames in raw.get("caption_frames", {}).items():
            caption_frames_raw[pillar] = [
                CaptionFrame(
                    id=str(f["id"]),
                    template=str(f["template"]),
                    requires_vars=list(f.get("requires_vars", [])),
                )
                for f in frames
            ]

        return cls(
            constraints,
            hashtags_by_category,
            emotional_words,
            pinned_patterns_raw,
            caption_frames_raw,
        )

    def hashtags_for(self, register: str, category: str) -> list[HashtagEntry]:
        """Active hashtags in *category* compatible with *register*."""
        return [h for h in self._hashtags.get(category, []) if h.active and register in h.registers]

    def words_for(self, register: str) -> list[str]:
        """Emotional words for *register*."""
        return list(self._words.get(register, []))

    def frames_for(self, pillar: str, ctx: dict[str, Any]) -> list[CaptionFrame]:
        """Caption frames for *pillar* whose requires_vars all resolve in ctx."""
        return [
            frame
            for frame in self._frames.get(pillar, [])
            if all(ctx.get(v) is not None for v in frame.requires_vars)
        ]

    def patterns_for(self, pillar: str, ctx: dict[str, Any]) -> list[str]:
        """Return rendered pinned comment patterns for *pillar*."""
        result = []
        for tmpl in self._pinned_raw.get(pillar, []):
            rendered = _render_simple(tmpl, ctx)
            if "{{MISSING}}" not in rendered and rendered.rstrip().endswith("?"):
                result.append(rendered)
        return result
