# Data verification

Cloudflare D1 is the standing operational verification source for new NobodyNamed story snapshots.

- Generate and verify new story snapshots through `scripts/snapshot_from_d1.py` using `D1_URL` and `D1_TOKEN`.
- GitHub Actions must not contact SSA endpoints directly for routine snapshot verification or extraction.
- The official SSA `names.zip` URL and the reviewed archive SHA256 remain the upstream provenance identity for a release; they are not the runtime verification endpoint.
- D1 is fail-closed: before it may emit snapshots for a reviewed release, it must reproduce checked-in archive-derived anchor observations, including annual counts, suppressed years and ranks.
- Any anchor mismatch blocks snapshot generation.
- When a new annual SSA release arrives, review and import that release into D1 through the controlled ingestion process, pin the reviewed archive SHA256, refresh the archive-derived anchors as needed, and only then resume D1 snapshot generation.

This policy preserves the official SSA dataset as the upstream authority while making D1 the reliable operational source used by the repository and CI.
