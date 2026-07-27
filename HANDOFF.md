# Handoff — nobodynamed-video

**As of:** 2026-07-27 · **HEAD:** `9cf9e35` (main) · **Status:** operational, week-3 batch rendering in CI

Pipeline that turns SSA baby-name data (Cloudflare D1 `name-vitals`) into 11-second 9:16 TikTok videos: Python planner → Satori/TS sidecar renders 1080×1920 PNG frames → ffmpeg → H.264/AAC MP4.

---

## 1. Current State

- **Live batch:** `batches/week-3.yaml` — 8 "One-Hit Wonder" names (Kunta, Arsenio, Moesha, Jkwon, Bethzy, Neymar, Khaleesi, Renesmee) with curated per-name copy. CI renders it on every push to main and publishes MP4s to the `videos` branch.
- **Last three commits** (all chart-motion work, newest first):
  - `9cf9e35` — Fluid draw: time-domain speed design (current motion system, see §4)
  - `fa00211` — Speed-based flatline pacing (FLAT_PACE_YPS=100) — superseded by 9cf9e35's smoothing
  - `ca8c4dc` — Two-phase draw pacing, dropped sine easing
- **Video spec:** 1080×1920 @ 30fps, exactly 11.000s, 10 Mbps CBR H.264, silent AAC track (add trending sound in TikTok editor at upload — deliberate, see §8).
- **Checks green:** mypy strict (40 files), ruff format+check, 139 pytest tests.

## 2. Architecture Map

| Path | Role |
|---|---|
| `src/nobodynamed_video/render/programs.py` | All timing constants + per-frame props assembly (Hyperframe scalar tracks) |
| `src/nobodynamed_video/render/frame_planner.py` | `SCENE_DURATIONS` — hook 1.0s / reveal 3.5s / narrative 5.0s / cta 1.5s |
| `satori-service/src/templates/canvas.tsx` | The single shared render template; `smoothPathD()` = chart draw math |
| `src/nobodynamed_video/data/classifier.py` | Deterministic badge tiers (EXTINCT/RESURRECTED/CRITICAL/RISING/DECLINING/STABLE) |
| `src/nobodynamed_video/data/d1_source.py`, `sqlite_source.py` | Name series fetch; both zero-fill suppressed years |
| `src/nobodynamed_video/batch/spec.py` | Batch YAML loader; per-name copy overrides; COPY_CAPS + cause-leak lint |
| `src/nobodynamed_video/qc/checks.py` | Post-encode QC (330 frames, 11.0s, resolution) |
| `src/nobodynamed_video/render/golden.py` | Golden-frame QC (write-if-missing, fail-on-mismatch) |
| `.github/workflows/ci.yaml` | check job (ruff/mypy/pytest) + batch job (renders `batches/week-*.yaml` → `videos` branch) |

## 3. Timing System (11s fixed)

```
t=0.0   header/diagnosis already readable (cover frame rule)
t=0.0–0.5   chart fades in
t=0.3–4.5   chart draw (DOT_LAND_T=4.5), linear progress → smoothPathD
t=5.2–6.0   stat cards fade in
t=6.5–7.2   narrative line    t=7.0–7.8  supporting line
t=8.8–9.5   support fades OUT (no footer collision — this was a bug, keep the sequencing)
t=9.5–10.4  footer fades in
```

## 4. Chart Motion (current design — canvas.tsx `smoothPathD`)

**Time-domain speed design.** Don't reintroduce segment-index pacing — that was the "mechanical" feel (a velocity step at every year boundary).

1. Series padded to 1880 in the render layer (`programs.py`), so flatline = years before first nonzero count.
2. Per-segment nominal seconds: flatline at `FLAT_PACE_YPS=100` y/s (capped at 30% of draw); story zone slope-weighted (`1 + 10·dy/maxDy`, flat runs cost 0.35 → ~35 y/s tail).
3. Speeds sampled on a 120 Hz grid → × smoothstep ramps (`RAMP_S=0.35` soft start/landing) → gaussian smooth (`SIGMA_S=0.08`) → integrate, normalize to exactly 4.2s.
4. Catmull-Rom control points clamped to baseline (`clampY`) — prevents curl below zero axis.

Expected feel: smooth acceleration → constant flatline → ~0.4s glide into story → slow deliberate story → soft landing. Kunta is the stress test (120 y/s flatline → 3 y/s wall).

## 5. Data Quirks (hard-won, don't regress)

