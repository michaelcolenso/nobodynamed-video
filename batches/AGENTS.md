# CAPTIONS.md — Caption & Pinned Comment Composition

> **Mission.** At render time, the pipeline generates a TikTok caption and a pinned comment from the same `NameRecord` + `Tier` + `Hook` that produced the video. Output is constrained: 150-char captions, 2–3 emotional words, 3–5 hashtags, and no two videos ever ship the same hashtag combination.

> **Integrates with** `nobodynamed-video` Phase 5 (composition). The compositor runs after frames render but before the MP4 is sealed. Output is written to the same manifest that carries the render metadata.

---

## 1. The rules (canonical)

These are the constraints. Every shipped video must satisfy all six.

1. **Caption length** ≤ 150 characters total, including hashtags and spaces.
2. **Emotional words**: exactly 2 or 3 from the curated lexicon, drawn from the register pool that matches the hook's register.
3. **Hashtags**: 3 to 5 per caption, drawn from the curated pool.
4. **Hashtag uniqueness**: no two videos may ship the same set of hashtags (order-independent). Tracked in state.
5. **One core hashtag minimum**: every caption must include at least one tag from `core` (niche-defining), ensuring topical clustering for the algorithm.
6. **Pinned comment**: one of the curated patterns, populated from the same context as the caption. Always a question. Never longer than 100 characters.

If any rule fails, the compositor regenerates up to 50 times. If still failing, the render aborts with a clear error. Better to surface the conflict than ship a degraded caption.

---

## 2. Repository placement

```
nobodynamed-video/
├── fixtures/
│   └── captions.yaml          # this file's data section, canonical
├── src/nobodynamed_video/
│   ├── compose/
│   │   ├── caption.py         # the compositor
│   │   ├── state.py           # used-combination tracker
│   │   └── lexicon.py         # loads captions.yaml, provides query API
│   └── ...
├── state/
│   └── used_combinations.db   # SQLite, tracks shipped hashtag sets
└── ...
```

The state DB is part of the project but gitignored. It survives across runs so the uniqueness rule actually holds. Back it up the way you back up the SSA database.

---

## 3. The data file: `fixtures/captions.yaml`

```yaml
version: 1

# ---------------------------------------------------------------------------
# CAPTION CONSTRAINTS — runtime-enforced
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# HASHTAG POOL
# ---------------------------------------------------------------------------
# Each tag has a category and an allowed-register list. The compositor filters
# by register when picking hashtags. Tags can be deprecated by setting
# `active: false` without removing them (keeps state DB references valid).

hashtags:

  # CORE — niche-defining. At least one MUST appear in every caption.
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

  # BROAD — discovery layer. Helps surface to new audiences.
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

  # EMOTIONAL — register-specific amplifiers.
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

  # TREND — high-traffic but low-signal. Use sparingly; 0–1 per caption.
  # Rotate quarterly based on TikTok's trending list.
  trend:
    - tag: fyp
      registers: [morbid, curious, nostalgic, hopeful, cultural]
      active: true
      max_uses_per_week: 3      # rate-limited; algorithm punishes overuse
    - tag: foryou
      registers: [morbid, curious, nostalgic, hopeful, cultural]
      active: true
      max_uses_per_week: 3
    - tag: namesoftiktok2026
      registers: [morbid, curious, nostalgic, hopeful, cultural]
      active: false             # placeholder for quarterly rotation

# ---------------------------------------------------------------------------
# EMOTIONAL LEXICON
# ---------------------------------------------------------------------------
# Words injected into the caption body. The compositor picks 2 or 3 from the
# pool matching the hook's register. Words must read editorially, not
# clickbait. No "INSANE" or "shocking."

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

# ---------------------------------------------------------------------------
# PINNED COMMENT PATTERNS
# ---------------------------------------------------------------------------
# Each pattern is a Jinja2 template. The compositor picks one matching the
# hook's pillar and register, populated from the same Ctx the video uses.
# Every pattern must end with a question mark — this is non-negotiable for
# engagement.

pinned_patterns:

  extinction-watch:
    - "Do you know anyone under 30 named {{ name }}?"
    - "When's the last time you met a {{ name }}?"
    - "Whose grandmother was named {{ name }}?"
    - "What's the rarest name you've heard this year?"
    - "{{ name }} or {{ peer_name }}: which dies first?"

  peak-year:
    - "Whose name peaked in {{ peak_year }}?"
    - "Drop a year. I'll tell you the top name."
    - "What name does your high school class share too many of?"
    - "Which {{ peak_decade }}s name is still cool?"
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

# ---------------------------------------------------------------------------
# CAPTION FRAMES (the narrative skeleton)
# ---------------------------------------------------------------------------
# Captions are composed from a frame (1-line narrative) + emotional words +
# hashtags. Each hook in hooks.yaml references a caption_frame_id, or the
# compositor picks one matching the hook's pillar and register.

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
      template: "{{ name }}'s 100-year story, in {{ duration_s | int }} seconds."
      requires_vars: [name, duration_s]
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

# ---------------------------------------------------------------------------
# COMBINATION TRACKER — operational
# ---------------------------------------------------------------------------

state_db:
  path: "state/used_combinations.db"
  schema: |
    CREATE TABLE used_combinations (
      combo_hash      TEXT PRIMARY KEY,    -- SHA-256 of sorted tag tuple
      tags_json       TEXT NOT NULL,       -- ["endangerednames","babynames",...]
      first_used_at   TIMESTAMP NOT NULL,
      first_used_spec TEXT NOT NULL,       -- e.g. "bertha-2024"
      use_count       INTEGER DEFAULT 1
    );
    CREATE INDEX idx_combo_first_used ON used_combinations(first_used_at DESC);
```

