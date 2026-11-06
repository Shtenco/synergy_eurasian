# SYNERGY SUES — Federation Identity and Signed Event Envelope V1

Status: executable research reference on PR #11. Ed25519 signatures authenticate registered signing keys; this is not a production PKI or authorization engine.

## Purpose and security boundary

The durable event store and SHA-256 hash chain provide persistence and tamper evidence relative to a trusted digest. They do not identify the author. V1 adds explicit federation identities, an out-of-band trusted-key registry, versioned signed envelopes, signer/tenant/key binding, validity windows, revocation and fail-closed verification.

A signature proves possession of the private key corresponding to a pre-registered public key. It does not prove factual truth, business ownership, or permission to post accounting entries, move cash, lend, issue tokens, custody assets or change ownership.

## Identity and trust registry

FederationIdentity identifies an organization, node or service using identity_id, tenant_id, identity_type and optional display name. TrustedKeyRegistry is a local explicit allowlist. Incoming messages cannot create identities or establish their own trust.

TrustedSigningKey binds one Ed25519 public key to exactly one identity and tenant. It includes key_id, a base64-encoded 32-byte public key, valid_from, optional exclusive valid_until and optional revoked_at. Key IDs cannot be overwritten. Rotation uses a new key ID followed by revocation of the old key.

## Signed envelope

The schema is synergy.signed-event.v1. The Ed25519 signature covers canonical UTF-8 JSON of every envelope field except signature_b64: schema version, fixed algorithm, identity, tenant, key ID, signing timestamp and the complete immutable event including payload, source reference, evidence IDs, aggregate sequence, previous hash and event hash.

Canonical JSON sorts object keys, uses compact separators, preserves Unicode and rejects non-finite numbers. Arrays retain their order. The event hash is independently recomputed using the V7-compatible canonical event shape before signature verification. No algorithm negotiation or fallback exists; unsupported schema and downgrade attempts fail closed.

## Verification order

1. Check exact schema version and Ed25519 algorithm.
2. Resolve the identity from the pre-provisioned registry.
3. Bind envelope tenant to registered identity and signing key.
4. Resolve the exact key ID.
5. Enforce signing-time validity and revocation.
6. Enforce current receiving-time validity and revocation.
7. Recompute the immutable event hash.
8. Verify the Ed25519 signature using the registered public key.

The sender's public key is never accepted as a trust anchor. Unknown identity/key, altered payload/hash, wrong tenant, expired or not-yet-valid key, revoked key, malformed signature and algorithm downgrade are rejected.

## Private key handling

generate_ed25519_keypair returns raw private key bytes once and a base64 public key. The registry stores public keys only. Never put private key material in event payloads, source control or logs. The helper is for local research and tests; production signers should use an HSM/KMS or isolated signing service with audited access, rotation, backup and compromise response.

The cryptography package supplies the Ed25519 primitive and is declared as a dependency. Private keys are not persisted by this module.

## Authentication is not authorization

The registry answers whether a signature verifies under a key trusted for an identity and tenant. It does not decide whether that identity may perform an action. A signed journal event is not automatically an authorized posting; a signed payment instruction is not payment authorization; a signed credit proposal is not a credit facility; a signed token event is not mint permission; a signed claim is not proof of physical delivery or cash receipt.

Financial OS remains the accounting authority; Pay System remains the payment execution authority. SUES identity and transport layers cannot override those boundaries.

## V1 limitations and next hardening

Not implemented: distributed PKI, certificate chains, HSM/KMS integration, identity discovery, database tenant isolation, policy authorization, trusted timestamping, transport replay windows, multi-signature approvals, broker mTLS or historical signature archival. Event IDs, aggregate sequence and hash chain provide source-level replay identity; delivery remains at-least-once and consumers must deduplicate.

Tests cover valid signatures, payload/hash tampering, unknown identities and keys, tenant mismatch, validity windows, revocation, duplicate key IDs, canonical JSON and algorithm downgrade rejection.

## Durable trust registry V1

`SQLiteTrustedKeyRegistry(database_path)` provides a persistent, file-backed local trust registry. It stores identities and public-key records, and records key revocation as a separate immutable fact rather than overwriting the original key record. Registration and revocation plus their administrative audit events commit atomically under SQLite `BEGIN IMMEDIATE`.

The registry records identity registration, key registration (including a SHA-256 fingerprint, never private key material) and key revocation. Audit events form a canonical SHA-256 chain with sequence and previous-hash links. Database triggers reject UPDATE/DELETE against identity, key, revocation and audit rows. Startup verifies the audit chain and fails closed if it is inconsistent. Verification refreshes persisted trust state each time so another process's key revocation is observed by already-running registry instances.

This is a single-host reference backend. SQLite WAL must not be treated as a distributed database or placed on arbitrary network filesystems. Protect the database, WAL/SHM files and backups with OS-level access controls. A local hash chain and triggers are tamper-evident against ordinary application-level mutation, not a defense against an attacker who can rewrite the database file, drop triggers or replace backups. Production requires externally anchored audit checkpoints, managed administrative authorization, key enrollment approvals, backup/restore controls and eventually a PostgreSQL or dedicated trust service.
