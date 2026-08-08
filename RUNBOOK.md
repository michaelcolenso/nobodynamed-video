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

The local fixture supports Alexa, Bertha, and Hazel but not Kunta. Use configured D1 access
for Kunta or render the other pilots locally. D1 requires a URL and either an explicit token
or a working Wrangler login.

### Golden-frame change

Golden hashes cover the first hook and reveal frames. Inspect visual changes before
regenerating them; do not accept new hashes solely to clear a failure.

## Annual SSA update

Update `LATEST_YEAR`, refresh the SQLite/D1 data, revise evidence counts and story IDs,
re-score every affected story, and obtain fresh human approval before rendering.
