# nobodynamed-video

An evidence-backed culture micro-documentary engine. It turns Social Security baby-name
history into adaptive 9–14 second vertical videos with reviewed premises, documentary
narration, word-timed captions, story-specific motion, and retention feedback.

The pipeline rejects weak or unapproved stories before it renders them.

## Quick start

```bash
make setup
cp .env.example .env
# Add CLOUDFLARE_API_TOKEN to the gitignored .env.

make satori       # separate terminal
make doctor
make smoke        # Bertha long-decline pilot
```

Approved stories use Cloudflare Workers AI Aura 2 English narration with the `luna`
speaker and Workers AI Whisper Large V3 Turbo timing. Generated speech is cached by
script, model, and voice. Every story video visibly discloses `AI NARRATION` and includes
`#AIVoice` in its reviewed caption.

## Editorial workflow

```bash
# Generate an evidence-first draft from SSA data.
uv run nbn story propose --name Hazel --sex F --kind comeback

# Inspect the deterministic 100-point gate.
uv run nbn story score stories/hazel-2024.yaml

# Record the one-time human approval. Rendering is automatic afterward.
uv run nbn story approve stories/hazel-2024.yaml --reviewer <name>

# Render the four-archetype pilot. Kunta requires the configured D1 source.
uv run nbn batch batches/pilot.yaml
```

The gate requires a score of at least 75, a 24–36 word script, a short opening beat,
a loop beat, SSA evidence, reviewed social copy, and approval metadata. A
`cultural_rupture` additionally requires at least two non-SSA sources.

The checked-in pilots cover:

- `Kunta` — one-hit cultural spike
- `Alexa` — cultural rupture
- `Bertha` — long decline
- `Hazel` — comeback

## Key commands

| Command | Purpose |
|---|---|
| `make smoke` | Render the narrated Bertha pilot |
| `make smoke-frames` | Render frames without narration or composition |
| `make pilot` | Render all four editorial archetypes |
| `uv run nbn preview ...` | Render one inspection frame |
| `uv run nbn analytics import export.csv` | Import per-video retention |
| `uv run nbn analytics report` | Produce the next-action retention report |
| `make test` | Run Python tests |
| `make lint` | Run Ruff checks |
| `make typecheck` | Run strict mypy |

## Outputs

```text
out/
  bertha-2024/
    frames/
      frame_0000.png
      frame_0001.png
      ...
  bertha-2024.mp4
  bertha-2024.json
  smoke.qc.html
```

The manifest records the approved thesis and score, script, word timestamps, narration
model and voice, disclosure, adaptive duration, audio targets, frame hashes, render
timings, and final social copy.

## Quality contract

- 1080×1920 at 30 fps, H.264, BT.709 limited range, 10 Mbps master
- one continuous global frame sequence; no scene crossfades or frozen tail
- 9–14 seconds based on the reviewed target and actual narration length
- narration mixed to -14 LUFS with a -1 dBTP target
- no baked-in music by default; add a native platform sound after upload
- QC derives frame and duration expectations from the manifest

See [ARCHITECTURE.md](ARCHITECTURE.md) for internals and [RUNBOOK.md](RUNBOOK.md) for
the operating workflow.
