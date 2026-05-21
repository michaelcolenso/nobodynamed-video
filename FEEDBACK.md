# FEEDBACK.md — `nobodynamed-feedback` Comment Mining Schema

> **Mission.** Mine the comments on @nobodynamed's TikTok posts nightly. Extract name requests. Score by engagement. Output a ranked queue that feeds directly into `nbn batch`. Close the loop between audience and content.

> **Sits alongside** `nobodynamed-video` in the same monorepo, under `feedback/`. Shares the SSA D1 connection. Outputs `batches/queue-<date>.yaml`.

---

## 0. Reality check: there is no official API

TikTok does not expose a comments API for personal or non-business creator accounts. The Research API requires academic affiliation. The Business API requires verified business account approval, a process Anthropic-style companies pass and solo creators usually do not.

**Practical options, ranked by reliability:**

| Approach | Reliability | Cost | Effort |
|---|---|---|---|
| `TikTokApi` Python library (unofficial, headless-browser-backed) | Medium. Breaks every few months when TikTok ships internal changes. Maintained, widely used. | Free | Low |
| `tikapi.io` or `apify.com` TikTok actors | High. Vendors absorb the breakage tax. | $20–$80/mo | Lowest |
| Playwright + hand-rolled selectors | Medium-low. Same fragility as TikTokApi but no library to absorb the maintenance. | Free | High |
| Manual export from TikTok Studio | High. But only ~20 comments per video, no full reply trees, no automation. | Free | Manual |

**Recommended default for v1: `TikTokApi` library.** It's the standard for solo creator analytics, the maintainer responds to selector breakage within a week or two, and the failure mode is graceful (the script logs an error and exits, doesn't corrupt data). When it breaks for more than a week, fall back to `tikapi.io` until the library catches up.

**The fragile dependency is acknowledged up front.** Build the schema and extraction logic to be source-agnostic. The TikTok scraper is a thin adapter; if it dies, swap to tikapi.io with a 50-line module replacement.

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   nobodynamed-feedback                          │
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐    │
│   │  scraper    │───→│  extractor  │───→│  ranker          │    │
│   │  (TikTok)   │    │  (NER + SSA │    │  (engagement-    │    │
│   │             │    │   match)    │    │   weighted)      │    │
│   └─────────────┘    └─────────────┘    └─────────────────┘    │
│         │                   │                   │               │
│         ↓                   ↓                   ↓               │
│   ┌─────────────────────────────────────────────────┐          │
│   │   SQLite (feedback.db)                          │          │
│   │   videos · comments · name_mentions · queue     │          │
│   └─────────────────────────────────────────────────┘          │
│                                                                 │
│   Outputs: batches/queue-YYYY-MM-DD.yaml                       │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓
                    feeds into `nbn batch` (video pipeline)
```

Three modules, one DB, one output file per day. Idempotent. Rerunnable. Auditable.

---

## 2. Repository layout

```
nobodynamed-video/                  # existing repo from AGENTS.md
└── feedback/
    ├── README.md
    ├── pyproject.toml              # separate dep set (TikTokApi, spacy, fuzzywuzzy)
    ├── .env.example                # TIKTOK_MS_TOKEN, TIKTOK_HANDLE
    ├── src/nobodynamed_feedback/
    │   ├── __init__.py
    │   ├── config.py               # Pydantic Settings
    │   ├── models.py               # Video, Comment, NameMention, QueueEntry
    │   ├── exceptions.py
    │   ├── db.py                   # SQLite connection, migrations
    │   ├── scraper/
    │   │   ├── __init__.py
    │   │   ├── source.py           # CommentSource protocol
    │   │   ├── tiktokapi_source.py # default: TikTokApi-backed
    │   │   ├── tikapi_source.py    # fallback: tikapi.io HTTP client
    │   │   └── jsonl_source.py     # dev: load from a recorded jsonl
    │   ├── extract/
    │   │   ├── __init__.py
    │   │   ├── candidates.py       # tokenize + find capitalized terms
    │   │   ├── patterns.py         # regex templates for explicit requests
    │   │   ├── ner.py              # spaCy en_core_web_sm fallback
    │   │   ├── ssa_match.py        # cross-reference against nobodynamed D1
    │   │   └── classify.py         # explicit_request | name_drop | family_reference
    │   ├── rank/
    │   │   ├── __init__.py
    │   │   ├── score.py            # weighted_score formula
    │   │   └── queue.py            # builds queue-YYYY-MM-DD.yaml
    │   ├── review/
    │   │   ├── __init__.py
    │   │   └── cli.py              # interactive accept/reject loop
    │   └── cli.py                  # nbn-feedback: fetch | extract | rank | review
    ├── migrations/
    │   ├── 001_initial.sql
    │   └── 002_add_queue_status.sql
    ├── tests/
    │   ├── fixtures/comments.jsonl # 200 hand-annotated comments for regression
    │   ├── test_extract.py         # extraction precision/recall ≥ 0.85
    │   ├── test_patterns.py
    │   ├── test_ssa_match.py
    │   └── test_ranker.py
    └── data/
        └── feedback.db             # gitignored
