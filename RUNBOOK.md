# RUNBOOK.md — nobodynamed-video operational guide

## Daily render workflow

1. Ensure the Satori sidecar is running: `make satori` (in a separate terminal).
2. Confirm preflight: `make doctor` — all checks must pass before rendering.
3. Run the smoke test to confirm the pipeline is healthy: `make smoke`.
4. Run the weekly batch: `make batch` or `uv run nbn batch batches/week-1.yaml`.
5. Inspect `out/week-1.summary.json`; any render or QC failure exits non-zero.
6. Upload the complete package from `releases/<spec-id>/` and record the post with `nbn ops record-publish`.

---

## How to update SSA data

1. Run `python scripts/fetch_ssa.py --out data/ssa.sqlite`.
2. Set `SQLITE_FIXTURE=data/ssa.sqlite`, `DATA_MODE=publish`, and `LATEST_YEAR=0`.
3. Run `uv run nbn data doctor`; confirm the reported provenance and newest year.
4. Run the smoke render and inspect its claim ledger and QC report.
5. Keep the importer-produced checksum and import timestamp in the database metadata.

---

## How to add a new scene template

1. Create the JSX template at `satori-service/src/templates/<scene-name>.tsx`.
   Follow the pattern in `shared.tsx` for brand constants and prop types.
2. Register the template name in `satori-service/src/server.ts` template dispatch map.
3. Create the Python scene class at `src/nobodynamed_video/scenes/<scene-name>.py`,
   implementing the `Scene` protocol (duration_s, frames_at, template_name, props_at).
4. Add the scene to the pipeline in the relevant VideoSpec builder.
5. Write tests in `tests/test_<scene-name>.py` covering props_at at key frame indices.
6. Run `make smoke` to confirm end-to-end rendering works.

---

## How to debug a Satori 500

1. Check the Satori sidecar terminal for stack traces — it logs to stdout.
2. Isolate the failing frame: `uv run nbn preview --scene <scene> --frame <n> --spec batches/smoke.yaml`.
3. Confirm fonts loaded at boot: `curl http://localhost:3001/health` should return `{"status":"ok"}`.
   If fonts are missing, place TTF files in `satori-service/fonts/` and restart the sidecar.
4. Narrow the props: add `console.log(props)` in the failing template, re-run preview.
5. Confirm the template name matches the dispatch map in `server.ts`.
6. If the issue is a JSX runtime error, run `cd satori-service && pnpm build` to see TypeScript errors.
7. If startup fails with `EADDRINUSE`, another process already owns the port.
   Reuse the existing sidecar if `curl http://localhost:3001/health` returns `status=ok`,
   otherwise stop the conflicting process or restart with `PORT=3002 make satori` and
   `SATORI_URL=http://localhost:3002`.

---

## How to bisect a golden-frame regression

1. Run `make smoke` — it will report the first divergent frame and scene name.
2. Use `git log --oneline` to identify the commit range when the regression appeared.
3. Run `git bisect start` with the known-good and known-bad commits.
4. At each bisect step, run `make smoke`; exit 0 means good, exit 1 means bad.
5. The bisect will identify the commit. Inspect the diff for template or motion changes.
6. Once reviewed, run `uv run nbn goldens update`. CI never creates missing goldens.

---

## How to rotate the D1 token

1. In the Cloudflare dashboard, create a new API token scoped to D1 read-only for the
   nobodynamed database.
2. Update `.env` (or your secrets manager) with the new `D1_TOKEN` value.
3. Run `make doctor` to confirm D1 reachability with the new token.
4. Revoke the old token in the Cloudflare dashboard.
5. If using CI, update the `D1_TOKEN` secret in the CI environment as well.
