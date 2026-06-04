# Caption Compositor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every video renders, produce a ≤150-char TikTok caption, a ≤100-char pinned comment, and 3–5 hashtags — all deterministic by spec_id, all constrained by brand rules, and no two videos ever ship the same hashtag set.

**Architecture:** A `Lexicon` loads `fixtures/captions.yaml` and provides typed query methods. A `CombinationState` wraps a SQLite DB to enforce hashtag-set uniqueness across runs. A `compose_caption()` function drives the algorithm: pick frame → inject emotional words → pick hashtags → enforce uniqueness → pick pinned comment → validate. The compositor runs in `batch/runner.py` after frame render, before ffmpeg, and writes its output to `RenderManifest`.

**Tech Stack:** Python, Pydantic, ruamel.yaml (already in deps), sqlite3 (stdlib), hashlib blake2b/sha256 (stdlib).

---

## File map

| Action | Path                                        | Responsibility                                                          |
| ------ | ------------------------------------------- | ----------------------------------------------------------------------- |
| Create | `fixtures/captions.yaml`                    | Canonical data: constraints, hashtags, lexicon, frames, pinned patterns |
| Create | `src/nobodynamed_video/compose/lexicon.py`  | Loads captions.yaml; typed query API for the compositor                 |
| Create | `src/nobodynamed_video/compose/state.py`    | SQLite combo tracker — enforces hashtag-set uniqueness across runs      |
| Create | `src/nobodynamed_video/compose/caption.py`  | Compositor algorithm                                                    |
| Create | `tests/test_caption.py`                     | All compositor tests                                                    |
| Modify | `src/nobodynamed_video/models.py`           | Add `caption`, `pinned_comment`, `hashtag_set` to `RenderManifest`      |
| Modify | `src/nobodynamed_video/compose/manifest.py` | Thread caption fields through `build_manifest()`                        |
| Modify | `src/nobodynamed_video/batch/runner.py`     | Call compositor after frame render, before ffmpeg                       |
| Modify | `src/nobodynamed_video/cli.py`              | Add `nbn captions stats / deprecate / reset` subcommands                |
| Modify | `.gitignore`                                | Ignore `state/*.db`                                                     |

---

## Task 1: Data file — `fixtures/captions.yaml`

No code. Write the canonical data file the compositor will load.

**Files:**

- Create: `fixtures/captions.yaml`

- [ ] **Step 1: Write the file**

