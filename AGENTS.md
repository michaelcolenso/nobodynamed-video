# AGENTS.md — `nobodynamed-video` Build Instructions

> **Mission.** Build a deterministic, agent-driven pipeline that turns SSA baby name records into 18-second 9:16 TikTok videos in the nobodynamed.com v3 brand system. Output: one command renders an MP4 ready for TikTok upload.

> **Audience.** A coding agent (Claude Code, Cursor, Codex) executing this top to bottom with no human in the loop until a phase gate fails.

> **Owner context.** Michael owns the repo, the SSA data already lives in a Cloudflare D1 database for nobodynamed.com, and the v3 brand identity is finalized (Source Serif 4 Black, `#B5B0A0` faded gray, `#A21F1F` crimson). Do not re-litigate brand decisions.

---

## 0. Read this first

### 0.1 Non-negotiables

1. **No placeholder logic.** If you cannot implement a function correctly, stop and surface the question. Do not write `# TODO: classification logic` and move on.
2. **Deterministic output.** Same inputs → byte-identical PNG frames and a reproducible MP4 (mod container timestamps). Seed every RNG. Pin every dependency.
3. **One name renders end-to-end before scaling.** The pipeline must produce a correct `Bertha-2024.mp4` before any other name is queued.
4. **Phase gates are mandatory.** Each phase has an acceptance test. If it fails, stop, diagnose, fix, re-run. Do not skip ahead.
5. **No silent fallbacks.** If Satori is down, fail loudly with a clear error. Do not substitute matplotlib charts.

### 0.2 Anti-goals

- ❌ Don't build a CMS, web UI, or upload automation. Render-only.
- ❌ Don't integrate TikTok's API. The output is a file Michael uploads manually.
- ❌ Don't add a database. Read from the existing nobodynamed D1 via HTTP, or accept a local SQLite fixture.
- ❌ Don't generate voiceover yet. Audio is a silent bed + optional ambient pad. ElevenLabs is Phase 8.
- ❌ Don't add face/talking-head support. Brand is editorial and data-first.

### 0.3 Success criteria for the whole project

A fresh clone, `make setup && make smoke`, on macOS or Linux, produces `out/Bertha-2024.mp4` (1080×1920, 30fps, ~18s, H.264, AAC silent track, under 8 MB) that:
- Opens cleanly in QuickTime/VLC.
- Survives a TikTok upload without re-encoding warnings.
- Visually matches the v3 brand (crimson dot reveal, faded gray body text, Source Serif 4 Black headlines on `#14110E` background).
- Is reproducible: rendering it twice produces identical PNG frames (verified by SHA-256).

---

## 1. Stack & decisions

| Layer | Choice | Why |
|---|---|---|
| Orchestrator | **Python 3.12** + `uv` | Michael's standard. Fast resolver. |
| Models | **Pydantic v2** | Validation, settings, serialization. |
| CLI | **Typer** | Same author as FastAPI; clean ergonomics. |
| Renderer | **Satori sidecar** (Node 20 + Express + `@resvg/resvg-js`) | Reuses the existing OG image stack from nobodynamed. JSX → PNG. |
| Composer | **ffmpeg 6+** via `subprocess` | Frame-sequence concat + crossfade + audio mux. |
| Data | **D1 over HTTP** (production) or **SQLite fixture** (dev) | No new infra. |
| Tests | **pytest** + golden-frame hashing | Catches visual regressions. |
| Lint/format | **ruff** (lint + format) + **mypy --strict** | Michael's standard. |
| Packaging | `pyproject.toml`, no `setup.py` | Modern. |

**Two-process design.** Python orchestrator on the host; Node Satori service on `:3001`. They communicate via HTTP/JSON. This isolates the JSX runtime and lets Michael reuse the exact templates from the OG image generator if he wants.

**Why not Remotion?** Remotion is the obvious choice and you should resist it. Remotion ships a full browser per render, costs 8–20× the wall-clock time, and forces Michael into a React video DSL he hasn't committed to. Satori + ffmpeg is 100% under his control, matches his existing nobodynamed stack, and runs headlessly without Chromium. If Phase 7 reveals motion limits Satori cannot reach, **then** introduce Remotion as a per-scene escape hatch.

---

## 2. Repository layout

