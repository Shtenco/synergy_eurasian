# 49 — SLE Cryptographic Evidence Verification V1

**Status:** implemented Ed25519 verification primitive; governed key registry and external evidence storage are integration dependencies.

## 1. Purpose

V1 scoring originally validated evidence metadata only. The new `src/synergy_labor_evidence.py` adds an explicit cryptographic path:
- content-addressed evidence bytes are re-hashed with SHA-256;
- a signer envelope binds the evidence ID, subject, signer, role, content digest, key ID and validity interval;
- Ed25519 signature is checked against a supplied trusted public-key registry;
- signer role, principal binding, key validity, expiry and revocation are checked;
- `score_verified_contributions` verifies all referenced evidence before calling the deterministic scorer.

## 2. Signed envelope

The strict schema is `interfaces/sle_evidence_envelope.schema.json`.

The signer signs canonical JSON bytes:
- UTF-8;
- keys sorted lexicographically;
- compact separators;
- non-ASCII preserved;
- NaN/infinity forbidden;
- the signature field excluded;
- domain prefix `SYNERGY_SLE_EVIDENCE_V1\0`.

The payload includes:
`schema`, `evidence_id`, `subject_id`, `signer_id`, `signer_role`, `content_sha256`, `issued_at`, `expires_at`, `key_id`.

The signature is Ed25519 and encoded as base64. The public key registry entry contains `principal_id`, `roles`, `public_key_b64`, `valid_from`, `valid_until`, and optional `revoked_at`.

## 3. Verification contract

`verify_evidence_envelope(envelope, evidence_bytes, key_registry, now=...)` fails closed when:
- envelope schema/fields differ from the strict contract;
- evidence bytes are unavailable or hash does not match;
- signer role differs from `INDEPENDENT_VERIFIER`;
- signer principal does not match the trusted key record;
- key is missing, not yet valid, expired or revoked;
- evidence is not yet valid or has expired;
- envelope validity exceeds the key validity interval;
- base64, key length, signature length or Ed25519 signature is invalid.

`score_verified_contributions(...)` additionally binds the verified evidence ID and digest to each contribution record and requires at least one evidence item signed by the record's declared independent verifier. Shared evidence may support multiple contributors only when it refers to the same benefit stream; duplicate evidence IDs within one contribution and cross-benefit reuse are rejected.

The original `score_contributions` remains a metadata-only local scorer. Callers must choose `score_verified_contributions` when cryptographic evidence verification is required. The output explicitly marks its verification scope.

## 4. Key governance is external

The function receives a public-key registry from its caller. It does not establish that the registry itself is authentic, current or governed. Production must supply a signed/versioned registry with:
- named key owners and approved roles;
- onboarding and identity proofing;
- key rotation, revocation and compromise response;
- registry digest, effective time and immutable audit;
- separation of verifier from contributor and award approver.

A valid signature proves that the holder of a registered private key signed the canonical envelope. It does not prove that the underlying claim is true, that the signer was unbiased, or that the work has economic value.

## 5. Data and privacy

Evidence bytes remain outside the ledger. The verifier accepts bytes supplied by an access-controlled evidence service. Do not place personal identifiers, health data, credentials or private keys in public events. Use pseudonymous subject IDs and minimum necessary disclosure.

## 6. Remaining gates

- Trusted key-registry authentication and version pinning.
- Durable evidence object storage, access control, retention and deletion policy.
- Independent verifier governance and conflict checks beyond self-declared role.
- Signature envelopes for award authorizations and bilateral cancellation approvals.
- Cross-system award reservation with Financial OS.
- Replay/reconciliation of the service-credit projection from immutable events.

Ed25519 verification is a necessary integrity control, not proof of legal enforceability, fair valuation or production readiness.