```

---

## 3. Database schema

SQLite. Schema lives in `migrations/`. The DB is the source of truth; everything else regenerates from it.

```sql
-- migrations/001_initial.sql

CREATE TABLE videos (
    video_id           TEXT PRIMARY KEY,           -- TikTok video ID
    url                TEXT NOT NULL,
    posted_at          TIMESTAMP NOT NULL,
    description        TEXT,
    view_count         INTEGER DEFAULT 0,
    like_count         INTEGER DEFAULT 0,
    comment_count      INTEGER DEFAULT 0,
    share_count        INTEGER DEFAULT 0,
    save_count         INTEGER DEFAULT 0,
    spec_id            TEXT,                       -- maps to nbn render spec, e.g. "bertha-2024"
    fetched_at         TIMESTAMP NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active'  -- active | deleted | private | failed
);

CREATE INDEX idx_videos_spec ON videos(spec_id);
CREATE INDEX idx_videos_posted ON videos(posted_at DESC);

CREATE TABLE comments (
    comment_id         TEXT PRIMARY KEY,
    video_id           TEXT NOT NULL REFERENCES videos(video_id),
    author_unique_id   TEXT NOT NULL,              -- hashed before storage
    author_followers   INTEGER,
    text               TEXT NOT NULL,
    like_count         INTEGER DEFAULT 0,
    reply_count        INTEGER DEFAULT 0,
    posted_at          TIMESTAMP NOT NULL,
    fetched_at         TIMESTAMP NOT NULL,
    parent_comment_id  TEXT,                       -- NULL for top-level
    is_pinned          BOOLEAN DEFAULT FALSE,
    is_creator_reply   BOOLEAN DEFAULT FALSE,
    language           TEXT                        -- ISO 639-1, detected
);

CREATE INDEX idx_comments_video ON comments(video_id);
CREATE INDEX idx_comments_likes ON comments(like_count DESC);

CREATE TABLE name_mentions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id         TEXT NOT NULL REFERENCES comments(comment_id),
    candidate_name     TEXT NOT NULL,              -- normalized case (Title Case)
    extraction_method  TEXT NOT NULL,              -- explicit_request | name_drop | family_reference | quiz_response
    confidence         REAL NOT NULL,              -- 0.0 – 1.0
    ssa_record_id      INTEGER,                    -- nullable; foreign key to nobodynamed D1
    matched_sex        TEXT,                       -- M | F | unknown | both
    context_snippet    TEXT NOT NULL,              -- ±40 chars around the name
    created_at         TIMESTAMP NOT NULL
);

CREATE INDEX idx_mentions_name ON name_mentions(candidate_name);
CREATE INDEX idx_mentions_method ON name_mentions(extraction_method);

CREATE TABLE name_queue (
    name               TEXT NOT NULL,
    sex                TEXT NOT NULL,              -- M | F (must be resolved before queueing)
    mention_count      INTEGER NOT NULL DEFAULT 0,
    weighted_score     REAL NOT NULL DEFAULT 0.0,
    first_mentioned_at TIMESTAMP NOT NULL,
    last_mentioned_at  TIMESTAMP NOT NULL,
    seed_video_id      TEXT REFERENCES videos(video_id),
    status             TEXT NOT NULL DEFAULT 'queued',  -- queued | rendered | rejected | blocked
    rendered_spec_id   TEXT,
    rejection_reason   TEXT,
    blocked_by_rule    TEXT,                       -- name of the block rule that fired
    reviewed_at        TIMESTAMP,
    PRIMARY KEY (name, sex)
);

