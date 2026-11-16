# SYNERGY Federation — End-to-End Execution Plan
**Revision:** 2026-11-16  
**Status:** Active implementation plan; not a production-readiness declaration.

## 1. Mission
Deliver a verifiable federation across:
- `synergistic_economics`: economic ontology, canonical economic entities, economic events and authoritative accounting contracts;
- `synergy_agentic_ai_economy`: autonomous agents, markets, learning and experimental economic simulation;
- `synergy_eurasian`: productive economy, regional/federated projects, physical flows and institutional rules;
- `synergy_metaverse`: canonical spatial entity registry, observations and business-twin bindings;
- `synergy_maps`: provenance-aware geospatial read model and map/3D presentation.

The repositories remain independently deployable bounded contexts. Integration is through versioned, authenticated, idempotent contracts—not shared mutable databases or copied authoritative balances.

## 2. Non-negotiable invariants
1. **One authority per fact.** Economic identity and legal/institutional status come from the economic authority. Financial balances and settlement facts come from the financial ledger/payment authority. Spatial identity and geometry provenance come from the spatial registry and its governed sources. Agent simulations never become authoritative financial records.
2. **No synthetic-to-real promotion.** Simulated bridge volume, fees, strategy fills, gas units, agent income, productive output or NAV must remain labelled simulated/modelled until independently evidenced by external records and reconciled.
3. **No double counting.** Internal mint/burn, internal transfers, CPMM fees, collateral recursion, external cash flows, protocol revenue and unrealized marks must be separately classified. Internal activity is not external wealth.
4. **Append-only evidence.** Events have stable IDs, canonical serialization, schema version, issuer, tenant, event time, recorded time, sequence/version, payload digest, signature and provenance. Corrections are compensating events, not silent rewrites.
5. **Idempotent consumers.** Re-delivery of an identical event has no additional effect; same event ID with different content is rejected. Consumers reject stale/out-of-order aggregate versions unless an explicit replay/recovery protocol applies.
6. **Fail closed.** Missing tenant identity, issuer trust, authorization, consent, signature, schema, key status or provenance blocks privileged reads/writes.
7. **Privacy and minimization.** No personal identifiers, raw RF/IQ payloads, subscriber IDs, private message contents or unnecessary OSM contributor metadata enter public spatial projections.
8. **Physical conservation.** Material, energy, inventory and money conservation are tested independently; unit conversions and rounding are explicit.
9. **Research is not production.** Passing tests or a deterministic backtest does not establish legal enforceability, real-world solvency, market liquidity, empirical calibration or production readiness.
10. **No direct writes to main during remediation.** Work proceeds on reviewed branches and pull requests; no forced ref updates, destructive migrations or secret/key operations.

## 3. Current verified baseline (2026-11-16)
### Repository permissions
The linked GitHub installation reports admin/push access to all five repositories. Default branch is `main` for each.

### Existing implementation candidates
- Eurasian PR #19, `fix/v66-reserve-recovery-ci`, head `700af96a935dd267b57408ad129e1e4ee65f44c0`, restores the V6.6 module chain and reserve recovery regression tests. Its PR description records exact-head CI success, 231 passed tests and a passing federation audit. It remains Draft and unmerged. Treat the claims as PR evidence; rerun against current GitHub Actions before merge.
- Economics PR #17 and #16 are near-duplicate Draft PRs for the Ed25519 canonical economic entity register, with the same five changed paths and the same base branch but different heads. Compare both diffs and histories; select one canonical candidate only after verifying unique changes and exact-head CI. Do not close either automatically.
- Economics PR #13 contains bank-deposit/credit constraints and is Draft. Preserve atomicity, cash/credit limits and double-entry invariants.
- Agentic AI PR #5 is an input-data PR, not evidence of a production agent economy. Keep historical data provenance and TRAIN/OOS separation.
- Metaverse PR #1 bootstraps spatial registry/contracts/observation security; PR #2 adds a read-only economic projection; PR #3 adds RF/GNSS and business-twin bindings. PR #2 currently reports non-mergeable; resolve its base/merge conflict before adding dependent changes.
- Maps PR #1 adds PostGIS/H3 ingestion, provenance and Cesium viewer. It remains Draft; its CI has reported failures. Retrieve current run logs and distinguish runner/infrastructure failure from code/test failure before changing implementation.

### Important correction to prior audit
The Eurasian V6.6 failure described in the earlier audit is no longer an unaddressed assumption: PR #19 explicitly restores the missing chain and reports a passing exact-head test run. The correct next action is to verify the current head and CI, review the diff, and only then propose readiness. Do not repeat stale failure claims as current facts.