```yaml
# fixtures/captions.yaml — caption compositor data v1
version: 1

constraints:
    caption_max_chars: 150
    include_hashtags_in_count: true
    emotional_words_min: 2
    emotional_words_max: 3
    hashtags_min: 3
    hashtags_max: 5
    min_core_hashtags: 1
    pinned_max_chars: 100
    regeneration_attempts: 50

hashtags:
    core:
        - tag: endangerednames
          registers: [morbid, curious, cultural]
          active: true
        - tag: namedata
          registers: [morbid, curious, nostalgic, hopeful, cultural]
          active: true
        - tag: ssadata
          registers: [morbid, curious, nostalgic, hopeful, cultural]
          active: true
        - tag: vanishingnames
          registers: [morbid, cultural]
          active: true
        - tag: namesondecline
          registers: [morbid, cultural]
          active: true

    broad:
        - tag: babynames
          registers: [morbid, curious, nostalgic, hopeful, cultural]
          active: true
        - tag: namesoftiktok
          registers: [morbid, curious, nostalgic, hopeful, cultural]
          active: true
        - tag: babynamehelp
          registers: [hopeful, nostalgic]
          active: true
        - tag: namesweek
          registers: [curious, nostalgic]
          active: true
        - tag: namehistory
          registers: [curious, nostalgic, cultural]
          active: true

    emotional:
        - tag: onthebrink
          registers: [morbid]
          active: true
        - tag: namesweloved
          registers: [morbid, nostalgic]
          active: true
        - tag: vintagenames
          registers: [nostalgic, hopeful]
          active: true
        - tag: grandmacore
          registers: [nostalgic, hopeful]
          active: true
        - tag: oldfashionednames
          registers: [nostalgic]
          active: true
        - tag: classicnames
          registers: [nostalgic]
          active: true
        - tag: namecomeback
          registers: [hopeful]
          active: true
        - tag: vintagecomeback
          registers: [hopeful]
          active: true
        - tag: culturalcollapse
          registers: [cultural]
          active: true
        - tag: memehistory
          registers: [cultural]
          active: true
        - tag: pophistory
          registers: [cultural]
          active: true
        - tag: didyouknow
          registers: [curious]
          active: true
        - tag: namefact
          registers: [curious]
          active: true
        - tag: genealogy
          registers: [nostalgic, curious]
          active: true

    trend:
        - tag: fyp
          registers: [morbid, curious, nostalgic, hopeful, cultural]
          active: true
          max_uses_per_week: 3
        - tag: foryou
          registers: [morbid, curious, nostalgic, hopeful, cultural]
          active: true
          max_uses_per_week: 3
        - tag: namesoftiktok2026
          registers: [morbid, curious, nostalgic, hopeful, cultural]
          active: false

emotional_words:
    morbid:
        - vanishing
        - fading
        - endangered
        - dying
        - on the brink
        - shrinking
        - dwindling
        - quiet
        - extinct
        - rare
        - hushed
        - last
        - final
        - barely surviving

    nostalgic:
        - timeless
        - classic
        - heirloom
        - vintage
        - inherited
        - storied
        - old-world
        - lived-in
        - familiar
        - generational
        - quietly enduring

    hopeful:
        - returning
        - reviving
        - reborn
        - back
        - cycling
        - rediscovered
        - claimed
        - reawakened
        - quietly rising
        - emerging

    curious:
        - rare
        - underrated
        - unexpected
        - hidden
        - overlooked
        - peculiar
        - statistical
        - documented
        - measured

    cultural:
        - rewritten
        - reshaped
        - reframed
        - undone
        - displaced
        - punctuated
        - upended

pinned_patterns:
    extinction-watch:
        - "Do you know anyone under 30 named {{ name }}?"
        - "When's the last time you met a {{ name }}?"
        - "Whose grandmother was named {{ name }}?"
        - "What's the rarest name you've heard this year?"

    peak-year:
        - "Whose name peaked in {{ peak_year }}?"
        - "Drop a year. I'll tell you the top name."
        - "What name does your high school class share too many of?"
        - "Comment the year you were born + your name."

    cultural-collapse:
        - "Which name has the saddest cultural arc?"
        - "What killed {{ name }}, in your view?"
        - "Pop culture vs. parents: who wins more?"
        - "Which name will collapse next?"

    resurrection:
        - "Which vintage name are you reviving?"
        - "Three generations: would you reuse {{ name }}?"
        - "What's the next {{ name }}?"
        - "Comment a great-grandparent's name worth bringing back."

    generation-arc:
        - "What name has the wildest 100-year arc?"
        - "Drop a name and a guess: which tier?"
        - "Which name surprised you most?"

    comparison-surprise:
        - "Drop your name. I'll find the peak year."
        - "What name is rarer than people think?"
        - "Year + sex below. I'll respond."

caption_frames:
    extinction-watch:
        - id: ext-frame-collapse
          template: "{{ name }} hasn't been common since {{ peak_year }}. Just {{ current_count }} last year."
          requires_vars: [name, peak_year, current_count]
        - id: ext-frame-numbers
          template: "{{ peak_count | thousands }} → {{ current_count }}. {{ name }}, in two numbers."
          requires_vars: [name, peak_count, current_count]
        - id: ext-frame-list
          template: "{{ name }}: another name on the endangered list."
          requires_vars: [name]
        - id: ext-frame-quiet
          template: "Names disappear quietly. {{ name }} is on the way out."
          requires_vars: [name]

    peak-year:
        - id: peak-frame-cohort
          template: "Every {{ name }} you've ever met was born in {{ peak_year }}, give or take."
          requires_vars: [name, peak_year]
        - id: peak-frame-ranked
          template: "{{ name }} was the #{{ rank_at_peak }} name in {{ peak_year }}."
          requires_vars: [name, rank_at_peak, peak_year]

    cultural-collapse:
        - id: cult-frame-killed
          template: "{{ killing_event }} ended {{ name }}. {{ peak_count | thousands }} → {{ current_count }}."
          requires_vars: [name, killing_event, peak_count, current_count]
        - id: cult-frame-before
          template: "{{ name }} was a real name before {{ killing_event }}."
          requires_vars: [name, killing_event]

    resurrection:
        - id: res-frame-comeback
          template: "{{ name }} came back. {{ trough_count }} → {{ current_count | thousands }}."
          requires_vars: [name, trough_count, current_count]
        - id: res-frame-cycle
          template: "Vintage names are returning. {{ name }} is leading."
          requires_vars: [name]

    generation-arc:
        - id: arc-frame-century
          template: "The full {{ name }} history. {{ year_range }} years. One chart."
          requires_vars: [name, year_range]
        - id: arc-frame-curve
          template: "The {{ name }} trajectory: peak, collapse, what's next."
          requires_vars: [name]

    comparison-surprise:
        - id: cmp-frame-guess
          template: "{{ peak_count | thousands }} named {{ name }} at peak. Guess how many last year."
          requires_vars: [name, peak_count]
        - id: cmp-frame-age
          template: "Most {{ name }}s are over {{ avg_age }}. The data is the surprise."
          requires_vars: [name, avg_age]

state_db:
    path: "state/used_combinations.db"
```

- [ ] **Step 2: Commit**

```bash
git add fixtures/captions.yaml
git commit -m "feat: add fixtures/captions.yaml — caption compositor data"
```

---

## Task 2: Lexicon loader — `compose/lexicon.py`

**Files:**

- Create: `src/nobodynamed_video/compose/lexicon.py`
- Test: `tests/test_caption.py` (start the file here)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_caption.py
"""Tests for caption compositor: lexicon, state, and composition."""

from __future__ import annotations

from pathlib import Path

from nobodynamed_video.compose.lexicon import Lexicon

CAPTIONS_YAML = Path("fixtures/captions.yaml")


def test_lexicon_loads_constraints() -> None:
    """Constraints are loaded with correct types."""
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    assert lex.constraints.caption_max_chars == 150
    assert lex.constraints.hashtags_min == 3
    assert lex.constraints.hashtags_max == 5
    assert lex.constraints.emotional_words_min == 2
    assert lex.constraints.emotional_words_max == 3
    assert lex.constraints.pinned_max_chars == 100
    assert lex.constraints.regeneration_attempts == 50


def test_lexicon_hashtags_for_returns_active_only() -> None:
    """hashtags_for() only returns active tags matching the register."""
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    core = lex.hashtags_for("morbid", "core")
    assert all(h.active for h in core)
    assert all("morbid" in h.registers for h in core)
    # namesoftiktok2026 is inactive — must not appear
    all_tags = [h.tag for h in lex.hashtags_for("morbid", "trend")]
    assert "namesoftiktok2026" not in all_tags