CREATE INDEX idx_queue_status ON name_queue(status);
CREATE INDEX idx_queue_score ON name_queue(weighted_score DESC);

CREATE TABLE run_log (
    run_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    command            TEXT NOT NULL,              -- fetch | extract | rank | review
    started_at         TIMESTAMP NOT NULL,
    completed_at       TIMESTAMP,
    videos_processed   INTEGER DEFAULT 0,
    comments_fetched   INTEGER DEFAULT 0,
    mentions_extracted INTEGER DEFAULT 0,
    new_queue_entries  INTEGER DEFAULT 0,
    errors             TEXT,                       -- newline-delimited error messages
    git_sha            TEXT                        -- commit hash of the code that ran
);
```

**Author hashing.** `author_unique_id` is `BLAKE2b(handle + salt, 16)`. Salt lives in `.env`. This makes the DB redistributable (golden fixtures, debugging) without leaking commenter identities.

---

## 4. Pydantic models

```python
# models.py — mirror the SQL but with validation

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class VideoStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"
    PRIVATE = "private"
    FAILED = "failed"

class ExtractionMethod(str, Enum):
    EXPLICIT_REQUEST   = "explicit_request"    # "do Hazel next!"
    NAME_DROP          = "name_drop"           # "my name is Linda"
    FAMILY_REFERENCE   = "family_reference"    # "my grandma was Mildred"
    QUIZ_RESPONSE      = "quiz_response"       # response to a "comment your name" CTA

class QueueStatus(str, Enum):
    QUEUED   = "queued"
    RENDERED = "rendered"
    REJECTED = "rejected"
    BLOCKED  = "blocked"

class Video(BaseModel):
    video_id: str
    url: str
    posted_at: datetime
    description: str | None = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    save_count: int = 0
    spec_id: str | None = None
    fetched_at: datetime
    status: VideoStatus = VideoStatus.ACTIVE

class Comment(BaseModel):
    comment_id: str
    video_id: str
    author_unique_id: str
    author_followers: int | None = None
    text: str = Field(min_length=1, max_length=2200)
    like_count: int = 0
    reply_count: int = 0
    posted_at: datetime
    fetched_at: datetime
    parent_comment_id: str | None = None
    is_pinned: bool = False
    is_creator_reply: bool = False
    language: str | None = None

class NameMention(BaseModel):
    comment_id: str
    candidate_name: str
    extraction_method: ExtractionMethod
    confidence: float = Field(ge=0.0, le=1.0)
    ssa_record_id: int | None = None
    matched_sex: str | None = Field(default=None, pattern=r"^[MF]$|^unknown$|^both$")
    context_snippet: str
    created_at: datetime

class QueueEntry(BaseModel):
    name: str
    sex: str = Field(pattern=r"^[MF]$")
    mention_count: int = Field(ge=1)
    weighted_score: float
    first_mentioned_at: datetime
    last_mentioned_at: datetime
    seed_video_id: str | None = None
    status: QueueStatus = QueueStatus.QUEUED
    rendered_spec_id: str | None = None
    rejection_reason: str | None = None
    blocked_by_rule: str | None = None
    reviewed_at: datetime | None = None