## 4. Workstreams and acceptance gates

### WS0 — Evidence and repository baseline
- Record default branches, head SHAs, open PRs, dependency edges and latest CI per exact commit.
- For each failed workflow, capture run ID, job, failed step, log excerpt and classification: code / test / dependency / runner / permission / external service.
- Keep a dated audit ledger; every status has an evidence URL and commit SHA.
**Exit:** all five repositories have a reproducible baseline and every blocker has an owner, severity and evidence.

### WS1 — Canonical economic identity and event contract
- Select one canonical implementation from economics PR #16/#17 after a complete diff/history comparison.
- Define stable `economic_entity_id`, tenant scope, entity kind, institutional sector, lifecycle, external references and effective/recorded timestamps.
- Define canonical event envelope: `event_id`, `event_type`, `schema_id`, `schema_version`, `tenant_id`, `aggregate_id`, `aggregate_version`, `event_ordinal`, `effective_at`, `recorded_at`, `actor_id`, `authority_ref`, `payload`, `payload_digest`, `attestation`.
- Canonicalize JSON (RFC 8785/JCS where cross-language signing is required); use domain separation and Ed25519. Trust keys, revocation and tenant/issuer scopes must come from independently governed trust configuration; private keys stay in KMS/HSM.
- Distinguish local hash-chain tamper evidence from issuer authorization signatures.
**Exit:** schema compatibility tests, signature/tamper/revocation/tenant isolation/replay tests, durable restart tests and a documented key lifecycle.

### WS2 — Financial and accounting truth
- Identify the single authority for balances, liabilities, reserves, payments, fees and settlement. Do not let spatial or agentic projections own them.
- Verify double-entry, balanced journal, currency/scale, idempotency, atomic loan/deposit creation, reserve floors, overdraft/credit limits, and reversal semantics.
- Split NAV into independently reconciled components: external cash, verified external receivables, marked assets, liabilities, restricted funds, unrealized PnL, realized PnL, fees and gas.
- For HardNAV, keep modelled bridge volume/fees and modelled gas units explicitly outside realized externally evidenced NAV. The Agentic AI Economy main README currently labels V4 gross bridge flow 84,911.06 as `MODELED_V5_CALIBRATED_REFERENCE_UNCHANGED_FROM_V3` and explicitly says it is not earned SYNERGY commission. Verify the actual accounting code and report before changing it; do not treat the documented classification as a confirmed bug. Include only independently evidenced and reconciled cashflows.
- Add property-based tests for conservation, no double-entry drift, no duplicate posting and failure atomicity.
**Exit:** all financial events reconcile to journals; modelled and verified values cannot be silently combined.

### WS3 — Eurasian productive economy
- Verify PR #19 exact head, all CI jobs and the full suite; inspect reserve-floor/contributor edge cases and conservation proofs.
- Reconcile V6.6/V7/SUES branches and dependency graph. Do not merge research branches by version label alone.
- Restore mainline tests only through explicit source dependencies; keep `src` import path deterministic.
- Validate sector input-output balances, inventory/material/energy constraints, capex lifecycle, wages, receivables/payables, default/reserve mechanics and regional/federation flows.
- Keep empirical calibration and scenario simulation clearly separated.
**Exit:** clean full mainline CI, deterministic reproducibility and sector/material/money conservation tests.

### WS4 — Agentic AI economy
- Preserve train-only parameter selection and frozen weights during OOS. Prevent data leakage and future-candle use.
- Classify each market leg and cost input by provenance, timestamp, staleness and exact/modelled status.
- Keep external capital flow, bridge volume, internal mint/burn, internal transaction volume, fee revenue, hedge PnL, funding, execution and gas as separate ledgers.
- Add strict accounting invariants and a test that modelled bridge/fees cannot affect verified HardNAV.
- Report multiple seeds, confidence intervals, baselines, ablations, drawdowns, concentration, defaults, liquidity and transaction costs. Do not select on OOS.
**Exit:** reproducible benchmark with no leakage, complete cost classification and separately reported simulated versus evidenced results.

