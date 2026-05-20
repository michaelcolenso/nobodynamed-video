# nobodynamed-video
nobodynamed-video/
├── pyproject.toml
├── .env.example                  # SATORI_URL, D1_URL, OUT_DIR
├── README.md
├── ARCHITECTURE.md               # data flow, scene timing, render pipeline
├── src/nobodynamed_video/
│   ├── config.py                 # Pydantic Settings, .env loader
│   ├── models.py                 # NameRecord, Scene, VideoSpec, Tier
│   ├── data/
│   │   ├── ssa_loader.py         # pulls year/count series from D1
│   │   └── classifier.py         # six-tier logic (extinct, critical, declining, stable, rising, resurrected)
│   ├── scenes/
│   │   ├── base.py               # Scene protocol: duration, frames(), props
│   │   ├── hook.py               # 3s: name + provocative stat
│   │   ├── reveal.py             # 6s: animated chart
│   │   ├── narrative.py          # 6s: context line + tier badge
│   │   └── cta.py                # 3s: "nobodynamed.com" + crimson dot
│   ├── render/
│   │   ├── satori_client.py      # POST /render with template + props, gets PNG
│   │   ├── frames.py             # interpolates props across N frames at 30fps
│   │   └── motion.py             # Ken Burns, fade, number-count-up, type-on
│   ├── compose/
│   │   ├── ffmpeg_runner.py      # concat frame sequences, crossfade, scale to 1080x1920
│   │   └── audio.py              # silence bed or ambient, optional ElevenLabs hook
│   └── cli.py                    # `nbn render`, `nbn batch`, `nbn preview`
├── satori-service/               # Node sidecar, runs on :3001
│   ├── server.ts                 # Express + Satori + @resvg/resvg-js
│   └── templates/                # JSX templates matching v3 brand system
│       ├── hook.tsx
│       ├── reveal.tsx
│       ├── narrative.tsx
│       └── cta.tsx
├── batches/
│   └── week-1.yaml               # 14 video specs
├── tests/
│   ├── test_classifier.py        # tier boundaries
│   ├── test_scene_timing.py      # total duration = 18s
│   └── fixtures/
└── out/                          # gitignored mp4s