```

---

## 5. Extraction logic

The heart of the system. Two-stage pipeline: **candidate generation** (high recall, accepts noise) then **classification + filtering** (high precision, rejects most candidates).

### 5.1 Candidate generation

For each comment, generate a candidate list of (token, position) pairs.

1. Lowercase the text, preserving original positions for context snippets.
2. Tokenize on whitespace + punctuation. Keep contractions intact.
3. For each token, check three signals:
   - Capitalized in original text (excluding sentence-initial position).
   - Length 3–14 characters.
   - Matches the regex `^[A-Z][a-z]+(-[A-Z][a-z]+)?$`. Hyphenated names allowed.
4. Pull a `±40 char` context window for each candidate.

This is intentionally noisy. Many candidates will be place names, brand names, or random capitalizations.

### 5.2 Pattern matching for explicit requests

Run the comment text through these regex templates (case-insensitive). A hit promotes any candidate within ±15 chars to `extraction_method=explicit_request` with `confidence += 0.4`.

```python
REQUEST_PATTERNS = [
    r"\bdo\s+(?P<name>[A-Z][a-z]{2,13})\b",                          # "do Hazel"
    r"\bwhat\s+about\s+(?P<name>[A-Z][a-z]{2,13})\b",                # "what about Linda"
    r"\bcover\s+(?P<name>[A-Z][a-z]{2,13})\b",                       # "cover Iris next"
    r"\b(?P<name>[A-Z][a-z]{2,13})\s+next\b",                        # "Mildred next"
    r"\bplease\s+do\s+(?P<name>[A-Z][a-z]{2,13})\b",
    r"\bcan\s+you\s+do\s+(?P<name>[A-Z][a-z]{2,13})\b",
    r"\b(?P<name>[A-Z][a-z]{2,13})\s+please\b",
    r"\bmy\s+name\s+is\s+(?P<name>[A-Z][a-z]{2,13})\b",              # NAME_DROP
    r"\bi'?m\s+(?:a|an)\s+(?P<name>[A-Z][a-z]{2,13})\b",
    r"\bmy\s+(?:grandma|grandpa|grandmother|grandfather|aunt|uncle|mom|dad|mother|father|daughter|son|sister|brother)(?:'s)?\s+(?:name\s+(?:is|was)\s+)?(?P<name>[A-Z][a-z]{2,13})\b",  # FAMILY_REFERENCE
]
```

`extraction_method` is determined by which group of patterns matched first.

### 5.3 SSA cross-reference

For each candidate, query the nobodynamed D1 database:

```sql
SELECT id, name, sex, peak_count
FROM names
WHERE LOWER(name) = LOWER(:candidate)
   OR levenshtein(LOWER(name), LOWER(:candidate)) <= 1
ORDER BY peak_count DESC
LIMIT 5;
```

- **Exact match (lowercase):** `confidence += 0.5`, set `ssa_record_id`.
- **Edit-distance-1 match** (typos like "Hazle" for "Hazel"): `confidence += 0.3`, set `ssa_record_id` to nearest.
- **No SSA match:** keep candidate at low confidence; surface in review queue for editorial decision (it might be a real name not yet in our dataset).

If multiple matches (M and F entries for same name), set `matched_sex = "both"` and defer sex resolution to the ranker.

### 5.4 Confidence scoring

Final confidence per mention is the sum of signals, capped at 1.0:

| Signal | Weight |
|---|---|
| Pattern match (explicit request) | +0.4 |
| Pattern match (name drop) | +0.3 |
| Pattern match (family reference) | +0.25 |
| SSA exact match | +0.5 |
| SSA fuzzy match (edit distance 1) | +0.3 |
| Comment author has >10K followers | +0.05 |
| Comment is a creator reply | -0.5 (don't queue your own requests) |
| Comment is in a non-English language | -0.2 (SSA is US-only) |

**Threshold for queueing:** `confidence ≥ 0.5`. Below that, the mention is stored but doesn't promote into the queue.

### 5.5 False positive blacklist

Names that look like names but consistently appear in non-name contexts:

```python
FALSE_POSITIVE_TERMS = {
    "Karen",     # often a meme reference, not a name request — handle via heuristic
    "Chad",      # same
    "Becky",     # same
    "Felicia",   # same
    "Alexa",     # voice assistant references
    "Siri",
    "Tiktok",
    "Spotify",
    "America",
    "England",
    "Christmas",
    "Halloween",
    "God",
    "Jesus",
}
```

**Karen heuristic.** If "Karen" appears in a comment without an explicit-request pattern, classify as `confidence = 0.2` (insufficient to queue). If it appears WITH a request pattern ("do Karen next"), classify normally — the audience is asking for it knowingly.

---

## 6. Ranker and queue output

### 6.1 Weighted score formula

```
weighted_score = Σ over mentions of (
    confidence × log(1 + comment.like_count) × method_weight × recency_decay
)

where:
    method_weight = 1.0 (explicit_request)
                  | 0.5 (name_drop)
                  | 0.7 (family_reference)
                  | 0.8 (quiz_response)

    recency_decay = exp(-days_since_mention / 30)