Create exactly this structure. Do not invent additional directories.

```
nobodynamed-video/
├── AGENTS.md                      # this file, copied in unchanged
├── ARCHITECTURE.md                # data flow, scene timing, render pipeline (Phase 0 deliverable)
├── README.md                      # quickstart for humans
├── RUNBOOK.md                     # operational tasks (Phase 9 deliverable)
├── Makefile                       # setup, smoke, render, test, lint
├── pyproject.toml
├── uv.lock
├── .python-version                # 3.12
├── .env.example                   # SATORI_URL, D1_URL, D1_TOKEN, OUT_DIR, FONT_DIR
├── .gitignore                     # includes out/, .venv/, node_modules/, *.mp4, frames/
├── .ruff.toml
├── mypy.ini
│
├── src/nobodynamed_video/
│   ├── __init__.py
│   ├── config.py                  # Pydantic Settings
│   ├── models.py                  # NameRecord, YearCount, Tier, Scene, VideoSpec, RenderManifest
│   ├── exceptions.py              # SatoriUnavailable, FrameRenderFailed, InvalidTier
│   ├── seed.py                    # deterministic seed helpers (name+year → int)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── source.py              # DataSource protocol
│   │   ├── d1_source.py           # production: hits Cloudflare D1 HTTP API
│   │   ├── sqlite_source.py       # dev fixture
│   │   └── classifier.py          # six-tier logic with explicit thresholds
│   │
│   ├── scenes/
│   │   ├── __init__.py
│   │   ├── base.py                # Scene protocol: duration_s, frames_at(fps), template_name, props_at(t)
│   │   ├── hook.py                # 3s
│   │   ├── reveal.py              # 6s
│   │   ├── narrative.py           # 6s
│   │   └── cta.py                 # 3s
│   │
│   ├── render/
│   │   ├── __init__.py
│   │   ├── satori_client.py       # httpx.AsyncClient wrapper, retries, timeout
│   │   ├── frame_planner.py       # builds (t, props) pairs per scene
│   │   ├── motion.py              # easing curves, Ken Burns, number-count-up
│   │   └── golden.py              # SHA-256 hashing for regression tests
│   │
│   ├── compose/
│   │   ├── __init__.py
│   │   ├── ffmpeg.py              # builds the concat + crossfade graph
│   │   ├── audio.py               # silent track or ambient bed
│   │   └── manifest.py            # writes Bertha-2024.json next to the mp4
│   │
│   ├── batch/
│   │   ├── __init__.py
│   │   ├── spec.py                # YAML loader → list[VideoSpec]
│   │   └── runner.py              # async pool, progress, retries
│   │
│   └── cli.py                     # Typer app: render, batch, preview, doctor, smoke
│
├── satori-service/
│   ├── package.json               # pinned versions
│   ├── pnpm-lock.yaml
│   ├── tsconfig.json
│   ├── src/
│   │   ├── server.ts              # Express, POST /render, GET /health
│   │   ├── render.ts              # Satori + resvg
│   │   ├── fonts.ts               # loads Source Serif 4 Black + Regular at boot
│   │   └── templates/
│   │       ├── shared.tsx         # tokens: colors, spacing, type ramp
│   │       ├── hook.tsx
│   │       ├── reveal.tsx
│   │       ├── narrative.tsx
│   │       └── cta.tsx
│   └── fonts/                     # SourceSerif4-Black.ttf, SourceSerif4-Regular.ttf
│
├── batches/
│   ├── smoke.yaml                 # single video: Bertha 2024
│   └── week-1.yaml                # 14 videos, two pillars
│
├── fixtures/
│   ├── ssa.sqlite                 # subset of SSA data, ~50 names, 1880–2024
│   └── golden/                    # PNG frame hashes for regression
│       └── bertha-2024/
│           ├── hook_f00.sha256
│           ├── reveal_f180.sha256
│           └── manifest.json
│
├── scripts/
│   ├── fetch_ssa.py               # one-off: pulls SSA data into D1 (idempotent)
│   ├── build_fixture.py           # exports a deterministic subset to fixtures/ssa.sqlite
│   └── doctor.py                  # verifies fonts, ffmpeg, Satori, D1 reachable
│
├── tests/
│   ├── __init__.py
│   ├── test_classifier.py
│   ├── test_motion.py             # easing math, count-up monotonicity
│   ├── test_frame_planner.py      # exact frame counts per scene at 30fps
│   ├── test_satori_client.py      # uses respx
│   ├── test_ffmpeg.py             # asserts the generated command string
│   └── test_smoke.py              # renders Bertha, compares to golden hashes
│
└── out/                           # gitignored; final mp4s + manifests land here
```

