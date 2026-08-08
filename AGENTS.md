# AGENTS.md — nobodynamed-video

Agent-driven pipeline: SSA baby name records (Cloudflare D1) → adaptive 9–14 second 9:16 TikTok MP4s in the nobodynamed.com v3 brand system. Two processes: Python orchestrator (`nbn` CLI) + Node Satori sidecar over HTTP. See ARCHITECTURE.md (design), RUNBOOK.md (ops), HANDOFF.md (current state + hard-won data quirks).

## Project
- Python 3.12+ (uv) package `nobodynamed_video` (src-layout, hatchling). Entry point `src/nobodynamed_video/cli.py` → console script `nbn`.
- Node 20+ sidecar `satori-service/` (pnpm; express + satori 0.10.13 + resvg) renders JSX → PNG on `POST :3001/render`.
- ffmpeg 6+ required. Output: `out/<id>.mp4` (+ PNG frames, + `<id>.json` RenderManifest).

## Commands (verified)
- `make setup` — `uv sync` + `pnpm install`; then place SourceSerif4 TTF fonts in `satori-service/fonts/`
- `make satori` — start Satori sidecar on :3001 (`PORT=3002 make satori` for alt; set `SATORI_URL` accordingly)
- `make smoke` — narrated render of `batches/smoke.yaml` → `out/bertha-2024.mp4` (needs sidecar + Cloudflare Workers AI credentials)
- `make smoke-frames` — render smoke frames without narration or MP4 composition
- `make pilot` / `make batch` — render the approved stories in `batches/pilot.yaml`
- `make doctor` — preflight: Node, ffmpeg, fonts, Satori, D1
- `make test` — `uv run pytest -x -q` (197 passed)
- `make lint` — `uv run ruff check src tests` + `ruff format --check src tests`
- `make typecheck` — `uv run mypy --strict src` (45 files)
- `make regen` — clear `fixtures/golden/**/*.sha256` so the next smoke re-bootstraps hashes
- `make clean` — remove `out/` + caches
- `uv run nbn render|batch|preview|doctor|smoke|captions stats|deprecate <tag>|reset --confirm`
- sidecar: `cd satori-service && pnpm dev|build|start|test`

## Architecture
- `config.py` — pydantic-settings from `.env`: Satori, D1, output/font paths, and Cloudflare Workers AI narration credentials/models
- `models.py` — pydantic v2 domain models including `StorySpec`, `WordTiming`, `NameRecord`, scenes, hooks, and cultural events
- `data/` — `DataSource` protocol: `d1_source.py` (D1 HTTP) / `sqlite_source.py` (`fixtures/ssa.sqlite`); `classifier.py` (six-tier thresholds, unit-tested); `ctx.py` (Ctx vars); `hooks.py`, `narratives.py`
- `batch/` — `spec.py` loads `batches/*.yaml` (+ hooks.yaml, narratives.yaml); `runner.py` orchestrates a run
- `scenes/` — `SceneProtocol`; hook / reveal / narrative / cta
- `render/` — `frame_planner.py` (`SCENE_DURATIONS` = timing source of truth), `hyperframes.py`/`motion.py`/`programs.py` (per-frame scalar tracks, chart draw), `satori_client.py` (HTTP render, SHA-256 frame cache `out/.cache`), `golden.py` (golden-hash QC)
- `compose/` — Cloudflare narration/alignment, ffmpeg composition, captions, lexicon/state, and render manifests
- `editorial/` — evidence-backed story scoring and approval gates; `analytics/` — retention-event summaries
- `qc/checks.py` — post-encode QC for adaptive duration/frame count, 1080×1920 output, narration, caption timing, and BT.709/tv color
- `satori-service/src/` — `server.ts` (POST /render, GET /health), `render.ts`, `fonts.ts`, `templates/` (`shared.tsx` brand constants, `canvas.tsx` = the single shared render template, plus hook/reveal/narrative/cta)
- CI: `.github/workflows/ci.yaml` — check job (ruff/mypy/pytest) + batch job renders `batches/week-*.yaml` → publishes MP4s to the `videos` branch

## Conventions
- `from __future__ import annotations` in every module; mypy --strict clean (40 files). Run lint + typecheck + tests before committing.
- Pydantic v2 models with `Field` constraints for all data; validate in models, not ad-hoc.
- Determinism by design: selections use `BLAKE2b(spec_id + label)` hashing (captions, hooks) — same spec → same output.
- Fixed canvas: 1080×1920 @ 30fps with an adaptive 9–14 second editorial envelope, four scene buckets, H.264 video, and narrated AAC audio.
- Golden QC: `fixtures/golden/<id>/*.sha256` write-if-missing / fail-on-mismatch. Intentional visual change → `make regen`, then re-render to re-bootstrap.
- ffmpeg color: must convert RGB→YUV with BT.709 + limited (tv) range — the wrong matrix shifts brand crimson (#A21F1F) toward orange.
- YAML-as-data: `batches/*.yaml`, `fixtures/captions.yaml`, hooks.yaml. Use ruamel.yaml with `preserve_quotes` for round-trip edits.
- Caption rules (`fixtures/captions.yaml`): ≤150 chars, 2–3 emotional words, 3–5 hashtags, ≥1 core tag, unique hashtag combo per video (`state/used_combinations.db` — gitignored, back it up), pinned comment ≤100 chars ending in `?`.
- Editorial voice: cold, editorial, mildly ominous, data-first ("if it reads like a mom-blog caption, kill it").
- Data quirks (HANDOFF.md §5): SSA suppresses counts <5 → sources zero-fill; charts always start at 1880; RESURRECTED has two guards. Never regress these.
- Never commit `.env`, `out/`, `state/*.db` (gitignored). Golden hashes ARE committed.
- hooks.yaml variables must exist in Ctx; the loader fails fast on missing vars.

## Notes
- `batches/AGENTS.md` is the caption-composition spec (CAPTIONS.md), NOT a generic agent-memory file — do not clobber it.
- Docs: ARCHITECTURE.md, RUNBOOK.md, HANDOFF.md, docs/PRO_SERIES_CHART_IMPLEMENTATION.md.
- `uv` prints a deprecation warning about `tool.uv.dev-dependencies` on every run — harmless; migrating to `dependency-groups.dev` is a follow-up.
- Python tests, Ruff, formatting, strict mypy, the Node build/tests, and an actual Satori smoke render should all pass before publishing visual changes.