```

Log-scaled comment likes prevents one viral comment from dominating the queue. Recency decay keeps the queue fresh — a name requested 90 days ago weighs ~5% of one requested yesterday.

### 6.2 Queue output

```yaml
# batches/queue-2026-05-20.yaml
# Auto-generated by `nbn-feedback rank`. Do not edit by hand; edit the DB
# via `nbn-feedback review`.

generated_at: 2026-05-20T03:00:00Z
generated_from:
  videos_scanned: 47
  comments_processed: 8341
  mentions_extracted: 612
  unique_names: 89

queue:
  - name: Hazel
    sex: F
    weighted_score: 12.4
    mention_count: 23
    sample_request: "do Hazel next please!!"
    sample_video_id: "7234567890123456789"
    status: queued

  - name: Theodore
    sex: M
    weighted_score: 9.1
    mention_count: 18
    sample_request: "what about Theodore? It's having a moment"
    sample_video_id: "7234567890123456789"
    status: queued

  # ... more entries ...

rejected:
  - name: Karen
    sex: F
    rejection_reason: "meme_reference_threshold"
    mention_count: 41
    notes: "All 41 mentions lacked explicit-request pattern."

blocked:
  - name: Trayvon
    sex: M
    blocked_by_rule: "blocked_names.yaml"
    mention_count: 2
```

This file is committed to the repo (as a dated artifact) and can be passed directly to `nbn batch`:

```bash
uv run nbn batch batches/queue-2026-05-20.yaml --top 14
```

The video pipeline's batch runner reads `queue:` entries (ignoring `rejected:` and `blocked:`), takes the top N by weighted_score, and renders them.

---

## 7. Configuration

```bash
# feedback/.env

TIKTOK_HANDLE=nobodynamed
TIKTOK_MS_TOKEN=<paste from logged-in browser DevTools>
TIKTOK_SESSION_COUNT=1
SCRAPER_BACKEND=tiktokapi              # tiktokapi | tikapi | jsonl
TIKAPI_KEY=                            # only if SCRAPER_BACKEND=tikapi
JSONL_INPUT=                           # only if SCRAPER_BACKEND=jsonl

VIDEOS_PER_RUN=50
COMMENTS_PER_VIDEO=200
JITTER_MIN_S=2
JITTER_MAX_S=8
RATE_LIMIT_PER_MIN=30

SSA_D1_URL=https://api.cloudflare.com/.../query
SSA_D1_TOKEN=<scoped read-only>

AUTHOR_HASH_SALT=<random 32-byte hex>

QUEUE_OUT_DIR=../batches
LOG_LEVEL=INFO
```

---

## 8. CLI commands

```bash
# Pull latest videos + comments from TikTok
uv run nbn-feedback fetch
  --since "7 days ago"        # or --all for backfill
  --max-videos 50

# Re-run extraction on existing comments (after improving heuristics)
uv run nbn-feedback extract --reprocess

# Rebuild queue from current DB state
uv run nbn-feedback rank --output ../batches/queue-$(date +%Y-%m-%d).yaml

# Interactive review of top candidates (accept | reject | block)
uv run nbn-feedback review --top 30

# Mark queued entries as rendered after a batch run
uv run nbn-feedback mark-rendered ../batches/queue-2026-05-20.yaml

# Stats dashboard (printed to terminal)
uv run nbn-feedback stats
```

The nightly cron job is:

```bash
0 3 * * *  cd /home/michael/nobodynamed-video/feedback && \
           uv run nbn-feedback fetch --since "2 days ago" && \
           uv run nbn-feedback rank --output ../batches/queue-$(date +%Y-%m-%d).yaml
