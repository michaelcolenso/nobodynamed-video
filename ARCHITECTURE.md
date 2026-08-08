# Architecture

## System shape

The project has a Python editorial/render orchestrator and a Node Satori sidecar.

```text
SSA SQLite or D1
      │
      ▼
VideoContext ── StorySpec evidence and approval gate
      │
      ├── Workers AI Aura WAV ── Whisper V3 Turbo caption timing
      │
      ▼
adaptive 9–14s motion program ── HTTP ── Satori PNG renderer
      │                                      │
      └──────── frame_%04d.png ◀─────────────┘
                         │
                         ▼
         ffmpeg H.264 + narrated AAC master
                         │
                         ▼
              MP4 + manifest + QC report
                         │
                         ▼
               retention decision report
```

## Editorial contract

`StorySpec` is the unit of publication. It contains the archetype, thesis, display copy,
24–36 word script, evidence, visual anchors, social copy, voice direction, score, and
approval. The scorer uses inspectable signals across evidence, premise, hook, script,
visual plan, and sharing. Rendering fails closed below 75 or without approval.

The four visual modes are `one_hit`, `cultural_rupture`, `long_decline`, and `comeback`.
They change scene allocation, status language, and accent treatment while sharing one
continuous canvas. Amber marks authored/long-history beats, crimson marks rupture and
decline, and emerald marks return.

## Narration and timing

Cloudflare Workers AI Aura 2 English produces linear-16 WAV narration; Workers AI Whisper
Large V3 Turbo returns transcription timing for the caption compositor. The normalizer
accepts word data, segment timing, or WebVTT cues and falls back to duration-weighted
script timing. The cache identity covers account, model, transcription model, voice, and
exact script. No secret is written to a manifest.

The reviewed target duration is expanded when narration plus a 0.85-second loop beat
needs more room, capped at 14 seconds, then quantized to whole 30 fps frames. The 11-second
motion program is smoothly time-warped to that runtime. In the final 0.75 seconds, chart,
stats, narrative, and footer recede while the opening diagnosis returns, creating a
purposeful loop seam.

## Rendering and composition

Python samples the shared-canvas program and writes a single global sequence:

```text
out/<spec-id>/frames/frame_0000.png ... frame_NNNN.png
```

Each frame cache key includes the complete Satori source digest, template, and props, so
template edits invalidate stale output while preserving cross-render reuse. The existing
cluster-friendly Satori worker and smooth chart-speed work remain intact.

ffmpeg receives one image sequence plus narration. Optional audio is mixed at 10% under
the voice; the default has no music. The final audio target is -14 LUFS and -1 dBTP. PNG
sRGB is explicitly converted to BT.709 limited-range YUV420p before the H.264 encode.

## Manifest and QC

The manifest is the source of truth for frame count and duration. QC checks dimensions,
cover legibility, adjacent opening motion, frame count, stream duration, codec, color
metadata, black segments, audio presence and measured loudness, story score, narration
timestamps, and the AI-voice disclosure.

## Retention loop

`nbn analytics import` stores per-video snapshots in `state/retention.db`.
`nbn analytics report` joins the latest snapshot to manifests and computes:

- primary outcomes: completion rate, share rate, and watch-time ratio
- drivers: two-second and midpoint retention when present
- guardrails: at least 1,000 views before directional action and a QC-cleared manifest

Initial rules are deliberately provisional: 45% completion, 70% watch ratio, and 1.5%
share rate. Recalibrate them after 20 comparable posts rather than importing generic
creator benchmarks into a distinct format.