---

## 4. The compositor: `compose/caption.py` algorithm

```
Inputs:
  - NameRecord (name, tier, current_count, peak_count, etc.)
  - Hook (id, pillar, register, ...)
  - VideoSpec (spec_id for state tracking)
  - Lexicon (loaded from captions.yaml)
  - StateDB (used combinations)

Output:
  - Caption (str, ≤150 chars)
  - PinnedComment (str, ≤100 chars)
  - HashtagSet (sorted list of strings)

Algorithm:

1. Select caption frame
   - Filter caption_frames by hook.pillar
   - Filter by hook.register if the frame has a register constraint
   - Filter to frames whose requires_vars are all available in Ctx
   - Pick deterministically using BLAKE2b(spec_id + "frame") % len(candidates)

2. Render the frame
   - Evaluate the Jinja template against Ctx
   - Strip extra whitespace; preserve punctuation

3. Inject emotional words
   - Filter emotional_words by hook.register
   - Pick 2 or 3 deterministically: count = 2 if frame is long, 3 if short
   - Pick words via BLAKE2b(spec_id + "emo_i") % len(pool) for each
   - Reject duplicates within the same caption
   - Splice into the frame — see Composition rules below

4. Compute budget for hashtags
   - body_chars = len(rendered frame with emotional words)
   - hashtag_budget = 150 - body_chars - 1 (for the leading space)
   - If hashtag_budget < 30, regenerate from step 3 with shorter words
   - Determine hashtag_count: prefer 4, fall back to 3 or 5 based on budget

5. Pick hashtags
   - Always include exactly 1 from `core` filtered by register
   - Include 1 from `broad` filtered by register
   - Include 1 or 2 from `emotional` filtered by register
   - Include 0 or 1 from `trend` subject to max_uses_per_week
   - Total must equal hashtag_count
   - Total char length (including # and joining spaces) must fit hashtag_budget

6. Enforce combination uniqueness
   - Sort the chosen tags lexicographically
   - Compute combo_hash = SHA-256(",".join(sorted_tags))
   - Query state_db.used_combinations for combo_hash
   - If exists: swap one tag (lowest-frequency tag in the global pool)
     and retry from step 6
   - If 50 retries fail, raise CombinationExhaustion (rare; pool is large)

7. Generate pinned comment
   - Filter pinned_patterns by hook.pillar
   - Filter to patterns whose template variables all resolve
   - Pick deterministically: BLAKE2b(spec_id + "pinned") % len(candidates)
   - Render the Jinja template
   - Reject if length > 100 chars; pick the next candidate

8. Assemble final caption
   - Format: "<body> <space-joined hashtags with # prefix>"
   - Validate total length ≤ 150
   - Validate one core hashtag present
   - Validate 2-3 emotional words present
   - Validate hashtag count in [3, 5]

9. Persist
   - Insert combo_hash into state_db.used_combinations
   - Write caption, pinned_comment, hashtag_set into RenderManifest
```

### Composition rules for emotional word splicing

- Adjective form: place before the noun ("a vanishing American name").
- Phrase form (multi-word like "on the brink"): place at end as standalone sentence.
- Never repeat the same word inside one caption.
- Prefer adjectives early in the body for skim-readability.

---

## 5. State management

The state DB is the only mutable artifact in the pipeline outside the `out/` directory. Treat it like the SSA fixture: backed up, versioned, never edited by hand.

**Operations:**
- `nbn captions stats` → prints used vs available combinations per register.
- `nbn captions deprecate <tag>` → marks a tag inactive without breaking historical state references.
- `nbn captions reset --confirm` → wipes state (e.g. for a brand relaunch). Requires explicit confirmation flag.

**Backup:** copy `state/used_combinations.db` into the daily `out/<batch>/` directory so a manifest carries the state at render time. If the DB is lost, restore from the most recent batch.

---

## 6. Integration with `hooks.yaml`

The existing `caption` and `pinned_comment` fields in `hooks.yaml` are **demoted to fallbacks**. If the compositor cannot satisfy the constraints for a given hook, the runner uses the hook's static caption and pinned_comment instead, and logs a warning. This way the system degrades gracefully.

**Migration path:**

1. Phase A (week 1): compositor runs in shadow mode — generates captions but the renderer still uses hook.caption. Manifest carries both.
2. Phase B (week 2): A/B test 50/50 between compositor and hook.caption. Track save rate and follow conversion.
3. Phase C (week 3+): compositor is authoritative. hook.caption persists as the documented fallback.

This A/B is the only way to verify the constraints help rather than hurt.

---

