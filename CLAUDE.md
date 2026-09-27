# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

`AGENTS.md` (imported above) is the primary project brief: commands, module map, conventions, and data quirks. This file adds only what it lacks or gets wrong.

## Corrections to AGENTS.md / HANDOFF.md (verified 2026-09-27)
- Test suite is ~252 tests, not 197; `mypy --strict src` covers 52 files, not 40/45. Don't treat those counts as a pass criterion.
- Dev deps are already in `[dependency-groups] dev` in `pyproject.toml`. The "tool.uv.dev-dependencies" warning follow-up is done.
- CI's `batch` job does not glob `batches/week-*.yaml`. It runs only on `workflow_dispatch` on `main`, with a batch picked from a fixed list (`launch-six`, `next-six`, `viral-ten`, `gen-z`). It runs `scripts/render_story_batch.py batches/<name>.yaml`, then `python -m nobodynamed_video.release` stages the output and `python -m nobodynamed_video.publish_release` pushes it to the `videos` branch. To make a new batch renderable in CI, add it to the `options` list in `.github/workflows/ci.yaml`.
- CI's `check` job also runs `pnpm test && pnpm build` in `satori-service/`, so sidecar TS changes must pass both.
- Only `fixtures/golden/bertha-2024/{hook_f00.sha256,manifest.json}` are tracked (`render/golden.py`). A missing hash is written on first render, but the committed Bertha hook hash still fails on mismatch on a clean checkout. Treat a mismatch as a real regression unless the visual change was intentional, and in that case delete the hash and re-render.
- HANDOFF.md §7–8 (`/home/kimi`, the tsinghua mirror, fuse FS) describe a different sandbox. Ignore them here.

## Running tests
- Single test: `uv run pytest tests/test_story.py::test_cultural_story_requires_two_external_sources -q`
- Several tests (`test_cover_qc`, `test_narration_pacing`, `test_release_safety`) shell out to real `ffmpeg`. They fail with `FileNotFoundError` when ffmpeg isn't installed, and that is an environment gap, not a code bug.
- `tests/test_story.py::test_story_library_is_valid...` loads **every** `stories/*.yaml`. A YAML syntax error in any story file (for example, an unquoted `: ` inside a `subhead`) fails it.
- Sidecar: `cd satori-service && pnpm test` (node:test via tsx, `src/**/*.test.ts`).

## Editorial pipeline (big picture)
There are two render paths, chosen per batch entry:
1. **Story path**: the batch entry has a `story:` ref to `stories/<id>.yaml` (a `StorySpec`). `batch/spec.py` resolves it through `editorial/story.py`. That gate is a 100-point score with a 75 minimum. It also requires a 24–36 word script, SSA evidence, reviewed social copy, and approval metadata, and `cultural_rupture` needs at least two non-SSA sources. Rendering fails closed if the gate fails. Passing stories get Workers AI Aura narration and Whisper word timing (`compose/narration.py`, cached by account, model, voice, and script). Their duration is adaptive (`adaptive_duration()`: narration + 0.85s loop beat, 9–14s, quantized to 30fps). The 11s motion program is time-warped to fit that duration.
2. **Legacy path**: no `story:` field. Fixed 11.0s with hand-curated `headline`/`subhead`/`narrative`/`support` overrides in the batch YAML. Load-time `COPY_CAPS` and a cause-leak lint apply.

Story workflow: `nbn story propose --name X --sex F --kind comeback` → edit `stories/x-2024.yaml` → `nbn story score <file>` → `nbn story approve <file> --reviewer <name>`. Approval is a human decision; never approve on someone's behalf.

Archetypes / visual modes: `one_hit`, `cultural_rupture`, `long_decline`, `comeback`. They change scene allocation and accent color (amber = authored/long history, crimson = rupture/decline, emerald = return) while sharing the single `canvas.tsx` template.

## Long-form episodes (60-90s)
`longform/<id>.yaml` (`LongFormSpec`) is an episode assembled from 3-8 already-approved chapter stories, with a narrated title card before and after (`title` Satori template, `longform/bookends.py`).
- Gate (`longform/spec.py`): every chapter must pass `evaluate_story`. Each title-card script must be 8-22 words; narration longer than the 10s card is pace-fitted (up to 1.5x) or rejected, never cut off. The caption needs 3-5 hashtags and a pinned comment ending in "?". Every combined total the copy states goes in `aggregate_claims`, and the gate recomputes it from the pinned chapter snapshots. Approval digests the episode copy plus the exact bytes of each chapter file, so editing a chapter story invalidates the episode approval.
- Chapters render through the normal `render_spec`, with `VideoSpec.chapter_label` set. That adds "PART n OF N" to the header, drops the short-form loop bridge, and swaps the 0.85s loop beat for a 0.4s hold. Each chapter passes the normal per-video QC. `build_concat_cmd` then joins the segments with one loudness pass, and `run_longform_checks` applies the 60-90s envelope.
- Budget: narrated chapters run about 13.9s each, so six chapters plus title cards exceed 90s. That is why `gen-z-five-2025` has five chapters.
- Commands: `uv run nbn longform check|approve|render <file>`. `render --no-narration` makes a local preview that is never releasable. The narrated render needs the Workers AI credentials, which only CI has. Before rendering, `python -m scripts.verify_batch_data <episode> --longform [--preview]` re-checks every chapter snapshot against D1.

## Render invariants that span files
- The manifest (`compose/manifest.py`, `out/<id>.json`) is the source of truth for frame count and duration. QC (`qc/checks.py`) derives its expectations from it, never from hardcoded 330 frames / 11s.
- The Satori frame cache key (`render/satori_client.py`, `out/.cache`) includes a digest of the sidecar template source. Template edits invalidate cached frames automatically, and you don't need to clear the cache by hand.
- Chart pacing is time-domain (see HANDOFF §4 and `docs/ANIMATION_TIMING.md`). Don't reintroduce per-segment-index pacing. Read that doc before touching `programs.py`/`hyperframes.py`/`smoothPathD`.
- `nbn preview` layout differs from batch render layout. Use preview only for motion/chart QA, not for layout QA.
- Every narrated video must show the `AI NARRATION` disclosure (`render/programs.py`) and include `#AIVoice` in its caption. Neither is verified on the output: the editorial gate checks `#AIVoice` on the StorySpec, and QC only checks the manifest's `ai_voice_disclosure` string, never a rendered frame. If you touch templates, programs or captions, confirm both by inspecting a smoke render.

## Configuration
`.env` (see `.env.example`): `SATORI_URL`, `D1_URL`, `D1_TOKEN`, `LATEST_YEAR`, and optional Workers AI overrides. The Cloudflare account ID is inferred from `D1_URL`, and narration uses `D1_TOKEN` unless `CLOUDFLARE_API_TOKEN` is set. `NARRATION_ENABLED` / `--no-narration` skips the AI calls. Without D1 credentials, `fixtures/ssa.sqlite` backs the SQLite source. Some stories, such as Kunta, need D1.