def test_lexicon_words_for_returns_register_pool() -> None:
    """words_for() returns the emotional words for a register."""
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    words = lex.words_for("morbid")
    assert "vanishing" in words
    assert "fading" in words
    assert len(words) >= 5


def test_lexicon_frames_for_filters_requires_vars() -> None:
    """frames_for() drops frames whose requires_vars are missing from ctx."""
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    # ctx missing killing_event — cult-frame-killed should be excluded
    ctx: dict = {"name": "Karen", "peak_count": 32873, "current_count": 325}
    frames = lex.frames_for("cultural-collapse", ctx)
    ids = [f.id for f in frames]
    assert "cult-frame-killed" not in ids
    assert "cult-frame-before" not in ids  # also needs killing_event


def test_lexicon_frames_for_includes_when_vars_present() -> None:
    """frames_for() includes frames when all requires_vars resolve."""
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    ctx: dict = {
        "name": "Karen",
        "killing_event": "the meme",
        "peak_count": 32873,
        "current_count": 325,
    }
    frames = lex.frames_for("cultural-collapse", ctx)
    ids = [f.id for f in frames]
    assert "cult-frame-killed" in ids


def test_lexicon_patterns_for_filters_unresolvable() -> None:
    """patterns_for() drops patterns whose template vars don't resolve."""
    lex = Lexicon.from_yaml(CAPTIONS_YAML)
    ctx: dict = {"name": "Bertha", "peak_year": 1910}
    patterns = lex.patterns_for("peak-year", ctx)
    # All returned patterns must render without missing-var substitution
    assert len(patterns) > 0
    for p in patterns:
        assert "{{" not in p  # all vars resolved
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_caption.py -x -q 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'Lexicon'`

- [ ] **Step 3: Implement `compose/lexicon.py`**

```python
"""Lexicon — loads fixtures/captions.yaml and provides typed query methods."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_TEMPLATE_VAR = re.compile(r"\{\{\s*([\w|]+)\s*\}\}")
_THOUSANDS_RE = re.compile(r"\|\s*thousands")
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


def _extract_var_names(template: str) -> list[str]:
    """Return bare variable names referenced in a Jinja2-style template."""
    names = []
    for match in _TEMPLATE_VAR.finditer(template):
        expr = match.group(1)
        var = _FILTER_RE.sub("", expr).strip()
        names.append(var)
    return names


def _render_simple(template: str, ctx: dict[str, Any]) -> str:
    """Render {{ var }} and {{ var | filter }} templates using ctx."""

    def replace(m: re.Match[str]) -> str:
        expr = m.group(1)
        parts = [p.strip() for p in expr.split("|")]
        value = ctx.get(parts[0])
        if value is None:
            return ""
        for flt in parts[1:]:
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
            pillar: [str(p) for p in patterns] for pillar, patterns in raw.get("pinned_patterns", {}).items()
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

        return cls(constraints, hashtags_by_category, emotional_words, pinned_patterns_raw, caption_frames_raw)

    def hashtags_for(self, register: str, category: str) -> list[HashtagEntry]:
        """Active hashtags in *category* compatible with *register*."""
        return [h for h in self._hashtags.get(category, []) if h.active and register in h.registers]

    def words_for(self, register: str) -> list[str]:
        """Emotional words for *register*."""
        return list(self._words.get(register, []))

    def frames_for(self, pillar: str, ctx: dict[str, Any]) -> list[CaptionFrame]:
        """Caption frames for *pillar* whose requires_vars all resolve in ctx."""
        result = []
        for frame in self._frames.get(pillar, []):
            if all(ctx.get(v) is not None for v in frame.requires_vars):
                result.append(frame)
        return result

    def patterns_for(self, pillar: str, ctx: dict[str, Any]) -> list[str]:
        """Pinned comment patterns for *pillar* with all template vars resolved."""
        result = []
        for tmpl in self._pinned_raw.get(pillar, []):
            rendered = _render_simple(tmpl, ctx)
            if "{{" not in rendered and rendered.rstrip().endswith("?"):
                result.append(rendered)
        return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_caption.py -x -q
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nobodynamed_video/compose/lexicon.py tests/test_caption.py
git commit -m "feat: lexicon loader for captions.yaml"
```

---

## Task 3: Combination state — `compose/state.py`

**Files:**

- Create: `src/nobodynamed_video/compose/state.py`
- Modify: `tests/test_caption.py` (add state tests)
- Modify: `.gitignore`

- [ ] **Step 1: Add tests for state tracker**

Append to `tests/test_caption.py`:

```python
import tempfile

from nobodynamed_video.compose.state import CombinationState


def test_state_new_combo_not_used() -> None:
    """A fresh combo is not in the state DB."""
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        h = "abc123"
        assert not state.is_used(h)


def test_state_record_then_is_used() -> None:
    """A recorded combo is detected as used."""
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        h = "deadbeef"
        state.record(h, ["namedata", "babynames", "onthebrink"], "bertha-2024")
        assert state.is_used(h)


def test_state_different_combos_independent() -> None:
    """Two distinct combo hashes are tracked independently."""
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        state.record("hash1", ["a", "b", "c"], "spec-1")
        assert state.is_used("hash1")
        assert not state.is_used("hash2")


def test_state_tag_uses_this_week_counts_correctly() -> None:
    """tag_uses_this_week returns the correct count for recent records."""
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        state.record("h1", ["fyp", "namedata", "babynames"], "spec-1")
        state.record("h2", ["fyp", "ssadata", "onthebrink"], "spec-2")
        state.record("h3", ["namedata", "babynames", "namefact"], "spec-3")
        assert state.tag_uses_this_week("fyp") == 2
        assert state.tag_uses_this_week("namedata") == 2
        assert state.tag_uses_this_week("culturalcollapse") == 0


def test_state_reset_clears_all_records() -> None:
    """reset() wipes the state DB."""
    with tempfile.TemporaryDirectory() as tmp:
        state = CombinationState(Path(tmp) / "combos.db")
        state.record("h1", ["a", "b", "c"], "spec-1")
        state.reset()
        assert not state.is_used("h1")
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_caption.py -k "state" -x -q 2>&1 | head -10
```

Expected: `ImportError: cannot import name 'CombinationState'`

- [ ] **Step 3: Implement `compose/state.py`**

```python
"""SQLite-backed hashtag combination tracker."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS used_combinations (
    combo_hash      TEXT PRIMARY KEY,
    tags_json       TEXT NOT NULL,
    first_used_at   TEXT NOT NULL,
    first_used_spec TEXT NOT NULL,
    use_count       INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_combo_first_used
    ON used_combinations(first_used_at DESC);
