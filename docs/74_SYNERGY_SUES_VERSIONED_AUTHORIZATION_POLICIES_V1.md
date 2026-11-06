# SYNERGY SUES — Versioned Administrative Authorization Policies V1

Status: executable, signed, versioned policy store. This is a file-backed SQLite research reference, not a production distributed control plane.

## Administrative trust root

The store receives a per-tenant administrator allowlist through trusted application configuration. Incoming policy events cannot enroll identities or change this allowlist. The default quorum is **two distinct independent approvers in addition to the proposer** (three-person control). The proposer cannot approve their own change. Each tenant must have at least one proposer plus the configured number of independent approvers.

All signers are authenticated through the Ed25519 trusted-key registry. Approvers must belong to the same tenant, be in the out-of-band allowlist, sign no earlier than the proposal, and bind the exact proposal event ID and SHA-256 hash. Duplicate event IDs do not increase quorum. An authorized REJECT vetoes the change.

## Signed change events

The proposal event type is `AUTHORIZATION_POLICY_CHANGE`.

For `UPSERT_RULE`, the payload has exactly:
- `change_id`, `tenant_id`, `expected_version`, `operation`;
- `rule`: complete AuthorizationRule document, including explicit subjects, approvers, approval threshold, resource scope and validity interval.

For `REVOKE_RULE`, the payload has exactly the common fields plus `rule_id`, and no rule body.

Approval event type: `AUTHORIZATION_POLICY_APPROVAL`. Its exact payload fields are `change_id`, `tenant_id`, `expected_version`, `policy_change_event_id`, `policy_change_event_hash`, `decision`. Decisions are APPROVE or REJECT.

## Versioning and atomicity

Each tenant has one monotonically increasing policy version across all its rules. Every accepted mutation supplies `expected_version` equal to the current tenant version. The store takes SQLite `BEGIN IMMEDIATE`, reconstructs the current complete rule set, applies one upsert/revocation, computes a deterministic snapshot hash and appends the new immutable policy event in the same transaction. Two concurrent changes cannot both consume the same version. A stale change fails closed without a partial write.

An exact replay of an already-applied `change_id` and request hash returns `ALREADY_APPLIED`; reuse of that change ID with another signed request hash is rejected. A revoked rule is removed from the active snapshot while its prior signed history and snapshots remain in the append-only log.

## Snapshot and execution binding

`snapshot(tenant_id)` returns the tenant version, deterministic policy hash and active immutable rule tuple. `load_policy(tenant_id)` builds the evaluator from that snapshot. `authorize(...)` evaluates against the persisted policy and attaches `policy_version` and `policy_hash` to the AuthorizationDecision. The execution receipt serializes both fields, preserving the exact policy snapshot that authorized the action.

The policy hash commits to the tenant, version and complete sorted active rule set. The version is tenant-wide, so concurrent changes to different rule IDs still contend on one compare-and-swap sequence.

## Audit and limitations

The append-only history stores canonical signed proposal and approval envelopes, exact event IDs/hashes, complete resulting policy snapshot, previous hash and event hash. Startup verifies per-tenant sequence continuity, previous-hash continuity, snapshot reconstruction and policy hashes. SQLite triggers block ordinary application mutation. A privileged actor able to rewrite the database or drop triggers can still defeat local controls; externally anchor checkpoints and protect backups.

The store verifies incoming signatures and approval quorum at mutation time through the trusted registry. Local history verification checks canonical serialization, event/hash-chain continuity and deterministic policy reconstruction; it does not independently re-verify old signatures because the store does not own the registry or its historical key state. A production audit verifier must replay the retained envelopes against a durable trust/key-revocation history.

Not implemented: hardware-backed root governance, administrator allowlist rotation ceremony, PostgreSQL/distributed consensus, multi-region replication, mTLS, external WORM audit anchoring, emergency break-glass workflow, policy migration, or production key management. This layer does not grant journal, payment, credit, token, custody or ownership execution authority. SQLite remains single-host reference infrastructure.

## Files

- `src/synergy_sues/federation_policy_store.py`
- `tests/test_synergy_sues_federation_policy_store.py`
- `interfaces/synergy_sues_policy_change.schema.json`