**One rule:** do not add files outside this tree without updating this document and `ARCHITECTURE.md` in the same commit.

---

## 3. Brand tokens (canonical)

Treat this as the constitution. Hardcode in `satori-service/src/templates/shared.tsx`.

```ts
export const COLORS = {
  bg:         "#14110E",   // near-black, warm
  ink:        "#E8E0D4",   // cream body
  fade:       "#B5B0A0",   // faded gray (secondary text, axes)
  crimson:    "#A21F1F",   // extinct / critical marker
  emerald:    "#059669",   // rising / resurrected marker
  rule:       "#2A2622",   // hairline dividers
} as const;

export const TYPE = {
  display: { family: "Source Serif 4 Black",   weight: 900 },
  body:    { family: "Source Serif 4",          weight: 400 },
} as const;

export const RAMP = {
  display: [128, 96, 72, 56],   // px, used in hook/reveal headlines
  body:    [48, 36, 28, 22, 18],
} as const;

// 1080 × 1920 canvas
export const CANVAS = { w: 1080, h: 1920, safe: { top: 220, bottom: 280, x: 80 } };
```

**Safe area.** TikTok's UI overlays the bottom ~270px (caption + actions) and the top ~210px (handle bar). All meaningful content must live inside `safe`.

**Font files.** Source Serif 4 is SIL OFL — free to embed. Place `SourceSerif4-Black.ttf` and `SourceSerif4-Regular.ttf` in `satori-service/fonts/`. Load them at server boot via `fs.readFileSync` into Satori's `fonts` option. **Do not** rely on system fonts; Satori needs the bytes.

---

## 4. Data contract

### 4.1 Models (`src/nobodynamed_video/models.py`)

```python
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, PositiveInt

class Tier(str, Enum):
    EXTINCT      = "extinct"      # count == 0 in latest year
    CRITICAL     = "critical"     # count <= 25 and peak >= 1000
    DECLINING    = "declining"    # 5-yr slope < -10% and current < 0.5 * peak
    STABLE       = "stable"       # within +/- 10% of 10-yr average
    RISING       = "rising"       # 5-yr slope > +20% and current > 1.5 * 10-yr avg
    RESURRECTED  = "resurrected"  # was EXTINCT or CRITICAL within last 30 years, now STABLE+

class YearCount(BaseModel):
    year: int = Field(ge=1880, le=2100)
    count: int = Field(ge=0)

class NameRecord(BaseModel):
    name: str
    sex: str = Field(pattern=r"^[MF]$")
    series: list[YearCount]            # full history, ascending by year
    peak_year: int
    peak_count: PositiveInt
    current_year: int
    current_count: int

class Scene(BaseModel):
    kind: str                          # "hook" | "reveal" | "narrative" | "cta"
    duration_s: float
    template: str                      # matches Satori template filename
    static_props: dict

class VideoSpec(BaseModel):
    id: str                            # e.g. "bertha-2024"
    record: NameRecord
    tier: Tier
    scenes: list[Scene]
    fps: int = 30
    seed: int                          # derived from id; controls Ken Burns + jitter

class RenderManifest(BaseModel):
    spec_id: str
    rendered_at: datetime
    frame_count: int
    duration_s: float
    output_path: str
    sha256_frames: dict[str, str]      # filename → hash
    satori_version: str
    ffmpeg_version: str
```

### 4.2 Classifier thresholds (`data/classifier.py`)

These are non-negotiable. Encode them as module-level constants and unit-test every boundary.

```python
LATEST_YEAR = 2024  # update annually when SSA releases new data
CRITICAL_THRESHOLD = 25
CRITICAL_PEAK_FLOOR = 1000
DECLINING_SLOPE_5Y = -0.10
DECLINING_PEAK_RATIO = 0.50
STABLE_BAND = 0.10
RISING_SLOPE_5Y = 0.20
RISING_AVG_RATIO = 1.50
RESURRECTION_LOOKBACK_YEARS = 30
```

