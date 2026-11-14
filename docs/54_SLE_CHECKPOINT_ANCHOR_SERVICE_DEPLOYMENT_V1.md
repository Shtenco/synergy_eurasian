# Independent SLE checkpoint anchor service

This directory-level deployment unit is implemented by
`src/synergy_labor_checkpoint_service.py`. It is a separate WSGI application and
must run under a separately administered service identity, host/account, database,
backup policy and credential lifecycle from the SLE award registry.

## Configuration

Set the following secrets/configuration in the service environment:

- `SLE_ANCHOR_DATABASE`: durable local database path on the anchor service.
- `SLE_ANCHOR_PRINCIPAL`: stable service identity used in audit records.
- `SLE_ANCHOR_BEARER_TOKEN`: random secret with at least 32 characters.

Construct the WSGI application using `create_app_from_environment()`. Run it only
behind a TLS-terminating reverse proxy with request-size limits, access logging that
redacts Authorization, network allow-lists, and a process manager. Do not expose
the built-in development WSGI server directly to the public Internet.

## Guarantees implemented by the application

- Durable SQLite file, WAL journal mode, FULL synchronous setting and busy timeout.
- Atomic append transaction using `BEGIN IMMEDIATE`.
- Compare-and-append against the current remote tail and strict monotonic event sequence.
- Unique registry/sequence, registry/digest and registry/idempotency-key constraints.
- Exact retry recognition after a committed write whose response was lost.
- Append-only update/delete triggers on checkpoint rows.
- Bearer authentication, per-principal audit records and no-store responses.
- Bounded request body and bounded pagination size.
- Restart recovery by reading the durable checkpoint chain.

The server stores signed records but does not independently establish that the
signature is valid or that labor evidence is truthful. Auditors must continue to
verify Ed25519 signatures and event-chain correspondence using the trusted key
registry. A bearer token grants publication/read access to this service; deploy
separate tokens and a separate auditor endpoint/role policy if read/write separation
is required.

## External durability and recovery requirements

SQLite WAL and FULL synchronous protect against ordinary process crashes; they do
not protect against loss of the host, disk, administrator credentials or service
account. Production activation still requires independently administered immutable
backups or replication, a tested restore procedure, off-host copies, alerting,
credential rotation/revocation and a documented RPO/RTO. Do not point this service
at the award registry database or its backup volume. Restore must validate the
latest checkpoint digest against an independently held copy before resuming writes.

## Limits

This is a durable single-node anchor service, not a consensus cluster or multi-region
replicated database. SQLite serializes writers on this database. The app's CAS
transaction provides single-database concurrency correctness, but high availability
and disaster recovery depend on external deployment infrastructure and restore drills.