```

---

## 9. Failure modes and defensive design

### 9.1 TikTok scraper breaks

**Symptom:** `TikTokApi` raises selector or auth errors.

**Response:**
1. Log the error to `run_log` with full traceback.
2. Exit non-zero so cron alerts via your normal mechanism.
3. Do NOT corrupt the DB. The fetch is transactional; either all comments for a video land or none do.
4. If breakage persists 3+ days, switch `SCRAPER_BACKEND=tikapi` in `.env`. The interface is identical; only the adapter changes.

### 9.2 Rate limiting

**Symptom:** TikTok starts returning empty results or 429s.

**Response:**
- Built-in jitter between requests: `random.uniform(JITTER_MIN_S, JITTER_MAX_S)`.
- Hard cap of `RATE_LIMIT_PER_MIN`.
- On 429 detected: exponential backoff starting at 60s, double up to 30 min, then abort.
- After abort, the cron's next run resumes from where it stopped (videos table tracks `fetched_at`).

### 9.3 MS token expires

**Symptom:** `TikTokApi` auth fails immediately.

**Response:**
- `nbn-feedback doctor` checks token validity by fetching `@tiktok`'s public profile.
- If invalid, the script logs a clear message: "MS token expired. Open TikTok in browser, log in, copy ms_token cookie from DevTools → Application → Cookies, paste into .env."
- Manual step. No auto-refresh; that's a security risk.

### 9.4 Comment author harassment / doxxing risk

Authors are hashed at ingest. Even if the DB leaks, commenter identities are not recoverable without the salt. Don't store the raw handle in any column.

### 9.5 Blocked / sensitive name auto-queueing

**Symptom:** Audience requests a name on the `blocked_names` list in `cultural_events.yaml`.

**Response:**
- The ranker reads `cultural_events.yaml` at startup.
- Any blocked name is moved to the `blocked:` section of `queue.yaml` with `blocked_by_rule` set.
- It will not be passed to `nbn batch`. The video pipeline's blocklist is the second line of defense; this is the first.

---

## 10. Editorial review workflow

The runner cannot judge nuance. Some queueing decisions require Michael's eyes. The review CLI:

```
$ uv run nbn-feedback review --top 30

[1/30] Hazel (F) — score 12.4, 23 mentions
  Sample: "do Hazel next please!! 😍" (147 likes)
  SSA: Hazel — F, peak 1900s, currently #28, tier=RESURRECTED
  Already rendered? No.
  → [a]ccept | [r]eject | [b]lock | [s]kip ?  a
  ✓ Queued for next batch.

[2/30] Khaleesi (F) — score 8.1, 14 mentions
  Sample: "Khaleesi went off a cliff after season 8" (62 likes)
  SSA: Khaleesi — F, peak 2013, currently rank 9999, tier=EXTINCT
  Already rendered? No.
  → [a]ccept | [r]eject | [b]lock | [s]kip ?  s

...
```

Five-minute daily ritual. Most names auto-pass; a few get a closer look.

---

## 11. Integration contract with `nobodynamed-video`

The two projects communicate through two file-level interfaces:

**Outbound from feedback → video:**
- `batches/queue-YYYY-MM-DD.yaml` — daily, structured per §6.2.

**Outbound from video → feedback:**
- After a batch run, `nbn batch` writes `out/<batch>.summary.json` containing `{spec_id, status, mp4_path}`.
- A nightly cron task `nbn-feedback mark-rendered` reads the latest summary and updates `name_queue.status` from `queued` to `rendered`.

The two projects are independently deployable, independently testable, and share only the SSA D1 connection plus the file interface. Neither imports the other's code.

---

## 12. Out of scope

- Cross-platform: this is TikTok-only in v1. Instagram Reels and YouTube Shorts comment mining is v2.
- Sentiment analysis: counting requests, not analyzing sentiment.
- Reply trees: replies to comments are stored but not currently extracted. Top-level comments only in v1.
- Auto-responses: this script never posts. Composing replies is manual and stays manual.
- Multi-language extraction: English only in v1. Non-English comments are stored but mentions are extracted with reduced confidence.

---

## 13. Acceptance test

The feedback subsystem is done when:

1. `nbn-feedback fetch --since "30 days ago"` populates the DB without errors against a real TikTok account with at least 10 published videos.
2. `nbn-feedback extract --reprocess` runs through fixture data (`tests/fixtures/comments.jsonl`) with precision ≥ 0.85 and recall ≥ 0.80 against hand-annotated ground truth.
3. `nbn-feedback rank` produces a `queue.yaml` that `nbn batch --dry-run` parses without errors.
4. `nbn-feedback doctor` exits 0 only when TikTok token, D1 connection, and SQLite write permissions all check out.
5. The full cron pipeline runs nightly for 7 consecutive days without manual intervention.

When all five hold, the feedback loop is live and the account becomes audience-driven.

---

*End of FEEDBACK.md.*
