# Repository audit — 2026-09-05

## Executive assessment

The pipeline has unusually strong foundations for a media system: render decisions are
deterministic, domain models constrain editorial inputs, visual regressions have golden
hashes, encoded files receive post-render QC, and the Python code is held to strict mypy.
The main risk discovered in this audit was not presentation but **data fidelity at the
backend boundary**. Sparse SSA rows were passed through as sparse chart points. Because
SSA suppresses small counts, a missing year means “reported as zero,” not “draw a straight
line between the surrounding observations.” That distinction can materially change the
story shown to viewers.

This audit therefore prioritized correctness and release-gate symmetry over adding new
visual effects. The resulting changes normalize both data backends through one invariant,
harden remote response handling, correct missing-name rank behavior, and make pull-request
CI test the Node renderer rather than only the Python half of the application.

## Scope and method

The review covered:

- package boundaries and domain models under `src/nobodynamed_video/`;
- SQLite and Cloudflare D1 query semantics;
- frame planning, motion programs, Satori transport, composition, and encoded-output QC;
- Python and Node dependency/build configuration;
- GitHub Actions release gates and ignored generated/secret state;
- the full Python lint, formatting, strict-type, and test suites;
- the Satori service unit tests and TypeScript build.

The audit deliberately did not regenerate visual goldens: data normalization changes the
input only for genuinely sparse records. The unit-level render suite continues to pass; a
cold frame smoke was also attempted, but this constrained environment's sidecar disconnected
while CPU-bound and is recorded as an environmental warning rather than used to rewrite a
baseline. A credentialed D1/Workers AI render remains an operational release check.

## Findings addressed

### 1. Critical — sparse SSA observations could imply invented births

Both sources only filled years after the final database row. They did not fill years before
the first observation or gaps between observations. The renderer could consequently draw a
continuous nonzero interpolation across suppressed years. A shared normalizer now emits
exactly one point for every year from 1880 through the reference year and validates negative,
duplicate, and out-of-range rows.

### 2. High — local and production source behavior had drifted

Cloudflare lookups were case-insensitive, while SQLite lookups were case-sensitive. A CLI
request for `ada` could work in production but fail against the development fixture. SQLite
name operations now consistently use case-insensitive matching, and record construction is
shared rather than duplicated.

### 3. High — an absent name/year could be reported as rank 1

The rank query used an aggregate over a comparison to a missing scalar subquery. SQL then
counted zero competitors and returned `1`, despite the target having no row in that year.
Both backends now explicitly test target-row existence and return the established `9999`
sentinel when SSA has no rankable observation.

### 4. High — malformed D1 responses escaped as incidental exceptions

An HTML gateway response, empty `result` array, or non-object row could previously raise a
JSON/index/type error far from the data-source abstraction. D1 responses now validate each
envelope level and consistently raise `DataSourceError` with an actionable boundary message.

### 5. High — pull requests did not validate the renderer sidecar

The deployment job built the sidecar only after changes reached `main`; the pull-request
check job linted, typed, and tested only Python. CI now installs locked Node dependencies and
runs both sidecar tests and `tsc` during review.

### 6. Low — uv configuration emitted a known deprecation warning

Development dependencies now use the standardized `dependency-groups.dev` table. This keeps
the lock unchanged while removing noise that could hide meaningful setup warnings.

## Residual risk and recommended roadmap

### Near term

1. **Add a credentialed, scheduled canary.** Render exactly one approved story against D1 and
   Workers AI nightly, retain its manifest, and alert on source, narration, or golden failure.
   Pull-request CI should remain credential-free for untrusted forks.
2. **Make D1 transport reusable.** `D1Source` creates an HTTP client per query. Give it an async
   lifecycle (or inject a shared client) before scaling batch concurrency; include bounded
   retries only for idempotent transient failures and respect `Retry-After`.
3. **Validate semantic model invariants.** Add `NameRecord` validators for sorted/unique annual
   points and consistency among peak/current summary fields. Source normalization guarantees
   this today, but tests and future importers can instantiate models directly.
4. **Version the manifest schema.** Add a schema version and input provenance (data backend,
   reference year, source-query timestamp, normalized-series digest) so historical renders can
   be reproduced and migrated safely.

### Medium term

1. **Introduce observability budgets.** Emit structured timings and error codes for D1, Satori,
   narration, alignment, frame rendering, and ffmpeg. Track p50/p95 plus cache hit rate per run.
2. **Add property-based tests at the data/motion seam.** Generate sparse valid series and assert
   contiguous normalization, finite motion scalars, bounded frame indices, deterministic output,
   and no single-frame velocity discontinuity.
3. **Separate pure planning from effects.** Produce a serializable render plan before HTTP or
   filesystem work. This enables resumable jobs, distributed workers, dry-run cost estimates,
   and exact plan diffs in review.
4. **Harden dependency maintenance.** Add scheduled Dependabot/Renovate updates and OSV audits,
   with explicit exceptions for visually sensitive Satori/resvg upgrades that require golden
   regeneration.

### Longer-term opportunities

- Build an editorial experiment ledger joining hook/program variants, manifest hashes, and
  retention outcomes, then choose variants with a deterministic exploration/exploitation policy.
- Store content-addressed frame bundles and narration artifacts outside the release checkout;
  make manifests the durable provenance record and garbage-collect unreferenced artifacts.
- Add perceptual visual comparison in addition to exact PNG hashes, allowing reviewers to see
  localized diffs while retaining exact hashes as the final deterministic gate.

## Quality posture after this audit

The architecture remains intentionally conservative where correctness matters: SQL stays
parameterized, secrets and generated state remain ignored, the renderer remains deterministic,
and no visual baseline was silently rewritten. The most important new guarantee is simple and
testable: **every backend now describes the same contiguous SSA timeline, and absence can no
longer masquerade as popularity.**