**Tier resolution order** (first match wins): EXTINCT → RESURRECTED → CRITICAL → RISING → DECLINING → STABLE. Resurrection is checked before critical because a name returning from the dead is more interesting than the fact that its current count is still low.

---

## 5. Scene specs

Total runtime: **18.0s** exactly. Don't deviate.

| # | Kind | Duration | Purpose | Key motion |
|---|---|---|---|---|
| 1 | hook | 3.0s | Name + provocative stat | Type-on headline, fade-in subhead at t=1.5 |
| 2 | reveal | 6.0s | Animated trajectory chart | Line draws left→right over 0.0–4.0s; crimson dot lands at current year at 4.0s; count-up number 4.0–5.5s |
| 3 | narrative | 6.0s | One-sentence story + tier badge | Crossfade in at 0.0–0.5s; subtle Ken Burns scale 1.00 → 1.04 over the full 6s |
| 4 | cta | 3.0s | nobodynamed.com + crimson dot | Logo fades in 0.0–0.6s; dot pulses at 1.5s, 2.0s, 2.5s |

**Crossfades between scenes:** 200ms each, achieved via ffmpeg `xfade` filter. The 200ms eats from both adjacent scenes equally — plan frame counts accordingly. Net visible time still sums to 18.0s because the crossfade overlaps content rather than appending.

**Frame counts at 30fps** (before xfade adjustment):
- hook: 90 frames (0–89)
- reveal: 180 frames (0–179)
- narrative: 180 frames (0–179)
- cta: 90 frames (0–89)
- **Total: 540 frames**

`tests/test_frame_planner.py` must assert exact counts. If the sum drifts, the test fails.

---

## 6. Phased build plan

Each phase ends with an **acceptance test** the agent runs. If it passes, commit and proceed. If it fails, do not advance.

### Phase 0 — Skeleton & docs (30 min)

Create the file tree from §2, all empty files committed, `pyproject.toml` with pinned deps, `Makefile` with stub targets, and a draft `ARCHITECTURE.md` that diagrams the two-process model and the data flow. `README.md` should fit on one screen and link to AGENTS.md, ARCHITECTURE.md, RUNBOOK.md.

**Acceptance:** `make setup` runs `uv sync` and `cd satori-service && pnpm install` without errors. `make doctor` exists but may exit 1.

### Phase 1 — Models, config, fixture data (1 hr)

Implement `models.py`, `config.py` (Pydantic Settings reading `.env`), `seed.py` (BLAKE2b of `f"{name}|{year}"` truncated to int64), `exceptions.py`, and `data/sqlite_source.py`. Write `scripts/build_fixture.py` that pulls a hand-picked set of names from the production D1 and writes `fixtures/ssa.sqlite`. Hand-pick at least: Bertha, Mildred, Karen, Hazel, Theodore, Linda, Jennifer, Emma, Liam, Adolf — covering all six tiers.

**Acceptance:** `pytest tests/test_classifier.py` passes with at least 18 cases covering every tier and every boundary.

### Phase 2 — Satori sidecar (2 hrs)

Build `satori-service/`. The service exposes:

- `GET /health` → `{ status: "ok", satori: "<version>", fonts: ["Source Serif 4 Black", "Source Serif 4"] }`
- `POST /render` → body `{ template: "hook" | "reveal" | "narrative" | "cta", props: {...} }` → PNG bytes (`Content-Type: image/png`)

Each template is a function `(props) => JSX.Element` rendered at 1080×1920. Templates import `COLORS`, `TYPE`, `RAMP`, `CANVAS` from `shared.tsx`. Satori does not support all CSS — restrict to flexbox, basic positioning, and explicit pixel sizes. **No CSS grid, no transforms beyond `translate`, no filters.**

**Acceptance:** `curl -X POST localhost:3001/render -d @samples/hook.json -o hook.png` produces a valid 1080×1920 PNG that, when opened, shows "Bertha" in Source Serif 4 Black 128px crimson on the dark background. Manual inspection only at this phase.

### Phase 3 — Frame planner & motion (1.5 hrs)

