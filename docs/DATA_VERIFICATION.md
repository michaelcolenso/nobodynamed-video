# Data verification

Cloudflare D1 is the standing operational verification source for new NobodyNamed story snapshots.

- Generate and verify new story snapshots through `scripts/snapshot_from_d1.py` using `D1_URL` and `D1_TOKEN`.
- GitHub Actions must not contact SSA endpoints directly for routine snapshot verification or extraction.
- The official SSA `names.zip` URL and the reviewed archive SHA256 remain the upstream provenance identity for a release; they are not the runtime verification endpoint.
- D1 is fail-closed: before it may emit snapshots for a reviewed release, it must reproduce checked-in archive-derived anchor observations, including annual counts, suppressed years and ranks.
- Any anchor mismatch blocks snapshot generation.
- When a new annual SSA release arrives, review and import that release into D1 through the controlled ingestion process, pin the reviewed archive SHA256, refresh the archive-derived anchors as needed, and only then resume D1 snapshot generation.

This policy preserves the official SSA dataset as the upstream authority while making D1 the reliable operational source used by the repository and CI.

## Connector replay: the fallback provenance

A workstation without `D1_URL` and `D1_TOKEN` cannot run the verified path above. For
that case `scripts/snapshot_from_d1.py --from-connector` replays captured nobodynamed
connector responses into snapshots. The connector serves annual counts but no national
rank, so this path:

- cannot run the rank-level anchor check, and therefore
- must not claim the SSA archive identity.

Snapshots it writes declare `source_dataset: nobodynamed-d1:name-vitals` instead of
`source_url` + `archive_sha256`, and the `Snapshot` model rejects any attempt to carry
both. Counts are gated exactly as they are for an archive snapshot: every `count_claims`
entry in a story is still checked against the pinned snapshot bytes.

Rank is the only field that differs. It reaches `VideoContext` but never reaches rendered
copy for an approved story, whose headline, subhead, narrative and support text all come
from the StorySpec. Do not build published copy on `current_rank`, `rank_at_peak`,
`last_top_1000_year`, `last_top_10_year` or `top10_years` from a connector snapshot.

Before a release, regenerate through the credentialed path and re-pin:

```sh
uv run python scripts/snapshot_from_d1.py \
  --year 2025 --anchor-dir data/ssa-2025 --out data/nobodynamed-2025 \
  --names Taylor:F Wednesday:F Chad:M Shirley:F Maverick:M \
          Khaleesi:F Luna:F Britney:F Wendy:F Adolph:M \
  --repin-stories stories/viral-2025
```

Re-pinning changes each story's `data_sha256`, which invalidates its approval digest by
design. The gate fails closed until a reviewer approves the re-pinned content.