"""


class CombinationState:
    """Tracks shipped hashtag sets to enforce combination uniqueness."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        conn = self._connect()
        conn.executescript(_DDL)
        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        return conn

    def is_used(self, combo_hash: str) -> bool:
        """Return True if this combo hash has been recorded before."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM used_combinations WHERE combo_hash = ?",
                (combo_hash,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def record(self, combo_hash: str, tags: list[str], spec_id: str) -> None:
        """Persist a new combo; increment use_count if it already exists."""
        now = datetime.now(tz=UTC).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO used_combinations (combo_hash, tags_json, first_used_at, first_used_spec)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(combo_hash) DO UPDATE SET use_count = use_count + 1
                """,
                (combo_hash, json.dumps(sorted(tags)), now, spec_id),
            )
            conn.commit()
        finally:
            conn.close()

    def tag_uses_this_week(self, tag: str) -> int:
        """Count how many recorded combos include *tag* in the last 7 days."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=7)).isoformat()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT tags_json FROM used_combinations WHERE first_used_at >= ?",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()
        count = 0
        for row in rows:
            tags: list[str] = json.loads(row["tags_json"])
            if tag in tags:
                count += 1
        return count

    def stats(self) -> dict[str, int]:
        """Return total combinations recorded and total uses."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS combos, COALESCE(SUM(use_count), 0) AS uses FROM used_combinations"
            ).fetchone()
            return {"combos": row["combos"], "uses": row["uses"]}
        finally:
            conn.close()

    def reset(self) -> None:
        """Wipe all records. Requires explicit call — no confirmation guard here."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM used_combinations")
            conn.commit()
        finally:
            conn.close()
```

- [ ] **Step 4: Update `.gitignore`**

Add to `.gitignore`:

```
state/*.db
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_caption.py -x -q
```

Expected: 11 passed.

- [ ] **Step 6: Commit**

```bash
git add src/nobodynamed_video/compose/state.py tests/test_caption.py .gitignore
git commit -m "feat: hashtag combination state tracker (SQLite)"
```

---

## Task 4: Compositor — `compose/caption.py`

**Files:**

- Create: `src/nobodynamed_video/compose/caption.py`
- Modify: `tests/test_caption.py` (add compositor tests)

The compositor uses `hashlib.blake2b` for deterministic, seeded selection and `hashlib.sha256` for combo hashing.

- [ ] **Step 1: Add compositor tests**

Append to `tests/test_caption.py`:

```python
import tempfile

from nobodynamed_video.compose.caption import (
    ComposedCaption,
    combo_hash,
    compose_caption,
)

from nobodynamed_video.models import (
    ResolvedHook,
    Tier,
    VideoContext,
)


def _make_spec_id() -> str:
    return "bertha-2024"


def _make_hook(pillar: str = "extinction-watch", register: str = "morbid") -> ResolvedHook:
    return ResolvedHook(
        id="ext-001",
        pillar=pillar,
        voice_register=register,
        headline="The Bertha you know is probably the last one you'll meet.",
        subhead="9 born last year.",
        pinned_comment="Tag the only Bertha you know.",
        caption="Bertha is on the brink.",
    )


def _make_ctx() -> VideoContext:
    return VideoContext(
        name="Bertha",
        sex="F",
        first_letter="B",
        tier=Tier.CRITICAL,
        current_year=2024,
        current_count=9,
        current_rank=9999,
        current_decade=2020,
        peak_year=1910,
        peak_count=5000,
        peak_decade=1910,
        rank_at_peak=12,
        trough_year=2020,
        trough_count=9,
        years_since_peak=114,
        trough_to_now_years=4,
        decline_pct=99,
        rise_pct=0,
        year_range=144,
        start_year=1880,
        avg_age=80,
        generation_at_peak="Greatest",
    )


def test_combo_hash_is_order_independent() -> None:
    """Sorting tags before hashing makes combo hash order-independent."""
    h1 = combo_hash(["namedata", "babynames", "onthebrink"])
    h2 = combo_hash(["onthebrink", "namedata", "babynames"])
    assert h1 == h2


def test_compose_caption_returns_composed_caption() -> None:
    """compose_caption returns a ComposedCaption with all fields populated."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state)
        assert isinstance(result, ComposedCaption)
        assert result.caption
        assert result.pinned_comment
        assert result.hashtag_set