### WS5 — Metaverse authority and privacy
- Resolve PR #2 merge conflict and establish dependency order PR #1 → PR #2 → PR #3.
- Keep economic bindings read-only and reject ownership/title/price/balance/credit/payment/settlement claims in spatial payloads.
- Wire a production canonical economic resolver only after its trusted issuer, tenant auth, audience, expiry, revocation and replay controls are available.
- Use KMS/HSM-backed envelope encryption; define key rotation, revocation, backup/restore and cryptographic erasure operations.
- Require authoritative consent/capture authorization and verify it at the correct transaction boundary.
- Keep RF/GNSS metadata minimal; no raw IQ or personal identifiers.
- Add external Ed25519/WORM anchoring for audit evidence where privileged database rewrite is in scope.
**Exit:** tenant isolation, signature verification, consent/erasure, crash recovery, KMS integration and business-twin authority tests pass.

### WS6 — Maps
- Resolve CI failures from logs before changing code. If logs are unavailable, rerun and classify runner allocation separately.
- Run PostGIS integration tests against an ephemeral service in CI; verify migration, spatial validity, geometry versioning and tenant filtering.
- Verify GeoJSON coordinates, CRS, antimeridian/polygon edge cases, H3 indexing and PostGIS exact geometry authority.
- Enforce source record/version idempotency, license and attribution, immutable manifests and source provenance.
- Verify tenant resolver cannot be spoofed by request headers.
- Build Cesium client in CI; restrict 3D Tiles URLs to verified publishers/manifests and protect against SSRF/open redirects.
**Exit:** green API/DB/browser CI, provenance-complete ingestion and verified tenant-scoped rendering.

### WS7 — Federation integration
- Publish versioned contracts and compatibility matrix.
- Use transactional outbox in each producer and durable inbox in each consumer; define retry, dead-letter, replay and schema evolution.
- Provide contract tests for: economic entity → business twin → map projection; economic event → agent simulation projection; Eurasian project/output → verified economic event → financial journal/payment settlement.
- Enforce per-event issuer, tenant, audience, expiry, sequence and idempotency.
- Provide trace/correlation IDs and evidence links across the chain.
**Exit:** end-to-end tests prove identity, authority, conservation and replay safety across all five repos.

### WS8 — Release and operations
- Document deployment topology, secrets/KMS, IAM, backups, disaster recovery, monitoring, incident response and data retention.
- Produce SBOM/dependency and vulnerability scans, reproducible builds, pinned CI actions and migration rollback plans.
- Define SLOs and operational runbooks.
- Keep all PRs Draft until acceptance gates pass; merge only after review and exact-head CI.
**Exit:** signed release checklist and explicit statement of what is research, staging and production.

## 5. Immediate execution sequence
1. Refresh PR metadata and exact-head CI for all open candidate PRs.
2. Compare economics PR #16 and #17 and choose a canonical branch without losing unique commits.
3. Verify Eurasian PR #19 exact-head CI and inspect the full diff.
4. Fix Agentic V4 accounting classification and add regression tests on a dedicated branch.
5. Diagnose Maps and Metaverse CI from fresh logs.
6. Resolve Metaverse PR #2 merge conflict and establish PR dependency order.
7. Publish shared event envelope/schema and cross-repository compatibility tests.
8. Implement end-to-end test harness and evidence report.

## 6. Change management
- One logical change per commit/PR.
- No destructive rewrite, force push, secret/key generation, production deployment or main-branch merge without a separate explicit approval.
- No test weakening, skipped failing tests or fabricated CI success.
- Each PR must state: motivation, exact scope, invariants, migration/backward compatibility, tests run, exact commit SHA, known limitations and rollback.
- If a failure is due to GitHub runner infrastructure, record it as infrastructure—not as code success.
- If code cannot be safely changed without missing external services or credentials, implement an interface/contract and mark production wiring blocked.

## 7. Completion definition
The plan is complete only when every workstream has:
- merged or explicitly accepted reviewed PRs;
- exact-head passing CI;
- contract and regression tests;
- evidence-backed documentation;
- no unresolved P0/P1 blockers;
- a clear research/staging/production classification.

**Current status:** planning baseline documented; implementation gates remain open. This file itself does not claim any system is production-ready.