Implement `render/motion.py` with these easing functions: `linear`, `ease_in_out_cubic`, `ease_out_quart`. Implement `frame_planner.py` so that for any `Scene`, `planner.frames(scene, fps=30)` yields `(frame_index, props_dict)` tuples where `props_dict` is the interpolated state at that instant.

Examples of interpolated props the planner must produce:
- hook: `headline_chars_visible` (int, 0 → len(name)) via `ease_out_quart` over 0–1.0s
- reveal: `chart_draw_progress` (0.0 → 1.0) over 0–4.0s linear; `count_value` (0 → current_count) over 4.0–5.5s `ease_out_quart`
- narrative: `kb_scale` (1.00 → 1.04) over full 6.0s `ease_in_out_cubic`
- cta: `dot_alpha` keyframed at [1.5, 2.0, 2.5] s

**Acceptance:** `pytest tests/test_motion.py tests/test_frame_planner.py` passes. The planner produces exactly 540 frames total for the Bertha spec.

### Phase 4 — Satori client + frame rendering (1.5 hrs)

`render/satori_client.py` uses `httpx.AsyncClient` with: connect timeout 2s, read timeout 10s, 3 retries with exponential backoff, semaphore limiting concurrency to 8 (Satori is single-threaded per request; more than ~8 in flight starves the event loop).

Add `render/golden.py` to SHA-256 each PNG as it lands on disk. Write frames to `out/<spec_id>/frames/<scene>_<frame:03d>.png`.

**Acceptance:** `uv run nbn render --spec batches/smoke.yaml --no-compose` produces 540 PNGs in `out/bertha-2024/frames/` in under 90 seconds on Michael's laptop. All PNGs are exactly 1080×1920.

### Phase 5 — ffmpeg composition (1.5 hrs)

`compose/ffmpeg.py` builds a filter graph that:

1. Reads each scene's frame sequence as `concat:` or `image2` input at the appropriate framerate.
2. Applies a `xfade=transition=fade:duration=0.2:offset=<t>` between consecutive scenes.
3. Scales/pads to exactly 1080×1920 with `scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x14110E`.
4. Adds a silent stereo AAC track at 44.1kHz matching total duration (TikTok rejects audio-less uploads on some Android versions).
5. Encodes with `libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart`.

Reference command (the function should build this dynamically, but the smoke test target must produce something equivalent):

```bash
ffmpeg -y \
  -framerate 30 -i out/bertha-2024/frames/hook_%03d.png \
  -framerate 30 -i out/bertha-2024/frames/reveal_%03d.png \
  -framerate 30 -i out/bertha-2024/frames/narrative_%03d.png \
  -framerate 30 -i out/bertha-2024/frames/cta_%03d.png \
  -f lavfi -t 18 -i anullsrc=channel_layout=stereo:sample_rate=44100 \
  -filter_complex "\
    [0:v][1:v]xfade=transition=fade:duration=0.2:offset=2.8[v01]; \
    [v01][2:v]xfade=transition=fade:duration=0.2:offset=8.6[v012]; \
    [v012][3:v]xfade=transition=fade:duration=0.2:offset=14.4,format=yuv420p[v]" \
  -map "[v]" -map 4:a \
  -c:v libx264 -preset slow -crf 20 -movflags +faststart \
  -c:a aac -b:a 128k \
  -t 18 \
  out/bertha-2024.mp4
```

**Acceptance:** `make smoke` produces `out/bertha-2024.mp4`. `ffprobe` reports: 1080×1920, 30fps, ~18.00s, H.264 high profile yuv420p, AAC stereo, faststart present. File size < 8MB.

### Phase 6 — Manifest & golden tests (1 hr)

After every render, `compose/manifest.py` writes `out/bertha-2024.json` containing the `RenderManifest`. Then `golden.py` compares the per-scene first-frame hashes to `fixtures/golden/bertha-2024/`. If a golden file is missing, write it (first run bootstraps). If it exists and mismatches, fail.

**Acceptance:** Running `make smoke` twice produces a manifest with identical frame hashes both times. Bumping a brand color produces a clear failure pointing at the first divergent frame.

### Phase 7 — Batch runner (1 hr)

`batch/runner.py` reads a YAML file like:

```yaml
batch: week-1
defaults:
  fps: 30
videos:
  - id: bertha-2024
    name: Bertha
    sex: F
    style: extinction-watch
  - id: karen-2024
    name: Karen
    sex: F
    style: cultural-collapse
  # ...
```

