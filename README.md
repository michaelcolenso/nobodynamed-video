# nobodynamed-video

Agent-driven pipeline that turns SSA baby name records into 18-second 9:16 TikTok videos in the nobodynamed.com v3 brand system.

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
# Edit .env with your D1_URL and D1_TOKEN

# 4. Start the Satori sidecar (leave running in a separate terminal)
make satori

# 5. Run preflight check
make doctor

# 6. Render the smoke test video
make smoke
# → out/bertha-2024.mp4
```

## Key commands

| Command | Description |
|---|---|
| `make setup` | Install Python + Node dependencies |
| `make satori` | Start Node Satori sidecar on :3001 |
| `make smoke` | Render Bertha 2024 (pipeline health check) |
| `make batch` | Render all 14 videos in batches/week-1.yaml |
| `make test` | Run pytest suite |
| `make lint` | Ruff check + format check |
| `make typecheck` | mypy --strict |
| `make doctor` | Preflight: Node, ffmpeg, fonts, Satori, D1 |
| `make clean` | Remove out/, caches |

## Output

All renders go to `out/`. Each video gets a directory of PNG frames and a final MP4:

```
out/
  bertha-2024/
    frames/
      hook_000.png ... hook_089.png
      reveal_000.png ... reveal_179.png
      narrative_000.png ... narrative_179.png
      cta_000.png ... cta_089.png
  bertha-2024.mp4
  bertha-2024.json   ← RenderManifest with frame hashes + timing
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the two-process design, data flow diagram, and scene timing.

## Operations

See [RUNBOOK.md](RUNBOOK.md) for daily workflow, token rotation, adding templates, and debugging.

## Agent build plan

See [AGENTS.md](AGENTS.md) for the full phased implementation plan.

## Requirements

- Python 3.12+ with `uv`
- Node 20+ with `pnpm`
- ffmpeg 6+
- SourceSerif4-Black.ttf and SourceSerif4-Regular.ttf (place in `satori-service/fonts/`)
- Cloudflare D1 token with read access to the nobodynamed database (or use local SQLite fixture)
