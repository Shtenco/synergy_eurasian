# SLE Signed Award Authorization V1

## Purpose

A signed award authorization binds a reward decision to one exact contribution result and a bounded in-kind/service obligation. It is a cryptographic authorization artifact, not a credit instrument or payment instruction.

Implementation: `src/synergy_labor_award_authorization.py`
Schema: `interfaces/sle_award_authorization.schema.json`
Tests: `tests/test_synergy_labor_award_authorization.py`

## Signed fields

The Ed25519 signature covers the complete canonical JSON envelope, excluding only the `signature` field, under domain separator `SYNERGY_SLE_AWARD_AUTHORIZATION_V1\0`.

The signed terms include:
- globally intended `award_id` (uniqueness is not globally enforced by this verifier);
- `source_contribution_id` and SHA-256 `result_digest`;
- `beneficiary_id`, `issuer_id`, `service_code`, and non-monetary `unit`;
- positive decimal-string `quantity` and `capacity_id`;
- `policy_version` and `budget_ref`;
- issue/expiry interval and signer/key identity;
- mandatory signer role `REWARD_AUTHORIZER`.

Any change to a signed economic term invalidates the signature. Quantity is a positive finite decimal string; floats, exponent notation, zero, negatives, NaN and infinity are rejected.

## Verification

The verifier requires a caller-supplied trusted key registry. It checks:
1. exact field set and schema version;
2. canonical domain-separated signature;
3. signer principal and `REWARD_AUTHORIZER` role against the registry;
4. current key validity and revocation;
5. authorization validity interval within key validity;
6. positive quantity and SHA-256 result digest format.

The returned authorization digest is a stable SHA-256 fingerprint of the signed canonical payload.

## Authority and safety boundaries

- This module does not issue service credits, reserve capacity, transfer claims, mint SDU, post accounting entries, or authorize payments.
- It does not prove that the contribution is truthful; it binds an authorization to a supplied contribution/result reference.
- It does not provide cross-system duplicate prevention. A globally shared award registry with atomic reserve/consume/release semantics is still required across SLE, Financial OS and other reward engines.
- A caller-supplied key registry is not itself authenticated or governed here. Registry governance, key ceremony, rotation, revocation distribution and audit remain external dependencies.
- `budget_ref` is a reference only; the verifier does not inspect a budget or establish that funds/capacity exist.
- `capacity_id` is a reference only; the verifier does not reserve or validate actual capacity.
- Financial OS remains the sole accounting and payment authority. No monetary value is inferred from labor score or service quantity.

## Status

Reference verification component under PR #17. Not production-ready and not a cross-repository integration. Focused tests are included in the PR's dedicated CI step; repository-wide CI must be assessed separately.
