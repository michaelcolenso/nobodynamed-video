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
classifier.classify_dimensions(counts)
  → prevalence + trajectory + historical shape
  → conservative legacy Tier adapter for presentation
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
ffmpeg concat (BT.709 limited-range conversion) + audio mux
        │
        ▼
out/<id>.mp4  (1080×1920, 30fps, 540-frame/18.0s stream, H.264, AAC, faststart)
        │
        ▼
RenderManifest → out/<id>.json
  (provenance, claim ledger, classifications, hashes, versions, timing)
        │
        ▼ after fatal QC
releases/<id>/
  (MP4, cover, manifest, claims, copy, transcript, source note, alt text)
```

---

## Scene timing

```
 0s          3s          9s         15s        18s
 ├───────────┼───────────┼───────────┼──────────┤
 │  hook.tsx │ reveal.tsx│narrative.tsx│ cta.tsx │
 │   90 fr   │  180 fr   │  180 fr   │  90 fr  │
 └───────────┴───────────┴───────────┴──────────┘
       ↑ straight concat — no transitions
```

Total: 540 frames at 30fps = 18.00s, carried 1:1 into the video stream.

The four scenes are windows over one continuous shared-canvas program, so
they are joined with a straight concat. (The original four-template design
crossfaded scenes with 0.2s xfades; once the canvas became continuous, the
xfades only ghosted the picture against itself and trimmed the video stream
to 17.4s, leaving a frozen 0.6s tail in the 18.0s container.)

Color: frames are full-range sRGB PNGs. Composition explicitly converts
RGB→YUV with the BT.709 matrix and limited (tv) range, matching the stream
tags — swscale's default BT.601 matrix visibly shifts the brand crimson
toward orange when players decode with the tagged BT.709.

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

Frames are cached at `out/.cache/<sha256>.png` where the hash covers renderer source, template, and props. On a batch run, identical frames are reused. Release artifacts exclude the frame/cache tree.

## Trust boundary

Test, preview, and publish are explicit data modes. Publish mode requires non-synthetic provenance and the newest year exposed by the selected source. SSA-suppressed and missing observations remain distinct from observed counts. Cultural-event copy requires an evidence record plus an observed decline threshold; all executable copy is filtered through typed/numeric guards before rendering.

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