It resolves each entry into a `VideoSpec`, runs them through the pipeline with a concurrency limit (default 2 — ffmpeg encodes are CPU-heavy), prints a progress table, and writes a batch-level summary at `out/week-1.summary.json`.

**Acceptance:** `uv run nbn batch batches/week-1.yaml` renders 14 videos with no errors. Average per-video wall time under 60s on an M-series laptop.

### Phase 8 — Optional audio bed (45 min)

Add a `--audio bed.wav` flag to `render`. If supplied, mix the bed at -22 LUFS (use `loudnorm` filter) under the video, ducked nowhere because there's no voiceover. Default remains silent. **Do not** download royalty-free audio; require the user to supply the file.

**Acceptance:** Re-rendering Bertha with `--audio fixtures/silence-pad.wav` produces a video whose audio track passes `ffmpeg -af loudnorm=print_format=json` reporting integrated loudness within ±1 LU of -22.

### Phase 9 — Runbook & polish (45 min)

Write `RUNBOOK.md` with:
- Daily render workflow.
- How to update the LATEST_YEAR constant.
- How to add a new scene template.
- How to debug a Satori 500.
- How to bisect a golden-frame regression.
- How to rotate the D1 token.

Make sure `make doctor` exits 0 only when Python, Node, ffmpeg ≥6, Satori `/health`, both fonts, and D1 reachability all check out.

**Acceptance:** A fresh checkout of the repo + `make setup && make smoke` produces `out/bertha-2024.mp4` with zero manual intervention beyond placing the two TTF files in `satori-service/fonts/`.

---

## 7. Clever requirements (do not skip)

These are the things separating a working pipeline from a useful one. Each must be implemented during the phase noted.

1. **Deterministic Ken Burns (Phase 3).** Seed the scale/pan parameters from `seed(spec_id)`. Same spec → same motion. This lets Michael re-render an old name months later and get the same video, which matters for series content.

2. **Frame cache by content hash (Phase 4).** Hash `(template, props)` and cache PNG bytes on disk under `out/.cache/<sha>.png`. If two videos share an identical CTA scene, the second render reuses 90 frames instantly. This is a 30–50% speedup on batches.

3. **`nbn doctor` (Phase 9).** A pre-flight that catches the five most common failures: Node not installed, fonts missing, ffmpeg < 6, Satori not running, D1 token expired. Each check prints a one-line fix.

4. **`nbn preview --scene reveal --frame 120 --spec bertha-2024.yaml` (Phase 4).** Renders one frame and opens it with `xdg-open`/`open`. Critical for iterating on templates without re-rendering 540 frames.

5. **Tier badge is a Satori component, not an image (Phase 2).** Pass `tier` into every template; render the colored pill text-side. Keeps the brand consistent and lets future tiers ship without new assets.

6. **Safe-area overlay debug mode (Phase 4).** `nbn render --debug-safe` overlays a 50% red translucent rectangle on the TikTok-unsafe zones. Saves Michael from shipping a video with the headline behind the caption box.

7. **Manifest carries Satori + ffmpeg versions (Phase 6).** When a regression hits in 6 months, the manifest tells you which version drift caused it.

8. **Refuse to render names with offensive history without `--force` (Phase 7).** Maintain `fixtures/blocklist.txt` (Adolf, etc.). The classifier flags them; the runner halts with a message explaining the editorial concern. Michael can override per-batch but cannot do so accidentally.

9. **Smoke spec ships with the repo (Phase 0).** `batches/smoke.yaml` containing only Bertha. `make smoke` is the heartbeat of the whole project. CI runs it. Michael runs it before every commit.

10. **Render times in manifest (Phase 6).** Per-scene and total. After a month, Michael can graph these and know when Satori or ffmpeg got slower.

---

## 8. Common pitfalls (read before coding)

