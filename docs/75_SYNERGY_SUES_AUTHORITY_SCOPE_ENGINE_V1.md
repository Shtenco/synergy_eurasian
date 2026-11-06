# SYNERGY SUES — Authority Scope Engine V1

Status: executable research evaluator; not yet wired into the authorized executor or a transactional ledger reservation.

## Purpose

Authorization answers whether an identity may request an action. Authority scope answers how far that authority extends economically. A valid signature, a matching ALLOW rule and a valid approval quorum must never imply unlimited economic authority.

## V1 contract

A scope is explicit and tenant-bound. It pins action and resource type; requester subject allowlist; allowed currency codes; maximum amount per transaction; maximum aggregate amount per configured period window; organization, account and counterparty allowlists; required initiator role; and independent approval-role quorums.

Amounts are decimal strings parsed with Python Decimal. Binary floating-point values, NaN, infinity, zero and negative transaction amounts are rejected. Currency identifiers must be canonical uppercase three-letter codes.

Role membership is supplied as trusted deployment configuration. Roles are not accepted from the signed request payload. The requester cannot satisfy an approval requirement, and each approval identity is counted once. Approval roles are evaluated independently; two signatures from one role do not satisfy another role's quorum.

## Evaluation inputs

AuthorityScopeEngine.evaluate(request, decision, committed_period_total) accepts the signed authorization request envelope, an already-allowed AuthorizationDecision, and the authoritative committed amount for the same tenant, scope and period, supplied as a decimal string by the caller.

The evaluator also binds the decision's request ID and requester identity back to the signed request envelope; a decision for another request cannot be reused. The request payload must contain request_id, action, resource_type, resource_id, amount, currency, period_key, organization_id, account_id and counterparty_id.

## Important transactional limitation

V1 is an evaluator, not a reservation engine. It does not itself read the ledger, lock a period bucket, reserve funds, or prevent two concurrent requests from both observing the same remaining period capacity. The caller must obtain committed_period_total from a trusted source and it must be denominated in the same currency as the request. Cross-currency aggregation is forbidden unless a separate, governed FX conversion supplies a normalized ledger amount. Until the evaluator is integrated into the executor's same-database transaction with an atomic usage reservation and receipt, it must not be used as the sole control for real payments, credit, token mint/burn or custody.

period_window declares the intended accounting window; the caller is responsible for deriving and verifying period_key and querying the matching ledger bucket. A later transactional integration must own period derivation and reservation rather than trusting caller-provided period labels.

## Explicit non-goals

- No payment, journal, credit, custody, token or ownership execution.
- No role enrollment or role mutation.
- No dynamic scope administration or signed scope-policy store.
- No distributed quota coordination or cross-database atomicity.
- No claim of production readiness.

## Files

- Implementation: src/synergy_sues/authority_scope.py
- Tests: tests/test_synergy_sues_authority_scope.py
- Contract: interfaces/synergy_sues_authority_scope.schema.json