- **SSA suppresses counts < 5** → absence ≠ "no data", absence ≈ 0. Sources zero-fill from last appearance to reference year. Without this, vanished names report stale `current` and classify wrong (Kunta was "stable" with "6 births in 2024").
- **Charts always start at 1880** — the steep rise is the story. Padding happens in the render layer only; classifier math uses the raw record.
- **RESURRECTED badge has two guards** (both were live bugs): first appearance must be >10y ago (Renesmee is a debut, not a resurrection), and current count must exceed count 5 years ago (Neymar was falling while wearing RESURRECTED).

## 6. Editorial System

- **Copy is per-name, hand-curated** in the batch YAML (`headline`/`subhead`/`narrative`/`support` overrides). Tier-templated copy misfires ("Vintage names are back" on Renesmee) — don't rely on it for published batches.
- **Rules:** tease the year, never the cause in the hook; causes only where documented in the blog; data-only otherwise. `COPY_CAPS` enforced at load; cause-leak lint rejects hooks that name the killing event for curated names.
- **Source material:** all 13 nobodynamed.com blog posts have been read; week-3 copy is fact-checked against the One-Hit Wonders article (e.g., Arsenio is NOT a 1989 debut — trickle existed prior; Bethzy is the unsolved mystery).
- Badge is computed deterministically by the classifier — never hand-set.

## 7. Ops

```bash
# Local setup (see §8 for why paths look like this)
export UV_PROJECT_ENVIRONMENT=/home/kimi/nbn/venv UV_LINK_MODE=copy \
       UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
uv sync
cp -r satori-service /home/kimi/nbn/ && cd /home/kimi/nbn/satori-service && pnpm install && pnpm build
node dist/server.js &   # sidecar on :3001

# Run
nbn preview --spec-id kunta-2024 --scene reveal --frame 30 --spec-file batches/week-3.yaml
nbn batch batches/week-3.yaml

# Before EVERY push (learned the hard way ×2):
mypy --strict src && ruff format --check src tests && ruff check src tests && pytest -x -q
```

- **Golden QC:** `fixtures/golden/*/manifest.json` is tracked; `.sha256` hashes are not. Write-if-missing means CI always passes on fresh runners; locally, delete a stale hash after intentional render changes.
- **D1 flakes:** httpx timeouts happen; retry. curl is more reliable for spot checks.
- **Secrets:** Cloudflare API token + account ID in `.env` (local) and GitHub Actions secrets (CI). GitHub PAT is used in the push remote URL — do not commit it into files.

## 8. Sandbox Environment Quirks (this dev machine)

- `/mnt/agents` is a fuse.portal FS: **no symlink support**, occasional "Transport endpoint is not connected" (retry).
- `/tmp` and `/home/kimi` are **wiped every few minutes** — venv, sidecar, and pnpm need periodic rebuilds (recipe above). PyPI is throttled → tsinghua mirror; pnpm via `npm i -g pnpm`; `UV_LINK_MODE=copy` mandatory.
- `nbn preview` layout ≠ batch render layout — preview is fine for motion/chart QA, NOT for layout QA.

## 9. Decisions & Pushbacks (feedback history)

**Adopted:** bigger fonts; 10 Mbps CBR (was 372 kbps); 1880 chart origin; brighter fade `#C9C4B5`; slope-weighted draw; deterministic badges; copy caps + cause lint; per-name copy overrides; fluid motion.

**Pushed back (stands):** no baked-in music — TikTok's algorithm favors trending sounds added in-app (documented in RUNBOOK); no 20% bottom safe-zone clearance — layout can't spare it, footer sits at 320px.

**Q&A decisions:** no template split (alternate editorially within one template); hook = tease year not cause; cadence 2/day week 1 then 1/day; copy variants = one call, three angles.

## 10. Roadmap / Open Threads

1. **Week-4 collapse slate** (awaiting go-ahead): Jessica Extinction Event, or Adolph/Hillary/Katrina/Alexa/Monica + Isis via cultural-event program. Workflow: PR-based review, not direct batch commit.
2. **Causative-phrase regex lint** for non-curated names (~10 lines, spec'd, not built).
3. **`LATEST_YEAR` → 2025** when SSA 2025 data lands (RUNBOOK documents the procedure).
4. **preview vs batch layout discrepancy** — flagged, unfixed.
5. **`feedback/` module** for mining TikTok comments into copy/selection decisions (spec exists).
6. Watch the week-3 renders on the `videos` branch after `9cf9e35` — Kunta specifically (most extreme speed range; any residual motion jerk shows there first).
