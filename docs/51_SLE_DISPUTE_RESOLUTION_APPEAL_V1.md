# SLE Dispute Resolution and Appeal V1

## Scope

This reference workflow adds a dispute state machine to the SLE service-credit ledger. It is not a court, legal arbitration service, monetary dispute rail or production identity system.

Implementation: `src/synergy_labor_disputes.py` (including bilateral remediation acknowledgement)
Decision schema: `interfaces/sle_dispute_decision.schema.json`
Ledger integration: `src/synergy_labor_credit_ledger.py`
Tests: `tests/test_synergy_labor_disputes.py`

## State machine

```text
OPEN -> DECIDED -> APPEALED -> DECIDED
```

- `OPEN`: a current issuer or holder records a reason code and non-empty evidence references.
- `DECIDED / CLAIM_UPHELD`: an independent resolver finds the claim valid; the dispute freeze is released.
- `DECIDED / DISPUTE_UPHELD`: the challenge is upheld; the claim remains frozen until both issuer and holder acknowledge a remediation reference.
- `APPEALED`: either credit party may appeal once with a reason and evidence references; the claim is frozen again.
- The appeal must be decided by a different resolver key/principal than the first decision.

A dispute is active and freezes the underlying credit while `OPEN` or `APPEALED`. The ledger rejects transfer, redemption and bilateral cancellation during those states. The SQLite dispute row, ledger event and credit mutation guard share the same transaction and database.

## Signed resolver decision

Decision signatures use Ed25519 over canonical JSON with domain separator `SYNERGY_SLE_DISPUTE_DECISION_V1\0`. Signed fields bind:
- case and credit IDs;
- resolver identity;
- outcome;
- SHA-256 digest of the rationale/evidence bundle;
- decision timestamp and expected case version;
- key ID.

The trusted key registry must authorize `DISPUTE_RESOLVER`, bind the principal to the key, and provide validity/revocation metadata. The registry itself is caller-supplied and not governed or authenticated by this module.

## Financial and obligation boundaries

- Opening a dispute does not erase or reduce the outstanding obligation.
- Resolver outcomes do not automatically cancel the claim, release capacity, write off a balance, transfer money or post Financial OS entries.
- `CLAIM_UPHELD` releases the dispute freeze. `DISPUTE_UPHELD` keeps it in place; `acknowledge_remediation()` requires distinct issuer and holder acknowledgement references before releasing the freeze.
- Bilateral remediation acknowledgement does not itself cancel, reduce or restructure the claim. Any cancellation still requires the existing bilateral cancellation command; restructuring remains a separate workflow.
- An appeal re-freezes transfer, redemption and cancellation until its final decision.
- Default is not automatically reversed by a dispute decision. A defaulted claim remains subject to the existing default restrictions.
- The workflow records party IDs and evidence references but does not authenticate the person submitting an open/appeal command. Production must add signed party authorization and identity proofing.
- Remediation acknowledgement references are caller-supplied metadata, not cryptographically verified issuer/holder approvals. The reference method demonstrates the state transition only; production must verify both parties' signatures/authority before allowing the freeze to be released.
- No appeal deadline or legal standard is inferred; the reference implementation permits one appeal per case.

## Audit and recovery

Every state transition is appended through the ledger's existing idempotent hash-chained event command. `verify_projection_consistency()` replays dispute-open, decision and appeal events and compares the reconstructed dispute projection with SQLite. Additive schema migration preserves existing databases by adding appeal metadata columns.

The hash chain is tamper-evident, not tamper-proof. External signed checkpoints, protected backups, independent key governance, multi-node consensus and disaster-recovery drills remain production prerequisites.

## Status

Research/reference implementation under PR #17. The dispute freeze is enforced inside the current SQLite credit ledger, not merely in a UI or sidecar registry. Focused adversarial tests are part of CI. This does not establish legal enforceability or production readiness.
