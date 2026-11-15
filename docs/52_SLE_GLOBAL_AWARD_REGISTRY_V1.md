# SLE Global Award Registry V1

## Purpose and uniqueness scope

`src/synergy_labor_award_registry.py` implements a shared coordination registry for one-time labor awards. It adds a uniqueness authority above the issuer-local uniqueness constraints in `LaborCreditLedger`.

The registry enforces, in its own SQLite database:
- one reservation per `source_contribution_id` across all producers that use the same registry database;
- one reservation per `result_digest`, preventing the same exact result artifact from being relabelled with a new contribution ID;
- one reservation per `award_id`;
- one use of a signed authorization digest;
- at most one local credit issuance event consumed by a reservation.

This is only global within the shared registry database. Two disconnected registry databases do not coordinate and cannot claim cross-system uniqueness. All participating SLE, Financial OS adapters and reward engines must use the same authoritative registry endpoint/database or a future consensus-backed equivalent.

## Protocol

`issue_authorized_credit()` implements a safety-first two-phase flow:

1. Verify the complete Ed25519 award authorization, signer role, key validity/revocation and expiry.
2. Atomically reserve `source_contribution_id` and `award_id` in the shared registry under `BEGIN IMMEDIATE`.
3. Issue the local service credit through the existing ledger, retaining Financial OS as the only accounting/payment authority.
4. Verify the local ledger event hash chain and replayed projections.
5. Match the exact `CREDIT_ISSUED` event and its issuer, beneficiary, contribution, award ID, result digest, service, unit, capacity and quantity against the reservation.
6. Atomically transition the registry record from `RESERVED` to `CONSUMED` and append a registry event referencing the local event ID and hash.

The local ledger and shared registry are separate SQLite databases; this is not a distributed atomic transaction. The reservation is committed first, so a crash cannot open a duplicate-award window. If local issuance succeeds but the process crashes before registry consumption, a retry with the same credit and idempotency identifiers reconciles the existing `CREDIT_ISSUED` event. It does not issue a second credit. A retry after the registry is already `CONSUMED` is also idempotent after authorization expiry: the caller must supply the byte-for-byte canonical original envelope, and the registry re-verifies its historical signature against the supplied trust registry before confirming the existing local issuance. A substituted envelope for the same award ID is rejected.

## Reservation lifecycle and failure policy

- `RESERVED` locks the source contribution and award ID.
- `CONSUMED` records the matching local credit and event proof.
- Reservations never auto-expire and are never silently released.
- If issuance fails before a local credit exists, retry the same signed authorization while it remains valid. The reservation stays locked.
- If issuance succeeded but registry consumption did not, retry/reconcile using the same local credit ID and idempotency key.
- There is intentionally no public abort/release operation in this reference version. A safe release requires an independently governed proof that no local or downstream award was issued; adding a caller-controlled release would reopen replay attacks.

This deliberately favors duplicate prevention over liveness. Operational deployments need an authenticated reconciliation queue and separately governed exception process for stranded reservations.

## Audit

