# Operations runbook

## Daily workflow

1. Start the sidecar in another terminal with `make satori`.
2. Run `make doctor`.
3. Score and review any new `stories/*.yaml` file.
4. Record human approval with `nbn story approve`; never hand-edit a draft to `approved`.
5. Run `make smoke`, inspect the MP4 and QC report, then run `make pilot` or the target batch.
6. Upload the MP4 and add a low-volume native platform sound. Do not bake music into the
   default master.
7. Export per-video metrics, run `nbn analytics import <csv>`, then `nbn analytics report`.

## Credential handling

Cloudflare Workers AI powers narration and alignment. Put a token with Workers AI Read
and Edit permissions in `CLOUDFLARE_API_TOKEN` in the gitignored `.env` file. Set
`CLOUDFLARE_ACCOUNT_ID`, or let the pipeline infer it from `D1_URL`. Never put a real
token in `.env.example`, a story, a batch file, a manifest, logs, or a commit.

Use `--no-narration` only for frame/compositor diagnosis. A composed approved story without
narration fails QC by design.

## Story decisions

Use the retention report as an operating queue:

- low two-second retention: rewrite the hook and opening visual
- healthy opening but weak completion/watch ratio: reveal sooner or remove a middle beat
- healthy completion but weak shares: preserve the premise and strengthen the final turn
- healthy completion and shares after 1,000 views: scale that archetype

Treat the initial thresholds as internal hypotheses. Recalculate after at least 20 posts
with comparable runtimes and distribution.

## Debugging

### Satori failure

1. Check `GET /health` on the configured `SATORI_URL`.
2. Run `npm run build` inside `satori-service`.
3. Render one frame with `nbn preview`.
4. If the port is occupied, reuse the healthy sidecar or choose another `PORT` and update
   `SATORI_URL`.

### Narration failure

1. Confirm only the presence of `CLOUDFLARE_API_TOKEN`; never print it.
2. Check the account ID and Workers AI model settings in `.env`.
3. Re-run the story score to ensure the script is within 24–36 words.
4. Cached audio lives under `out/.cache/narration`; a changed script or voice naturally
   creates a new cache key.

### Data-source failure

Launch stories use checksummed official SSA snapshots in `data/ssa-2025/`; they never use
the illustrative SQLite fixture. A missing/changed snapshot or mismatched count claim blocks
rendering. Legacy non-story batches may still use SQLite or D1. D1 requires a URL and either
an explicit token or a working Wrangler login.

### Golden-frame change

Golden hashes cover the first hook and reveal frames. Inspect visual changes before
regenerating them; do not accept new hashes solely to clear a failure.

## Annual SSA update

Update `LATEST_YEAR`, refresh the SQLite/D1 data, revise evidence counts and story IDs,
re-score every affected story, and obtain fresh human approval before rendering.

## Verified six-video launch (2025 data)

Review `docs/LAUNCH_SIX_REVIEW.md` and the six files in `stories/launch-2025/`.
They are intentionally drafts. Existing approvals were removed from legacy scripts because
those scripts do not carry the required verified data bindings. The old pilot commands
therefore reject drafts; use the new launch batch after human review.

1. Refresh snapshots when needed: download the complete official SSA `names.zip`, then run
   `uv run python scripts/fetch_ssa.py /path/to/names.zip --year 2025 --out data/ssa-2025`.
   A refresh changes snapshot bytes; update story hashes/claims and obtain fresh approval.
2. After explicit human approval, use `uv run nbn story approve <story-path> --reviewer <reviewer>`
   for each approved story. Never insert approval metadata to bypass review.
3. Start Satori and configure Workers AI credentials as described above. D1 is unnecessary
   for these snapshot-backed stories.
4. Run `uv run nbn batch batches/launch-six.yaml`. Inspect the six MP4s and QC reports.
5. Run `uv run python -m nobodynamed_video.release out/launch-six.summary.json out/release`
   only after a fully successful batch. The destination must be empty.

Missing narration, silence, failed QC, missing provenance and partial batches block release.
The main-branch workflow renders only this explicit batch and stages its MP4, manifest,
story and source sidecars; stale files from earlier runs cannot enter that publication.
GitHub's `videos` branch is an artifact destination, not a TikTok upload.
