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

The canonical Cloudflare credentials for this project are `D1_URL` and `D1_TOKEN`.
`D1_URL` contains the Cloudflare account path, which the application uses to infer the
Workers AI account ID. `D1_TOKEN` is used for D1 access and is also the fallback token for
Workers AI narration. The token therefore needs the permissions required by the operations
you run, including Workers AI narration for approved story renders.

The application still supports optional `CLOUDFLARE_ACCOUNT_ID` and
`CLOUDFLARE_API_TOKEN` overrides, but the GitHub launch workflow does not require them.
Keep all real credentials in the gitignored `.env` file or GitHub Actions secrets. Never put
a real token in `.env.example`, a story, a batch file, a manifest, logs, or a commit. If any
credential ever appears in logs, revoke or rotate it before reuse.

The GitHub launch workflow requires repository secrets named exactly `D1_URL` and
`D1_TOKEN`. The six launch stories read their facts from checked-in verified SSA snapshots;
D1 is not queried for those facts during release. `D1_URL` is still supplied so the
application can infer the Workers AI account ID, and `D1_TOKEN` supplies the narration
authorization used by the existing CLI configuration.

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

1. Confirm only the presence of `D1_TOKEN`; never print it.
2. Confirm `D1_URL` contains the expected `/accounts/<account-id>/` path so the account ID
   can be inferred.
3. Confirm the token has the Workers AI permissions needed by the narration models.
4. Re-run the story score to ensure the script is within 24–36 words.
5. Cached audio lives under `out/.cache/narration`; a changed script or voice naturally
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
Each release story must carry current human approval bound to its exact content and verified
data snapshot.

1. Refresh snapshots when needed: download the complete official SSA `names.zip`, then run
   `uv run python scripts/fetch_ssa.py /path/to/names.zip --year 2025 --out data/ssa-2025`.
   A refresh changes snapshot bytes; update story hashes/claims and obtain fresh approval.
2. After explicit human approval, use `uv run nbn story approve <story-path> --reviewer <reviewer>`
   for each approved story. Never insert approval metadata to bypass review.
3. Set GitHub Actions repository secrets `D1_URL` and `D1_TOKEN`. `D1_URL` supplies the
   account path used to infer the Workers AI account ID; `D1_TOKEN` supplies the narration
   token fallback already used by the CLI.
4. In GitHub Actions, manually run the `CI` workflow on `main` with `batch=launch-six`.
   The legacy `render_launch` shortcut remains supported. The render job verifies
   approvals, the two release secrets, and every current D1 count/rank against the
   approved snapshots before starting Satori or narration.
5. Inspect the six narrated MP4s and QC reports from the Actions artifact. Check phone-size
   legibility, pronunciation, word alignment, timing and historical interpretation.
6. A fully successful workflow stages `out/launch-six.summary.json` into a verified release
   and publishes the release artifacts to the `videos` branch. That branch is an artifact
   destination, not a TikTok upload.

Missing approval, missing release credentials, missing narration, silence, failed QC,
missing provenance and partial batches block release. Stale files from earlier runs cannot
enter the staged publication.

### Next-six branch publication

`Render Next Six` remains manual-only and runs from `main`. It publishes only after
D1 snapshot verification, content-bound human approval checks, rendering/QC,
release staging, and the verified-release artifact upload all succeed. Publication
adds the 25 staged files (six MP4/manifest/story/source packages and the batch
summary) to the existing `videos` branch, preserving other files and history.
Identical releases produce no commit. A concurrent branch update rejects the
normal push; publication never force-pushes or automatically rerenders.

To recover an already successful run without rendering again, first verify the
source run and all its gates succeeded, download its `next-six-release-<sha>`
artifact, and confirm the story/source approvals still match the source commit.
From a checkout with the publisher and authenticated Git access, run:

```sh
uv run python -m nobodynamed_video.publish_release /path/to/downloaded-release SOURCE_COMMIT_SHA
```

The publisher rechecks package completeness and QC summary, rejects unexpected
files, and commits only the selected batch's package paths. It is not a substitute for
checking the source run's D1, approval, and artifact-upload results. After a
concurrent-push rejection, inspect the new branch state before retrying this
publication command with the same verified artifact.

### Approved ten-story batch

The September 12, 2026 approval covers `batches/viral-ten.yaml`: Taylor, Wednesday,
Chad, Shirley, Maverick, Khaleesi, Luna, Britney, Wendy, and Adolph. Every approval
is bound to corrected copy and an archive-pinned source. The verification record is
`research/viral-ten-2025.verification.json`.

Run **CI → Run workflow → main → batch: viral-ten**, leaving `render_launch` false.
The default `batch=none` runs checks only. Pushes and pull requests never render.
CI verifies the selected batch against current D1, uses the bounded-narration
renderer, stages only a complete QC-passed batch, uploads the verified release,
and appends its packages to `videos` without force-pushing. Launch and next-six
are also supported by the same selector; the separate `Render Next Six` action
remains compatible.

Before uploading any new MP4 to TikTok, inspect its pronunciation, caption timing,
phone-size legibility, and historical interpretation. Story approval authorizes
production; a successful render and final video review are separate milestones.