## 7. Worked examples

### 7.1 Bertha (extinct, hook ext-001)

```
Hook: ext-001-only-n-last-year
Pillar: extinction-watch
Register: morbid
NameRecord: name=Bertha, current_count=122, peak_count=8843, peak_year=1908, tier=CRITICAL

Compositor output:

  Caption:
    "Bertha hasn't been common since 1908. Just 122 last year.
     A vanishing American name. #endangerednames #babynames #onthebrink #grandmacore"
    
    Length: 148 chars
    Emotional words: "vanishing", "on the brink" (2 — under-the-cap)
    Hashtags: 4
    Core: endangerednames ✓
    Combo hash: 8f3a... (new)

  Pinned comment:
    "When's the last time you met a Bertha?"
    Length: 39 chars
```

### 7.2 Karen (declining, hook cult-001)

```
Hook: cult-001-not-always-meme
Pillar: cultural-collapse
Register: cultural
NameRecord: name=Karen, current_count=325, peak_count=32873, peak_year=1965
killing_event: "the meme"

Compositor output:

  Caption:
    "The meme ended Karen. 32,873 → 325.
     A reshaped American name. #namedata #pophistory #culturalcollapse #babynames"
    
    Length: 144 chars
    Emotional words: "reshaped" (only 1) — REJECTED, regenerate
    
    Retry:
    "The meme ended Karen. 32,873 → 325.
     A reframed, displaced name. #namedata #pophistory #culturalcollapse #babynames"
    
    Length: 146 chars
    Emotional words: "reframed", "displaced" (2) ✓
    Hashtags: 4 ✓
    Core: namedata ✓

  Pinned comment:
    "What killed Karen, in your view?"
    Length: 32 chars
```

### 7.3 Hazel (resurrected, hook res-001)

```
Hook: res-001-almost-extinct
Pillar: resurrection
Register: hopeful
NameRecord: name=Hazel, trough_year=1976, trough_count=300, current_count=3284, tier=RESURRECTED

Compositor output:

  Caption:
    "Hazel came back. 300 → 3,284.
     A returning, vintage American name. #namedata #vintagecomeback #babynames #grandmacore"
    
    Length: 149 chars
    Emotional words: "returning", "vintage" (2) ✓
    Hashtags: 4 ✓
    Core: namedata ✓

  Pinned comment:
    "Which vintage name are you reviving?"
    Length: 36 chars
```

---

## 8. Validation rules (runtime, in `compose/caption.py`)

```python
def validate_caption(caption: str, hashtags: list[str], cfg: Constraints) -> None:
    assert len(caption) <= cfg.caption_max_chars, f"caption too long: {len(caption)}"
    assert cfg.hashtags_min <= len(hashtags) <= cfg.hashtags_max
    assert any(h in CORE_TAGS for h in hashtags), "missing core hashtag"
    assert count_emotional_words(caption) in (2, 3), "wrong emotional word count"
    assert caption.count("#") == len(hashtags), "hashtag count mismatch"
    assert all(t == t.lower() for t in hashtags), "hashtags must be lowercase"
    assert not any("!" in caption or "OMG" in caption), "tone violation"

def validate_pinned(text: str, cfg: Constraints) -> None:
    assert len(text) <= cfg.pinned_max_chars
    assert text.rstrip().endswith("?"), "pinned comment must end with '?'"
    assert not any(emoji in text for emoji in BLOCKED_EMOJI)
```

---

## 9. Acceptance test

The captioning subsystem is done when:

1. Rendering Bertha twice produces identical caption text (deterministic by spec_id).
2. Rendering a batch of 14 videos produces 14 distinct hashtag combinations, verified by querying `state_db`.
3. `nbn render --spec smoke.yaml` writes `caption`, `pinned_comment`, `hashtag_set` into the manifest JSON.
4. The validation suite passes for 100 randomly sampled NameRecords from the SSA fixture.
5. After 100 batch runs (~1400 videos), the state DB shows zero duplicate combo_hash entries.
6. A/B test (Phase B above) shows compositor-generated captions have save rate ≥ hook.caption baseline.

---

## 10. Failure modes

| Failure | Detection | Response |
|---|---|---|
| Combination exhaustion (pool too small) | Compositor raises after 50 retries | Deprecate over-used tags, add new ones, rerun |
| Hashtag character budget exhausted | Body too long after emotional words | Drop emotional word count to 2, retry |
| No matching pinned pattern for hook | All patterns reference unresolvable vars | Fall back to generic "What name should we cover next?" |
| State DB corrupted | SQLite errors at write time | Restore from most recent batch backup; do not silently bypass |
| Tag becomes inappropriate (e.g. hijacked) | Manual editorial review | `nbn captions deprecate <tag>`; existing references in state DB remain |

---

## 11. Out of scope

- **Multi-language captions.** English-only. The SSA dataset is US-only.
- **Auto-translation.** A future v2 concern.
- **Caption testing against TikTok's algorithm directly.** No reliable signal; A/B internally is the substitute.
- **Hashtag freshness scoring.** Quarterly manual review of the trend pool. No automated trend detection in v1.

---

*End of CAPTIONS.md.*
