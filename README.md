# nobodynamed-video

Source-backed pipeline that turns official SSA baby-name records into audited 9:16 social videos in the nobodynamed.com v3 brand system.

One command renders an MP4 ready for TikTok upload.

## Quick start

```bash
# 1. Install dependencies
make setup

# 2. Place fonts (required — Satori will not render without them)
#    Copy SourceSerif4-Black.ttf and SourceSerif4-Regular.ttf to:
#    satori-service/fonts/

# 3. Configure environment
cp .env.example .env
# Test mode uses the explicitly synthetic fixture and can never publish.

# 4. Start the Satori sidecar (leave running in a separate terminal)
make satori
# If :3001 is already in use, either reuse the running sidecar or:
# PORT=3002 make satori
# SATORI_URL=http://localhost:3002 make doctor

# 5. Run preflight check
make doctor

# 6. Render the smoke test video
make smoke
# → out/bertha-2025.mp4
```

## Key commands

| Command | Description |
|---|---|
| `make setup` | Install Python + Node dependencies |
| `make satori` | Start Node Satori sidecar on `:3001` (or `PORT=3002 make satori`) |
| `make smoke` | Render Bertha with the newest dataset year |
| `make batch` | Render all 14 videos in batches/week-1.yaml |
| `make test` | Run pytest suite |
| `make lint` | Ruff check + format check |
| `make typecheck` | mypy --strict |
| `make doctor` | Preflight: Node, ffmpeg, fonts, Satori, D1 |
| `uv run nbn data doctor` | Validate provenance and publication readiness |
| `python scripts/fetch_ssa.py` | Import the newest official SSA archive atomically |
| `uv run nbn goldens update` | Explicitly replace reviewed golden hashes |
| `uv run nbn ops --help` | Publishing ledger, metrics import, and content queue |
| `make clean` | Remove out/, caches |

## Data and editorial safety

The SSA national files omit rows with fewer than five births. The pipeline models a current observation as `observed`, `below_reporting_threshold`, or `missing_data`; an absent row is never converted into an exact zero or an “extinct” claim. Runtime year selection comes from the active dataset rather than a hardcoded constant.

Three modes make the boundary explicit:

- `test`: synthetic fixtures are allowed and artifacts are non-publishable.
- `preview`: synthetic data is allowed, with provenance carried into every artifact.
- `publish`: synthetic data, stale year overrides, missing sources, unsupported cultural events, caption exhaustion, and QC failures stop the batch.

Import official local data with `python scripts/fetch_ssa.py --out data/ssa.sqlite`, set `SQLITE_FIXTURE=data/ssa.sqlite`, `DATA_MODE=publish`, and run `uv run nbn data doctor` before rendering. D1 remains supported for production.

Classification is explainable and separates current prevalence, recent trajectory, and historical shape. The old six-tier value remains only as a conservative presentation adapter.

## Formats and releases

Batch entries accept `format: fast`, `explainer`, or `deep_story` (18, 40, or 88 seconds). Audio remains pluggable through `--audio`; silent AAC is generated when no track is supplied.

After render and fatal QC pass, each item is packaged under `releases/<spec-id>/` with the MP4, cover, manifest, claim ledger, caption, pinned comment, transcript, source note, and alt text. Caption combinations are reserved during rendering and committed only after QC, so failed rerenders do not consume state.

Use `nbn ops record-publish` to map a release to a platform post, `nbn ops import-metrics` for portable analytics CSVs, and `nbn ops enqueue` for a source-agnostic content queue. Store campaign/UTM identifiers in the publication URL or experiment label.

## Output

All renders go to `out/`. Each video gets a directory of PNG frames and a final MP4:

```
out/
  bertha-2025/
    frames/
      hook_000.png ... hook_089.png
      reveal_000.png ... reveal_179.png
      narrative_000.png ... narrative_179.png
      cta_000.png ... cta_089.png
  bertha-2025.mp4
  bertha-2025.json   ← provenance, classifications, claims, frame hashes, timing
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the two-process design, data flow diagram, and scene timing.

## Operations

See [RUNBOOK.md](RUNBOOK.md) for daily workflow, token rotation, adding templates, and debugging.

## Requirements

- Python 3.12+ with `uv`
- Node 20+ with `pnpm`
- ffmpeg 6+
- SourceSerif4-Black.ttf and SourceSerif4-Regular.ttf (place in `satori-service/fonts/`)
- Cloudflare D1 token with read access to the authoritative database, or an official local SSA import

## Governance

Project code is MIT-licensed. Bundled Source Serif 4 fonts remain under the SIL Open Font License; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Generated releases should not ship until `DATA_MODE=publish`, the data doctor, render checks, and QC all pass.
