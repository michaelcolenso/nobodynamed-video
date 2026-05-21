# ARCHITECTURE.md — nobodynamed-video

## Overview

nobodynamed-video is a two-process pipeline: a Python orchestrator and a Node.js Satori sidecar. They communicate over HTTP. Python drives all business logic, data access, scheduling, and ffmpeg orchestration. Node handles JSX-to-PNG rendering via Satori, which is identical to the renderer used on nobodynamed.com for OG images.

---

## Two-process design

```
┌─────────────────────────────────────────────┐
│  Python orchestrator (nbn CLI)              │
│                                             │
│  config.py → models.py                      │
│       │                                     │
│  data/source.py (DataSource protocol)       │
│    ├── d1_source.py  (Cloudflare D1 HTTP)   │
│    └── sqlite_source.py  (local fixture)    │
│       │                                     │
│  data/classifier.py  →  Tier enum           │
│       │                                     │
│  batch/spec.py  →  VideoSpec                │
│       │                                     │
│  scenes/*.py  →  Scene list                 │
│       │                                     │
│  render/frame_planner.py  →  FramePlan      │
│  render/hyperframes.py   →  Scalar tracks   │
│       │          │                          │
│       │    render/satori_client.py ──────── │── HTTP POST :3001/render
│       │                                     │
│  render/golden.py  (hash comparison)        │
│       │                                     │
│  compose/ffmpeg.py  (subprocess ffmpeg)     │
│  compose/audio.py   (optional bed mix)      │
│  compose/manifest.py → RenderManifest JSON  │
│                                             │
└─────────────────────────────────────────────┘
                         │
              HTTP JSON (localhost:3001)
                         │
┌─────────────────────────────────────────────┐
│  Node.js Satori sidecar                     │
│                                             │
│  src/server.ts  (Express, POST /render)     │
│  src/render.ts  (Satori → resvg → PNG)      │
│  src/fonts.ts   (load TTF bytes at boot)    │
│  src/templates/                             │
│    ├── shared.tsx   (brand constants)       │
│    ├── hook.tsx     (3s opening scene)      │
│    ├── reveal.tsx   (6s name reveal)        │
│    ├── narrative.tsx (6s data story)        │
│    └── cta.tsx      (3s call to action)     │
│                                             │
│  fonts/                                     │
│    ├── SourceSerif4-Black.ttf               │
│    └── SourceSerif4-Regular.ttf             │
└─────────────────────────────────────────────┘
```

---

## Data flow

```
SSA D1 database (or local SQLite fixture)
        │
        ▼
DataSource.fetch(name, sex)  →  list[YearCount]
        │
        ▼
classifier.classify(counts)  →  Tier
  (extinction-watch / cultural-collapse / declining /
   stable / rising / resurrected)
        │
        ▼
VideoSpec(id, name, sex, tier, counts, fps=30)
        │
        ▼
Scene list:  [Hook(3s), Reveal(6s), Narrative(6s), CTA(3s)]
        │
        ▼
FramePlanner.plan(spec, scenes)  →  list[FrameJob]
  Each FrameJob: { scene, frame_index, t, template, props }
  Motion-heavy scenes can sample declarative hyperframe tracks for
  chart reveals, dot landings, and staged text fades.
        │
        ▼
SatoriClient.render(template, props)  →  PNG bytes
  (cached by SHA-256 of template+props)
        │
        ▼
out/<id>/frames/<scene>_<NNN>.png
        │
        ▼
ffmpeg concat + xfade + audio mux
        │
        ▼
out/<id>.mp4  (1080×1920, 30fps, H.264, AAC, faststart)
        │
        ▼
RenderManifest → out/<id>.json
  (frame hashes, render times, satori version, ffmpeg version)
```

---

## Scene timing

```
 0s          3s          9s         15s        18s
 ├───────────┼───────────┼───────────┼──────────┤
 │  hook.tsx │ reveal.tsx│narrative.tsx│ cta.tsx │
 │   90 fr   │  180 fr   │  180 fr   │  90 fr  │
 └───────────┴───────────┴───────────┴──────────┘
       ↑ xfade 0.2s at offsets: 2.8s, 8.6s, 14.4s
```

Total: 540 frames at 30fps = 18.00s

xfade offsets (transition starts, not scene starts):
- hook → reveal: offset = 3.0 - 0.2 = 2.8
- reveal → narrative: offset = (3 + 6) - 0.2 = 8.6
- narrative → cta: offset = (3 + 6 + 6) - 0.2 = 14.4

---

## HTTP interface (Python → Node)

### POST /render

Request body:
```json
{
  "template": "hook",
  "props": {
    "name": "Bertha",
    "tier": "extinction-watch",
    "frame": 0,
    "total_frames": 90
  },
  "width": 1080,
  "height": 1920
}
```

Response: PNG bytes (Content-Type: image/png)

### GET /health

Returns 200 `{"status": "ok", "satori_version": "0.10.13"}` when fonts are loaded.

---

## Frame caching

Frames are cached at `out/.cache/<sha256>.png` where the hash covers the serialized `(template, props)` pair. On a batch run, identical CTA scenes across all videos are rendered once and reused. This cuts batch render time by 30–50%.

---

## Directory layout rationale

- `src/nobodynamed_video/` — Python package (hatchling wheel target)
- `satori-service/` — isolated Node process; owns all JSX and font concerns
- `batches/` — YAML specs checked into git; reproducible batch definitions
- `fixtures/` — golden frame hashes + test blocklist; versioned reference data
- `out/` — gitignored render outputs
- `scripts/` — one-off operational scripts (SSA fetch, fixture builder, doctor)
- `tests/` — pytest unit + integration tests

---

## Brand constants

| Token | Value |
|---|---|
| Background | `#14110E` |
| Headline font | Source Serif 4 Black |
| Body font | Source Serif 4 Regular |
| Accent (crimson) | `#A21F1F` |
| Faded gray | `#B5B0A0` |
| Canvas | 1080 × 1920 px (9:16) |
| Frame rate | 30 fps |
