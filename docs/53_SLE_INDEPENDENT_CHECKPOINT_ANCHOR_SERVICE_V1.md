# SLE independent checkpoint anchor service contract

## Deployment boundary

HttpCheckpointAnchorStore is a production client adapter, not a hosted anchor service. Configure it against a separately administered HTTPS service with durable storage, independent credentials, monitoring, backups and a recovery process. Do not point it at the same SQLite host, filesystem, administrator account or backup domain as the award registry. Loopback HTTP is permitted only for tests.

The token provider supplies credentials at request time. Never commit tokens to source, log them, place them in URLs or reuse them across unrelated trust domains.

## Required HTTP API

Base URL: https://<independent-service>

- GET /v1/registries/{percent-encoded-registry-id}/checkpoints[?cursor=...] returns {"items":[checkpoint,...],"next_cursor":null|string}. Pagination must provide a complete, non-overlapping traversal.
- POST /v1/registries/{registry-id}/checkpoints accepts {"checkpoint":{...},"expected_previous_checkpoint_digest":"<sha256>"}.
- The service MUST atomically compare the expected digest with its current tail (genesis for an empty registry), validate continuity and durably append in one indivisible operation.
- Requests carry Authorization: Bearer ..., If-Match: <expected-tail-digest>, and Idempotency-Key: <SHA-256 of canonical checkpoint JSON>.
- A successful append returns 200/201. A stale tail returns 409. Same-key retries must be idempotent and key reuse with different bytes rejected. The client fails closed on auth errors, conflicts, malformed responses and transport errors. Redirects are disabled.

## Required server-side controls

Enforce authenticated writer identities and distinct reader/auditor permissions; append-only retention; unique idempotency keys; atomic compare-and-append; durable replication; immutable or independently protected backups; audit logs; rate limits; bounded responses; TLS; key rotation; and restore drills. At least one recovery copy must be outside both the application and anchor service primary failure domains. A restored service must prove the latest tail digest before accepting writes.

## Recovery and concurrency

A new client instance recovers by enumerating the durable remote chain. If the remote service loses all anchors, verification returns invalid and the registry MUST remain fail-closed; never silently create a new genesis chain. Concurrent writers racing from one tail must yield exactly one append; stale writers re-read, re-audit the registry and create a newly signed checkpoint. Never automatically re-sign stale data.

## Security limitations

A valid signature proves only that an authorized key signed the checkpoint bytes, not that the labor event was truthful. Events after the newest checkpoint remain unanchored until publication. The client alone does not establish service independence, availability, legal enforceability or distributed consensus. A real endpoint, identity policy, secret manager, independent operator and tested backup/restore evidence remain required before production activation.


## Freshness policy

The core checkpoint verifier establishes cryptographic validity but does not decide whether the latest anchor is recent enough for a particular deployment. The separate check_registry_checkpoint_freshness helper evaluates a timezone-aware current time against a deployment-supplied maximum age. Production callers must combine a fresh result with a successful verify_registry_checkpoints result and alert/fail closed when either fails. Choose the maximum age from the acceptable unanchored-event exposure window; it is an operational risk limit, not a cryptographic constant.
