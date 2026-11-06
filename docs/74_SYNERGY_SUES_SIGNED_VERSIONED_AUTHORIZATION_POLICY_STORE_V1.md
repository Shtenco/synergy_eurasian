# SYNERGY SUES — Signed Versioned Federation Authorization Policy Store V1

Status: executable single-host reference implementation. Policy creation, replacement and revocation are represented by signed events, require out-of-band administrator trust plus two independent approvals, and are committed with compare-and-swap version control and a per-tenant hash-chained history.

## Why this layer exists

The V1 authorization evaluator previously accepted rules provisioned in process memory. That was useful for testing decisions, but insufficient for a federation: policy could disappear on restart, change without an auditable event, or be evaluated against an unpinned version.

This module adds a durable policy lifecycle. It does not make the policy store a governance authority for the whole SYNERGY ecosystem; it is a research reference for controlled policy mutation.

## Administrative trust model

The administrator allowlist is passed to `SQLiteAuthorizationPolicyStore` by trusted deployment configuration. An incoming signed event cannot add itself, nominate its own signer as administrator, or change the allowlist.

For each tenant:
- The proposer must be in the configured administrator allowlist.
- At least two distinct, allowlisted administrators must approve.
- The proposer cannot approve their own change.
- Each approver signs a separate `AUTHORIZATION_POLICY_APPROVAL` event.
- A valid `REJECT` from an allowlisted independent administrator vetoes the change.
- All signatures are checked through the existing trusted-key registry; tenant identity comes from the verified signer, not from an untrusted claim.

The default quorum is two independent approvers, so the allowlist must contain at least three administrators: one proposer and two approvers. The quorum can be raised, never lowered below two, at construction time.

## Signed change contract

The proposer signs an `AUTHORIZATION_POLICY_CHANGE` event. It contains:
- `change_id`: unique idempotency key within the tenant;
- `tenant_id`: target tenant;
- `expected_version`: the exact current policy version the proposer reviewed;
- `operation`: `UPSERT_RULE` or `REVOKE_RULE`;
- `rule`: complete rule document for UPSERT, or `rule_id` for REVOKE.

Each approval binds to the exact `change_id`, tenant, expected version, change event ID and change event SHA-256 hash. It also carries `APPROVE` or `REJECT`. A valid approval cannot be replayed for another signed change event, even if the new event reuses the same change ID and intended rule.

A rule is validated by the existing `FederationAuthorizationPolicy.register_rule` contract before it can enter the durable snapshot. Rule replacement is an explicit `UPSERT_RULE` operation. Revocation is a separate signed `REVOKE_RULE` operation; unknown rule IDs cannot be revoked.

## Versioning, concurrency and idempotency

Policy versions begin at zero (empty policy) and increase by exactly one for every accepted mutation. A mutation must provide the exact `expected_version`. The store obtains a SQLite `BEGIN IMMEDIATE` write lock, checks the current version, applies the mutation and appends its signed evidence and new snapshot in one transaction.

This is compare-and-swap semantics:
- If two administrators prepare changes against version 4, only the first committed change can create version 5.
- The second change fails as stale; it must be reviewed and re-signed against version 5.
- Replaying the same `change_id` and same signed request hash returns `ALREADY_APPLIED` without a second version.
- Reusing a `change_id` with a different signed request event is rejected.

The policy hash commits to tenant ID, version and the complete canonically ordered rule set. Each change-history hash commits to the signed request envelope, the selected signed approval envelopes, resulting policy snapshot, policy hash and previous tenant-history hash.

## Authorization and execution evidence

`store.authorize(...)` loads the current tenant snapshot, evaluates it using the existing deny-by-default evaluator and attaches `policy_version` and `policy_hash` to the resulting `AuthorizationDecision`. The authorized executor now includes these two fields in its immutable execution receipt decision record.

This is an evidence pin, and the local reference now adds a final same-database guard: when the executor receives a decision with `policy_version` and `policy_hash`, it requires the policy store table in the same SQLite database, acquires `BEGIN IMMEDIATE`, and compares the current tenant version/hash before calling the handler. A missing policy table or stale snapshot fails closed. Sharing one SQLite database lets the write lock prevent a policy mutation between this check and the execution receipt commit.

This is a single-host check-to-commit guarantee only. Separate databases, hosts or regions are not atomic; production requires a managed shared transactional authority or a separately designed consensus/fencing protocol.

## Persistence and integrity

The implementation uses a file-backed SQLite database, append-only policy change rows, unique tenant/version and tenant/change IDs, and per-tenant SHA-256 history chains. Startup verifies canonical JSON, version continuity, previous-hash continuity, reconstructed rule snapshots, policy hashes and event hashes.

SQLite is a single-host reference. WAL is not a distributed database or consensus protocol. Triggers and hash chains are tamper-evident against ordinary application-level mutation, not against an attacker who can rewrite the database file, drop triggers and recompute hashes. Production requires managed database permissions, external audit anchoring, backup/restore drills, key management, authenticated admin interfaces and independent governance.

The store structurally verifies persisted history at startup. Before accepting a new mutation or authorizing an action, it can also revalidate every stored request and approval signature through the trusted-key registry at each envelope's original signing time. This means a key revoked after a valid historical signature does not retroactively invalidate that signature, while a signature created after revocation or a subsequently altered signature fails verification. This requires the historical public keys and identities to remain resolvable in the trust registry; key destruction/retention policy and externally anchored trust checkpoints remain operational requirements. Snapshot reads also re-verify the complete per-tenant history before returning a policy, so this reference has O(history length) read cost. Signature revalidation is performed on the mutation and authorization paths when a registry is supplied; the public structural `verify()` call without a registry does not independently prove Ed25519 signatures. Rejected administrative attempts are also recorded in a separate append-only, per-tenant hash chain with the claimed signer, change/event references, timestamp and bounded rejection reason. Claimed identity is explicitly untrusted until signature verification succeeds. Audit-write failure does not replace the original authorization error, so deployments must monitor audit I/O failures. This is not a tamper-proof external log: a privileged attacker able to rewrite the SQLite file and recompute the chain can still alter it.

## Explicit non-goals

This layer does not:
- authorize itself to modify the out-of-band administrator allowlist;
- implement admin enrollment, key issuance, emergency override or recovery;
- provide multi-region consensus, PostgreSQL, HSM/KMS or mTLS;
- transfer payment, credit, custody, token-mint/burn, journal-posting or ownership authority;
- provide a cross-host or cross-database policy-version fence;
- turn an authorization decision into an economic fact or settlement receipt.

## Files

- Implementation: `src/synergy_sues/federation_policy_store.py`
- Rejected administrative-attempt audit: `authorization_policy_admin_attempts` table, append-only and hash-chained per tenant
- Tests: `tests/test_synergy_sues_federation_policy_store.py`
- Contract: `interfaces/synergy_sues_authorization_policy_store.schema.json`
- Existing evaluator: `src/synergy_sues/federation_authorization.py`
- Execution receipts: `src/synergy_sues/federation_execution.py`