## 8. Implementation log — 2026-11-16
### Completed repository actions
- Created this plan as Draft PR #20 in `synergy_eurasian`; branch `integration/federation-execution-plan-2026-11-16`. Main remains unchanged.
- Compared Economics PR #16 and #17: all five changed-file patches are byte-for-byte identical. Closed #16 as superseded; its branch remains intact. PR #17 is the canonical candidate, with successful prototype and schema validation runs on head `a4bc7a3e21d8bdee7cf35653b58c6f05ec637f1e`.
- Eurasian PR #19 remains Draft/unmerged; exact head `700af96a935dd267b57408ad129e1e4ee65f44c0` has a recorded successful EIIOM CI run `43685160237`. Revalidation/review still required before merge.
- Metaverse PR #2 was superseded by rebased PR #5; PR #2 closed, branch retained. PR #5 now contains the latest economic projection, tests and integration documentation.
- Hardened the Metaverse economic projection: event ingestion now requires an injected trusted producer verifier and non-empty attestation, binds verification to audience `synergy.metaverse.economic-projection.v1` and the independently supplied expected tenant, and fails closed on absent verifier, verifier error or rejection. Added negative regression tests and documented that the test stub is not a production verifier. This closes the unsafe default-acceptance gap at the consumer boundary, but a production Ed25519 verifier/key-registry adapter and producer-side signing remain open.
- Rebased the RF/GNSS/business-twin implementation onto the updated economic projection base in PR #6. The new branch preserves the RF/GNSS files and tests, reconciles CI branch filters and avoids cancelling runs while validation is pending. Closed old PR #3 as superseded; its branch remains intact. PR #6 is mergeable and remains Draft.
- Maps PR #1 and Metaverse PR #5/#6 CI jobs were retried where GitHub allowed. The latest job records show failures with zero reported steps; log downloads return BlobNotFound. Treat these as unresolved Actions/runner or log-retention failures, not as successful code validation. The old Agentic AI runs are outside GitHub's 30-day rerun window and the API rejected retries.

### Agentic AI accounting correction — confirmed and patched
Source-level review confirmed a real V4 HardNAV leakage:
- `closed_multimarket_hardnav_v4.py` divided the modeled V3 bridge volume (84,911.06) across 13,000 blocks and called `record_external_bridge_flow()`, which booked the configured bridge/swap fee as external protocol revenue.
- The pre-correction report included 339.64424 bridge/swap fees and 7.808553 external AMM fee estimates in HardNAV, while the bridge volume was explicitly marked modeled and there were no transaction-level fee receipts.
- The AMM fee was inferred from price-ratio arbitrage notional, not observed swap transactions.

PR #10 in `synergy_agentic_ai_economy` implements separate modeled bridge and AMM fee counters, defaults AMM fee recognition to false, excludes modeled fee estimates from V4 HardNAV, adds regression tests, marks the previous report superseded and documents the audit. No replacement return/drawdown values are published until the corrected 13,000-block replay is rerun and exact-head tests pass. PR #10 remains Draft.

### Current open integration blockers
1. Production Ed25519 producer verifier and independently governed key registry; producer-side marketplace event signing.
2. Authenticated remote resolver and tenant IAM between Economics and Metaverse.
3. Maps and Metaverse CI evidence unavailable despite retries; need a fresh run with retrievable logs.
4. Metaverse PR #6 exact-head CI and mergeability review.
5. Agentic AI historical real-block workflow failure requires a new PR synchronization event or new workflow run; old run IDs cannot be retried after 30 days.
6. No production PostGIS, KMS/HSM, RF/GNSS hardware adapters, backup/restore, WORM anchoring or deployment evidence yet.

**Status after this log:** planning and several branch-level changes are committed. No PR has been merged and no production deployment has been performed.


### Additional implementation log — 2026-11-16 04:14 UTC
- Agentic AI PR #10 created: [Exclude modeled bridge and AMM fee estimates from HardNAV V4](https://github.com/Shtenco/synergy_agentic_ai_economy/pull/10). Branch `fix/v4-exclude-modeled-fees-from-hardnav-20261116`.
- The V4 historical report is preserved for traceability but now marked superseded. The README explicitly warns that the prior V4 HardNAV values included modeled fee estimates and must not be used as verified realized wealth.
- Added `docs/HARDNAV_V4_ACCOUNTING_AUDIT_2026-11-16.md` documenting the source-level evidence and correction.
- Added tests for modeled bridge fee exclusion and modeled AMM fee exclusion; existing tests retain the explicit observed-fee path.
- PR #10 CI runs `43802719900` and `43802719919` both failed with zero reported steps and unavailable log blobs, including after retry. The exact-head code is therefore not yet test-validated. The full historical replay has not been regenerated.
- Metaverse PR #5 and PR #6 remain mergeable Drafts, but their latest CI attempts also failed before reporting any steps; log blobs are unavailable. Maps PR #1 has the same unresolved state.
- Eurasian PR #20's retry `43802554827` is currently executing; checkout and Python setup completed and dependency installation is in progress at the time of this update. Its final result must be checked before relying on it.