The registry maintains an append-only SHA-256 event chain for reservation and consumption transitions. `verify_event_chain()` checks sequence, previous hashes, event hashes and the head. Public chain, projection and authorization-history audits execute inside a consistent SQLite read transaction, so a concurrent commit cannot make one audit compare rows from different snapshots. `verify_projection_consistency()` replays registry events and compares every material projection field, including reservation and consumption timestamps, with the mutable award table. `verify_authorization_history()` re-verifies the original signed envelope at the reservation event timestamp (not merely at the signer's `issued_at`), so a key revoked after signing but before acceptance is rejected while a later revocation does not retroactively invalidate an accepted award.

Consumption also verifies the local ledger's event chain and `verify_projection_consistency()` before accepting a local issuance reference. Registry and local event hashes are linked in the `AWARD_CONSUMED` record.

The event chain is tamper-evident, not tamper-proof. External checkpoints, backups, access controls and registry key governance remain production requirements.

## Authority boundaries

- LABOR SCORE remains a non-monetary metric.
- A reservation is not a credit, money, accounting entry or payment.
- The local service-credit ledger still enforces issuer capacity and outstanding limits.
- Financial OS remains the sole authority for monetary recognition, accounting and payment.
- The registry does not independently prove that the underlying labor result is truthful; it relies on the signed award authorization and its configured trusted key registry.
- The registry does not coordinate with disconnected copies of itself or provide multi-region consensus.

## Status

Research/reference implementation under PR #17. Focused tests cover global source/award/result uniqueness across registry instances sharing one database, concurrent competing and identical reservations, concurrent identical end-to-end issuance, competing end-to-end attempts for the same contribution, concurrent idempotent consumption, lock-contention fail-closed behavior, concurrent audit snapshot isolation, separate-process uniqueness, hard process termination after reservation (verifying the stranded reservation remains locked after authorization expiry) and after local issuance (WAL database reopen and idempotent reconciliation), signature verification, idempotent issuance and post-expiry replay, crash recovery after local issue, rejection of substituted recovery envelopes, stranded reservation safety, local term mismatch, timestamp/projection tampering and configured SQLite lock timeouts including rejection of unrepresentably large values. This is not a production distributed consensus service.


## SQLite concurrency and backup/restore contract

The lock acquisition order for the cross-database consumption path is **registry lock / registry write transaction, then local ledger lock**. Ledger commands and ledger audit methods acquire only the ledger lock and must never call back into the registry while holding it. Registry methods must not invoke a ledger operation while already holding a ledger lock. This one-way order prevents an application-level registry↔ledger lock cycle; SQLite's own busy timeout remains a separate cross-process contention control. If a future adapter needs the reverse dependency, it must redesign the protocol rather than acquire locks in the opposite order.

Both file-backed databases use WAL journaling and synchronous=FULL. Operational backups must use SQLite's online backup API (or a documented quiesce/checkpoint procedure); copying only the main .sqlite file while WAL is active can omit committed pages. Restore validation must reopen the database and run event-chain and projection audits before accepting writes. The regression suite now creates online backups of both databases, restores them independently, validates both audit histories and performs a post-restore idempotent retry after authorization expiry. This validates SQLite backup/restore behavior for the tested committed state; it does not provide a cross-database atomic snapshot or a disaster-recovery guarantee for arbitrary storage failures.


## Externally signed registry checkpoints

`src/synergy_labor_checkpoints.py` adds Ed25519 checkpoints over the audited registry event head. A checkpoint binds the stable operator-supplied `registry_id`, event sequence and hash, UTC creation time, checkpoint signer key ID, and digest of the previous checkpoint. The strict wire shape is `interfaces/sle_registry_checkpoint.schema.json`. Verification checks the signer role (`REGISTRY_CHECKPOINTER`), key validity interval and revocation time at checkpoint creation, Ed25519 signature, monotonic sequence, checkpoint-to-checkpoint digest continuity, and the event hash at every anchored sequence in the current registry.

The anchor store is an injected `CheckpointAnchorStore` contract. The included `InMemoryCheckpointAnchorStore` is test-only and is **not** durable or independent. A production adapter must persist anchors in a separately administered failure and privilege domain (for example, an independently controlled append-only object store or signing/transparency service), enforce append-only monotonic writes, authenticate readers/writers, and retain recovery copies. Storing the anchor beside the registry under the same administrator does not solve full-history rewrite risk.

A valid audit detects a rewritten history at or before the latest anchor and detects a registry rollback behind an anchor. It cannot detect deletion or rewriting of events created after the most recent checkpoint; checkpoint cadence therefore defines the maximum unanchored exposure window. It also cannot prove that the original business events were truthful. Key custody, independent anchor availability, retention, monitoring, and recovery drills remain deployment responsibilities. This feature is a signed anchoring protocol and test adapter, not a distributed consensus service or production external-storage integration.

Regression tests cover multi-checkpoint continuity, duplicate/stale checkpoint rejection, a privileged full-chain rewrite that still passes the local chain and projection audits, rollback behind the anchor, signature tampering, and schema validation.
