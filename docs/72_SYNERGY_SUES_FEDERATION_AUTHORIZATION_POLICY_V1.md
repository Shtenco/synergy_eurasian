# SYNERGY SUES — Federation Authorization Policy V1

Status: executable deny-by-default research policy evaluator. It authenticates signed request/approval events through the V1 trusted identity registry, evaluates explicit policy rules, and returns a decision. It never executes the requested operation.

## Separation of concerns

Authentication answers which registered key signed an event. Authorization answers whether that authenticated identity may request a specific action against a specific resource under a tenant's policy. Neither operation proves the underlying economic claim or executes the operation.

The policy evaluator is not an accounting ledger, payment gateway, credit facility, token minter, custodian or ownership registry. A positive decision is an authorization input for a separately controlled executor, not a transaction itself.

## Signed request

The requester submits a signed event with event_type `AUTHORIZATION_REQUEST` and payload fields:
- `request_id`: unique request identity;
- `action`: exact operation name, e.g. `JOURNAL_POST`;
- `resource_type`: exact resource class, e.g. `LEDGER`;
- `resource_id`: exact target identifier.

The requester identity and tenant come from successful Ed25519 verification, never from self-asserted payload fields. Request time is the envelope's signed_at timestamp. A future-dated envelope is rejected by the identity layer.

## Explicit policy rules

`AuthorizationRule` is immutable and has a unique rule_id, tenant, effect (ALLOW or DENY), exact action, exact resource_type, optional exact resource_id, explicit requester identities, allowed approver identities, minimum distinct approvals and validity interval.

ALLOW rules require a non-empty subject allowlist. No wildcard action or resource matching is implemented. A null resource_id means the rule applies to any resource ID within the exact resource_type/action/tenant scope. DENY rules take precedence over all matching ALLOW rules. No matching ALLOW rule means denial. Duplicate rule IDs, duplicate subjects/approvers, invalid time windows and impossible approval thresholds are rejected.

When multiple ALLOW rules match, approvals are evaluated independently per rule and cannot be combined across policies. The narrowest resource scope wins, with rule ID as deterministic tie-break.

## Signed approvals and separation of duties

Each approval must be a signed `AUTHORIZATION_APPROVAL` event. The event payload binds the approval to request_id, action, resource_type, resource_id, requester_identity_id and decision (APPROVE or REJECT). The identity registry verifies the approver's signature and tenant.

An approval is counted only when its scope exactly matches the signed request, it is signed no earlier than the request, the signer is explicitly listed as an approver in a matching ALLOW rule, and the signer is not the requester. Each identity counts at most once. A REJECT from an authorized approver vetoes the request. An unrelated trusted identity cannot veto or approve.

## Decision semantics

- Explicit matching DENY rule → deny.
- No matching ALLOW rule → deny.
- Insufficient distinct signed approvals → deny.
- Authorized REJECT approval → deny.
- Otherwise → allow with selected rule ID and verified approver identities.

The engine returns an `AuthorizationDecision` with a machine-readable reason. It performs no external side effect and does not write a journal, send a payment, mint a token, transfer custody or alter ownership. V1 does not persist or consume request IDs. The eventual executor must atomically record and consume each request_id with its action to prevent duplicate execution/replay; a positive decision must never be treated as a reusable bearer token.

## V1 limitations

Rules currently live in process memory and must be provisioned by trusted application code. There is no persistent policy store, policy-signature approval workflow, policy version rollout, delegated authority graph, emergency override, revocation cache distribution, multi-region consensus or durable decision audit. These are required before production. The policy API accepts only already-signed request/approval envelopes and delegates identity/key revocation checks to the trusted registry.

## Files and verification

- Implementation: `src/synergy_sues/federation_authorization.py`
- Contracts: `interfaces/synergy_sues_authorization.schema.json`
- Tests: `tests/test_synergy_sues_federation_authorization.py`

Tests cover signed requester and approver flows, deny-by-default, quorum, self-approval rejection, authorized veto, unlisted-identity veto prevention, deny precedence, request/approval scope binding, timestamp ordering, tampering and rule validation.