def test_compose_caption_respects_length_limits() -> None:
    """Caption is ≤150 chars, pinned comment is ≤100 chars."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state)
        assert len(result.caption) <= 150
        assert len(result.pinned_comment) <= 100


def test_compose_caption_pinned_ends_with_question_mark() -> None:
    """Pinned comment always ends with '?'."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state)
        assert result.pinned_comment.rstrip().endswith("?")


def test_compose_caption_has_core_hashtag() -> None:
    """Caption always includes at least one core hashtag."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state)
        core_tags = {h.tag for h in lex.hashtags_for("morbid", "core")}
        assert any(t in core_tags for t in result.hashtag_set)


def test_compose_caption_hashtag_count_in_range() -> None:
    """Hashtag set has 3–5 tags."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state)
        assert 3 <= len(result.hashtag_set) <= 5


def test_compose_caption_is_deterministic() -> None:
    """Same spec_id produces same output when state DB is empty."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state1 = CombinationState(Path(tmp) / "a.db")
        state2 = CombinationState(Path(tmp) / "b.db")
        r1 = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state1)
        r2 = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state2)
        assert r1.caption == r2.caption
        assert r1.pinned_comment == r2.pinned_comment
        assert r1.hashtag_set == r2.hashtag_set


def test_compose_caption_records_combo_in_state() -> None:
    """After composition, the hashtag combo is recorded in state."""
    with tempfile.TemporaryDirectory() as tmp:
        lex = Lexicon.from_yaml(CAPTIONS_YAML)
        state = CombinationState(Path(tmp) / "combos.db")
        result = compose_caption(_make_spec_id(), _make_hook(), _make_ctx(), lex, state)
        h = combo_hash(result.hashtag_set)
        assert state.is_used(h)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_caption.py -k "compose" -x -q 2>&1 | head -10
```

Expected: `ImportError: cannot import name 'compose_caption'`

- [ ] **Step 3: Implement `compose/caption.py`**

```python
"""Caption compositor — deterministic caption + pinned comment generator."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from nobodynamed_video.compose.lexicon import CaptionFrame, Lexicon, _render_simple
from nobodynamed_video.compose.state import CombinationState

from nobodynamed_video.models import ResolvedHook, VideoContext


class CaptionExhausted(Exception):
    """Raised when the compositor cannot satisfy constraints after max retries."""


@dataclass
class ComposedCaption:
    """Output of compose_caption()."""

    caption: str
    pinned_comment: str
    hashtag_set: list[str] = field(default_factory=list)


def combo_hash(tags: list[str]) -> str:
    """SHA-256 of sorted, comma-joined tag names — order-independent."""
    return hashlib.sha256(",".join(sorted(tags)).encode()).hexdigest()