- **Satori font loading.** Satori does not read system fonts. Read the TTF bytes at boot. If you forget, every render produces invisible text on a dark background and looks blank.
- **`yuv420p` is non-negotiable.** Without `-pix_fmt yuv420p`, TikTok's web uploader rejects the file silently in Safari. Some clients show a thumbnail and never play.
- **xfade offset arithmetic.** The `offset` is when the transition *starts*, not when the next scene starts. For two 3s scenes with a 0.2s xfade, offset is `3.0 - 0.2 = 2.8`. Get this wrong and you get black flashes.
- **ffmpeg `image2` demuxer and leading zeros.** `frame_%03d.png` requires `000`, `001`, ...; padding mismatches silently truncate the sequence. Use `f"{n:03d}"` everywhere.
- **D1 rate limits.** Cloudflare D1's HTTP API rate-limits at ~50 req/s. Batch your reads. Pull the full series for a name in one query, not one row per year.
- **PNG color profile drift.** resvg embeds sRGB; ffmpeg may convert to BT.709. Force `-colorspace bt709 -color_primaries bt709 -color_trc bt709` in the encode to keep crimson looking like crimson on iPhones.
- **macOS Gatekeeper on the Node binary.** If installing Node via `.pkg`, the Satori service may stall on first run. Recommend `nvm` in the README.
- **Don't trust the SSA's 1880 records.** Counts under 5 are suppressed; a count of 5 may mean "5 to 9." The classifier treats 5 as a hard floor for CRITICAL evaluation. Document this in `classifier.py`.

---

## 9. Acceptance test for the whole project

The agent declares done when **all** of the following are true:

1. `git clean -fdx && make setup && make smoke` produces `out/bertha-2024.mp4` matching the golden hashes.
2. `make test` runs in under 30s with 100% of tests passing.
3. `make lint` and `make typecheck` are clean.
4. `nbn doctor` exits 0.
5. `nbn batch batches/week-1.yaml` produces 14 MP4s in under 15 minutes total wall time.
6. `RUNBOOK.md`, `ARCHITECTURE.md`, and `README.md` are filled in with no `TODO` markers.
7. The smoke video, played on an iPhone, looks correct: crimson dot at current year, faded gray axis, Source Serif 4 Black headline, no content in TikTok's safe-area exclusion zones.

When all seven hold, commit with the message `feat: nobodynamed video pipeline v1.0` and stop. Do not invent further features.

---

## 10. Out of scope (explicitly)

- Voiceover generation (Phase 8 of a future v2).
- TikTok auto-upload (compliance and rate-limit landmines).
- Web UI for non-technical editing.
- Multi-language support (the SSA dataset is English/US-only).
- Per-state breakdowns (the D1 schema doesn't carry state-level data yet).
- Sound effects / music licensing.

If Michael asks for any of the above during execution, surface the question; do not implement.

---

## Appendix A — `Makefile` (canonical)

```makefile
.PHONY: setup smoke render batch test lint typecheck doctor clean

setup:
	uv sync
	cd satori-service && pnpm install
	@echo "→ place SourceSerif4-Black.ttf and SourceSerif4-Regular.ttf in satori-service/fonts/"

satori:
	cd satori-service && pnpm dev

smoke:
	uv run nbn render --spec batches/smoke.yaml

batch:
	uv run nbn batch batches/week-1.yaml

test:
	uv run pytest -x -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy --strict src

doctor:
	uv run nbn doctor

clean:
	rm -rf out/ .pytest_cache .mypy_cache .ruff_cache
```

## Appendix B — environment variables

```
SATORI_URL=http://localhost:3001
D1_URL=https://api.cloudflare.com/client/v4/accounts/<acct>/d1/database/<db>/query
D1_TOKEN=<scoped token, read-only>
OUT_DIR=./out
FONT_DIR=./satori-service/fonts
LATEST_YEAR=2024
LOG_LEVEL=INFO
```

## Appendix C — first commit checklist

- [ ] `AGENTS.md` (this file) committed unchanged
- [ ] `pyproject.toml` with pinned versions
- [ ] `satori-service/package.json` with pinned versions
- [ ] `.python-version` set to `3.12`
- [ ] `.gitignore` includes `out/`, `node_modules/`, `.venv/`, `*.mp4`, `frames/`, `.env`
- [ ] `.env.example` committed; `.env` ignored
- [ ] `ARCHITECTURE.md` stub with the two-process diagram
- [ ] `README.md` one-screen quickstart
- [ ] Empty `RUNBOOK.md` with section headings only

Once the checklist is green, begin Phase 0.

---

*End of AGENTS.md.*
