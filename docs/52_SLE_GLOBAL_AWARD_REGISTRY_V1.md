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

The registry maintains an append-only SHA-256 event chain for reservation and consumption transitions. `verify_event_chain()` checks sequence, previous hashes, event hashes and the head. `verify_projection_consistency()` replays registry events and compares every material projection field, including reservation and consumption timestamps, with the mutable award table. `verify_authorization_history()` re-verifies the original signed envelope at the reservation event timestamp (not merely at the signer's `issued_at`), so a key revoked after signing but before acceptance is rejected while a later revocation does not retroactively invalidate an accepted award.

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

Research/reference implementation under PR #17. Focused tests cover global source/award/result uniqueness across registry instances sharing one database, concurrent competing and identical reservations, concurrent idempotent consumption, signature verification, idempotent issuance and post-expiry replay, crash recovery after local issue, rejection of substituted recovery envelopes, stranded reservation safety, local term mismatch, timestamp/projection tampering and configured SQLite lock timeouts. This is not a production distributed consensus service.