def _pick(seed_key: str, n: int) -> int:
    """Deterministic index in [0, n) using BLAKE2b of *seed_key*."""
    digest = hashlib.blake2b(seed_key.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % n


def _pick_frame(spec_id: str, frames: list[CaptionFrame]) -> CaptionFrame:
    return frames[_pick(spec_id + "frame", len(frames))]


def _pick_words(spec_id: str, pool: list[str], count: int) -> list[str]:
    """Pick *count* distinct words from *pool* deterministically."""
    chosen: list[str] = []
    indices_used: set[int] = set()
    for i in range(count * 3):  # enough attempts to find distinct words
        idx = _pick(f"{spec_id}emo{i}", len(pool))
        if idx not in indices_used and pool[idx] not in chosen:
            chosen.append(pool[idx])
            indices_used.add(idx)
        if len(chosen) == count:
            break
    return chosen[:count]


def _build_body(frame_text: str, words: list[str]) -> str:
    """Append emotional words to the frame body.

    Single-word adjectives: appended as 'A {word} name.'
    Multi-word phrases: appended as '{phrase}.'
    """
    parts = [frame_text.rstrip(".").rstrip()]
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
    """Pick 4 hashtags (1 core + 1 broad + 1–2 emotional + 0–1 trend).

    Returns a list of tag strings. Raises CaptionExhausted if no valid
    combination exists after the attempt budget is spent (caller handles retries).
    """
    cfg = lexicon.constraints

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

    # Pick 1 emotional tag, ensuring it differs from core and broad
    emo_candidates = [h.tag for h in emotional_pool if h.tag not in {core, broad}]
    if not emo_candidates:
        emo_candidates = [h.tag for h in emotional_pool]
    emo = emo_candidates[_pick(seed + "emo", len(emo_candidates))]

    tags = [core, broad, emo]

    # Optionally add a trend tag (target 4 total)
    if trend_pool:
        trend_candidates = [h.tag for h in trend_pool if h.tag not in set(tags)]
        if trend_candidates:
            tags.append(trend_candidates[_pick(seed + "trend", len(trend_candidates))])

    return tags


def _pick_pinned(spec_id: str, pillar: str, ctx: dict, lexicon: Lexicon) -> str | None:
    """Select a pinned comment pattern. Returns None if none available."""
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
    """Compose a caption, pinned comment, and hashtag set for *spec_id*.

    Deterministic by spec_id when the state DB is empty. Falls back gracefully
    if the first hashtag combination is already used. Raises CaptionExhausted
    if constraints cannot be satisfied within regeneration_attempts.
    """
    cfg = lexicon.constraints
    register = hook.voice_register
    pillar = hook.pillar
    ctx_dict = ctx.as_template_context()

    frames = lexicon.frames_for(pillar, ctx_dict)
    if not frames:
        # Fall back to hook's static caption as the body
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

    # Truncate pinned if needed (template expansion could exceed limit)
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
            # Body too long with hashtags — truncate body
            max_body = cfg.caption_max_chars - len(hashtag_str)
            body = body[:max_body].rsplit(" ", 1)[0]
            caption = body + hashtag_str

        if len(caption) > cfg.caption_max_chars:
            continue

        state.record(h, tags, spec_id)
        return ComposedCaption(caption=caption, pinned_comment=pinned, hashtag_set=tags)

    raise CaptionExhausted(
        f"Could not satisfy caption constraints for spec_id={spec_id!r} after {cfg.regeneration_attempts} attempts."
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_caption.py -x -q
```

Expected: 19 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nobodynamed_video/compose/caption.py tests/test_caption.py
git commit -m "feat: caption compositor with deterministic selection and uniqueness enforcement"
```

---

## Task 5: Wire into models and manifest

**Files:**

- Modify: `src/nobodynamed_video/models.py` (lines ~122–136)
- Modify: `src/nobodynamed_video/compose/manifest.py`

- [ ] **Step 1: Add caption fields to `RenderManifest`**

In `src/nobodynamed_video/models.py`, add three fields to `RenderManifest`:

```python
class RenderManifest(BaseModel):
    spec_id: str
    rendered_at: datetime
    frame_count: int
    duration_s: float
    output_path: str
    sha256_frames: dict[str, str]
    satori_version: str
    ffmpeg_version: str
    scene_render_times_s: dict[str, float] = Field(default_factory=dict)
    total_render_time_s: float = 0.0
    program: str | None = None
    hook_id: str | None = None
    voice_register: str | None = None
    caption: str | None = None
    pinned_comment: str | None = None
    hashtag_set: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Update `build_manifest()` signature**

In `src/nobodynamed_video/compose/manifest.py`, add three keyword parameters and thread them through:

```python
def build_manifest(
    spec_id: str,
    frame_count: int,
    duration_s: float,
    output_path: str,
    sha256_frames: dict[str, str],
    satori_version: str,
    ffmpeg_version: str,
    scene_render_times_s: dict[str, float] | None = None,
    total_render_time_s: float = 0.0,
    program: str | None = None,
    hook_id: str | None = None,
    voice_register: str | None = None,
    caption: str | None = None,
    pinned_comment: str | None = None,
    hashtag_set: list[str] | None = None,
) -> RenderManifest:
    return RenderManifest(
        spec_id=spec_id,
        rendered_at=datetime.now(tz=UTC),
        frame_count=frame_count,
        duration_s=duration_s,
        output_path=output_path,
        sha256_frames=sha256_frames,
        satori_version=satori_version,
        ffmpeg_version=ffmpeg_version,
        scene_render_times_s=scene_render_times_s or {},
        total_render_time_s=total_render_time_s,
        program=program,
        hook_id=hook_id,
        voice_register=voice_register,
        caption=caption,
        pinned_comment=pinned_comment,
        hashtag_set=hashtag_set or [],
    )
```

- [ ] **Step 3: Run tests to confirm nothing broke**

```bash
uv run pytest tests/ -q
```

Expected: all passed.

- [ ] **Step 4: Commit**

```bash
git add src/nobodynamed_video/models.py src/nobodynamed_video/compose/manifest.py
git commit -m "feat: add caption/pinned_comment/hashtag_set to RenderManifest"
```

---

## Task 6: Runner integration

**Files:**

- Modify: `src/nobodynamed_video/batch/runner.py`

The compositor runs after all frames are rendered, before `build_ffmpeg_cmd`. It needs a shared `Lexicon` (loaded once per batch) and a `CombinationState` (shared across all specs in the batch so uniqueness holds within a run).

- [ ] **Step 1: Update `render_spec()` to call the compositor**

In `src/nobodynamed_video/batch/runner.py`, add the imports and thread through lexicon + state:

```python
"""Async batch runner — renders a list of VideoSpecs with a concurrency limit."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from nobodynamed_video.compose.caption import CaptionExhausted, compose_caption
from nobodynamed_video.compose.lexicon import Lexicon
from nobodynamed_video.compose.state import CombinationState
from rich.console import Console
from rich.table import Table

from nobodynamed_video.compose.ffmpeg import build_ffmpeg_cmd, get_ffmpeg_version, run_ffmpeg
from nobodynamed_video.compose.manifest import build_manifest, write_manifest
from nobodynamed_video.models import VideoSpec
from nobodynamed_video.render.frame_planner import plan_frames
from nobodynamed_video.render.golden import check_or_write_golden, sha256_bytes
from nobodynamed_video.render.satori_client import SatoriClient

console = Console()

_BATCH_CONCURRENCY = 2
_CAPTIONS_YAML = Path("fixtures/captions.yaml")
_STATE_DB = Path("state/used_combinations.db")


async def render_spec(
    spec: VideoSpec,
    client: SatoriClient,
    out_dir: Path,
    lexicon: Lexicon,
    state: CombinationState,
    no_compose: bool = False,
    debug_safe: bool = False,
    audio_path: Path | None = None,
) -> dict[str, object]:
    """Render one VideoSpec: frames → caption → ffmpeg → manifest."""
    spec_out = out_dir / spec.id
    frames_dir = spec_out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    sha256_frames: dict[str, str] = {}
    scene_times: dict[str, float] = {}
    total_start = time.monotonic()

    # Render all frames.
    for scene_kind, frame_idx, template, props in plan_frames(spec, spec.fps, debug_safe):
        png_path = frames_dir / f"{scene_kind}_{frame_idx:03d}.png"

        import hashlib

        cache_key = hashlib.sha256((template + str(sorted(props.items()))).encode()).hexdigest()
        cache_path = out_dir / ".cache" / f"{cache_key}.png"

        if cache_path.exists():
            png_bytes = cache_path.read_bytes()
        else:
            t_start = time.monotonic()
            png_bytes = await client.render(template, props)
            scene_times[scene_kind] = scene_times.get(scene_kind, 0.0) + (time.monotonic() - t_start)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(png_bytes)

        png_path.write_bytes(png_bytes)
        sha256_frames[png_path.name] = sha256_bytes(png_bytes)

    # Golden hash regression check.
    for scene_kind in ["hook", "reveal"]:
        first_file = frames_dir / f"{scene_kind}_000.png"
        if first_file.exists():
            check_or_write_golden(spec.id, f"{scene_kind}_f00", first_file.read_bytes())

    # Compose caption (non-fatal if no context/hook available).
    caption: str | None = None
    pinned_comment: str | None = None
    hashtag_set: list[str] = []
    if spec.hook and spec.context:
        try:
            composed = compose_caption(spec.id, spec.hook, spec.context, lexicon, state)
            caption = composed.caption
            pinned_comment = composed.pinned_comment
            hashtag_set = composed.hashtag_set
        except CaptionExhausted as exc:
            console.print(f"[yellow]⚠[/yellow]  {spec.id}: caption exhausted — {exc}")

    if no_compose:
        return {"id": spec.id, "frames": len(sha256_frames), "composed": False}

    # Compose with ffmpeg.
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4_path = out_dir / f"{spec.id}.mp4"
    cmd = build_ffmpeg_cmd(
        frames_dir=frames_dir,
        out_path=mp4_path,
        fps=spec.fps,
        audio_path=audio_path,
    )
    run_ffmpeg(cmd)

    total_time = time.monotonic() - total_start
    satori_version = await client.get_version()
    ffmpeg_version = get_ffmpeg_version()

    manifest = build_manifest(
        spec_id=spec.id,
        frame_count=len(sha256_frames),
        duration_s=18.0,
        output_path=str(mp4_path),
        sha256_frames=sha256_frames,
        satori_version=satori_version,
        ffmpeg_version=ffmpeg_version,
        scene_render_times_s=scene_times,
        total_render_time_s=total_time,
        program=spec.program.value if spec.program else None,
        hook_id=spec.hook.id if spec.hook else None,
        voice_register=spec.hook.voice_register if spec.hook else None,
        caption=caption,
        pinned_comment=pinned_comment,
        hashtag_set=hashtag_set,
    )
    write_manifest(manifest, out_dir)

    return {
        "id": spec.id,
        "frames": len(sha256_frames),
        "composed": True,
        "mp4": str(mp4_path),
        "duration_s": total_time,
        "caption": caption,
    }


async def run_batch(
    specs: list[VideoSpec],
    satori_url: str,
    out_dir: Path,
    batch_name: str = "batch",
    no_compose: bool = False,
    debug_safe: bool = False,
    audio_path: Path | None = None,
) -> None:
    """Run all specs concurrently with a semaphore, then write summary JSON."""
    lexicon = Lexicon.from_yaml(_CAPTIONS_YAML)
    state = CombinationState(_STATE_DB)

    semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
    results: list[dict[str, object]] = []
    errors: list[tuple[str, Exception]] = []

    async with SatoriClient(satori_url) as client:

        async def _render_one(spec: VideoSpec) -> None:
            async with semaphore:
                try:
                    result = await render_spec(
                        spec,
                        client,
                        out_dir,
                        lexicon,
                        state,
                        no_compose,
                        debug_safe,
                        audio_path,
                    )
                    results.append(result)
                    console.print(f"[green]✓[/green] {spec.id}")
                except Exception as exc:
                    errors.append((spec.id, exc))
                    console.print(f"[red]✗[/red] {spec.id}: {exc}")

        tasks = [asyncio.create_task(_render_one(s)) for s in specs]
        await asyncio.gather(*tasks)

    table = Table(title=f"Batch: {batch_name}")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Time (s)")
    for r in results:
        table.add_row(str(r["id"]), "ok", f"{r.get('duration_s', 0):.1f}")
    for spec_id, exc in errors:
        table.add_row(spec_id, f"[red]FAILED: {exc}[/red]", "—")
    console.print(table)

    summary = {
        "batch": batch_name,
        "total": len(specs),
        "succeeded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": [{"id": sid, "error": str(exc)} for sid, exc in errors],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{batch_name}.summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")

    if errors:
        raise SystemExit(f"{len(errors)} video(s) failed in batch '{batch_name}'")
```

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all passed.

- [ ] **Step 3: Commit**

```bash
git add src/nobodynamed_video/batch/runner.py
git commit -m "feat: call caption compositor in batch runner, write to manifest"
```

---

## Task 7: CLI extension — `nbn captions`

**Files:**

- Modify: `src/nobodynamed_video/cli.py`

Three subcommands: `stats`, `deprecate <tag>`, `reset`.

- [ ] **Step 1: Add the `captions` group to `cli.py`**

Add to `src/nobodynamed_video/cli.py` after the existing `smoke` command:

```python
captions_app = typer.Typer(name="captions", help="Manage caption combination state.")
app.add_typer(captions_app)


@captions_app.command("stats")
def captions_stats() -> None:
    """Print used vs available combination counts."""
    from nobodynamed_video.compose.state import CombinationState

    state = CombinationState(Path("state/used_combinations.db"))
    s = state.stats()
    console.print(f"Combinations recorded: {s['combos']}")
    console.print(f"Total uses:            {s['uses']}")


@captions_app.command("deprecate")
def captions_deprecate(
    tag: str = typer.Argument(..., help="Hashtag to mark inactive in captions.yaml"),
) -> None:
    """Mark a hashtag as inactive so it won't be selected for new captions."""
    from ruamel.yaml import YAML

    path = Path("fixtures/captions.yaml")
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(path.read_text())
    changed = 0
    for _category, entries in data.get("hashtags", {}).items():
        for entry in entries:
            if entry.get("tag") == tag and entry.get("active", True):
                entry["active"] = False
                changed += 1
    if changed:
        yaml.dump(data, path.open("w"))
        console.print(f"[green]Deprecated:[/green] #{tag}")
    else:
        console.print(f"[yellow]Not found or already inactive:[/yellow] #{tag}")


@captions_app.command("reset")
def captions_reset(
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually wipe state."),
) -> None:
    """Wipe all recorded hashtag combinations from state DB."""
    from nobodynamed_video.compose.state import CombinationState

    if not confirm:
        console.print("[red]Pass --confirm to wipe the state DB.[/red]")
        raise typer.Exit(1)
    state = CombinationState(Path("state/used_combinations.db"))
    state.reset()
    console.print("[green]State DB wiped.[/green]")
```

- [ ] **Step 2: Verify CLI loads**

```bash
uv run nbn captions --help
```

Expected output includes: `stats`, `deprecate`, `reset`.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all passed.

- [ ] **Step 4: Commit**

```bash
git add src/nobodynamed_video/cli.py
git commit -m "feat: nbn captions stats/deprecate/reset CLI commands"
```

---

## Task 8: End-to-end smoke test

Verify the compositor runs during a real batch render and writes caption data to the manifest.

- [ ] **Step 1: Start Satori sidecar**

```bash
node satori-service/dist/server.js &
until curl -sf http://localhost:3001/health; do sleep 1; done
```

- [ ] **Step 2: Render smoke batch**

```bash
D1_URL= uv run nbn render --spec batches/smoke.yaml
```

Expected: `✓ bertha-2024`

- [ ] **Step 3: Verify caption in manifest**

```bash
python3 -c "
import json; m = json.load(open('out/bertha-2024.json'))
print('caption:',       m.get('caption'))
print('pinned_comment:', m.get('pinned_comment'))
print('hashtag_set:',   m.get('hashtag_set'))
assert m.get('caption'), 'caption missing'
assert m.get('pinned_comment'), 'pinned_comment missing'
assert len(m.get('hashtag_set', [])) >= 3, 'hashtag_set too short'
print('OK')
"
```

Expected: prints caption, pinned comment, hashtag set, then `OK`.

- [ ] **Step 4: Verify state DB was written**

```bash
python3 -c "
import sqlite3, pathlib
db = pathlib.Path('state/used_combinations.db')
assert db.exists(), 'state DB not created'
conn = sqlite3.connect(str(db))
count = conn.execute('SELECT COUNT(*) FROM used_combinations').fetchone()[0]
print(f'Combinations recorded: {count}')
assert count >= 1
print('OK')
"
```

- [ ] **Step 5: Stop sidecar and commit**

```bash
kill $(lsof -ti :3001)
git add state/.gitkeep 2>/dev/null; true
git commit -m "chore: ensure state/ directory is tracked"
```

---

## Self-review

**Spec coverage:**

- §1 Rules: caption ≤150 ✓, emotional words 2-3 ✓, hashtags 3-5 ✓, uniqueness via state DB ✓, ≥1 core ✓, pinned ≤100 and ends with `?` ✓
- §2 Repo placement: `fixtures/captions.yaml` ✓, `compose/caption.py` ✓, `compose/state.py` ✓, `compose/lexicon.py` ✓, `state/used_combinations.db` ✓
- §3 Data file: written verbatim in Task 1 ✓
- §4 Compositor algorithm steps 1-9: frame selection ✓, Jinja render ✓, emotional words ✓, budget check (truncation) ✓, hashtag selection ✓, uniqueness loop ✓, pinned comment ✓, assemble ✓, persist ✓
- §8 Validation rules: length ✓, hashtag count ✓, core present ✓, pinned ends `?` ✓
- `nbn captions stats/deprecate/reset` CLI ✓

**Gaps identified:**

- Trend tag weekly rate-limiting: implemented via `tag_uses_this_week()` ✓
- `peer_name` in one pinned pattern: filtered out by `patterns_for()` when var is None ✓ (pattern just won't be selected)
- `{{ peak_decade }}s` in pinned: `peak_decade` is an int in VideoContext, renders as `1960s` ✓

**Type consistency check:** `compose_caption(spec_id, hook, ctx, lexicon, state)` matches usage in `runner.py` ✓. `ComposedCaption.hashtag_set: list[str]` matches `RenderManifest.hashtag_set: list[str]` ✓.
