# SYNERGY SUES — Durable Event Store and Transactional Inbox/Outbox V1

Status: executable SQLite reference implementation on research branch. This is infrastructure groundwork, not a production multi-region broker or financial authorization system.

## 1. Objective and guarantees

The module `src/synergy_sues/event_transport.py` implements three durable primitives:

1. An append-only, file-backed SQLite event log with per-aggregate sequence and SHA-256 hash-chain verification.
2. A transactional outbox: appending an event and enqueueing its outbound message occur in one SQLite transaction.
3. A transactional inbox: a consumer's local database writes and its inbox receipt commit in one SQLite transaction.

The transport delivery contract is **at-least-once**. Exactly-once delivery across independent systems is not claimed. Duplicate delivery is expected and must be handled through stable message IDs and idempotent consumer processing.

## 2. Durable event log

`DurableEventStore(database_path)` opens a persistent SQLite database and initializes:

- `event_log` — immutable event envelopes, globally unique event IDs, unique aggregate sequence and unique non-empty idempotency keys;
- `aggregate_heads` — latest sequence and event hash for each aggregate;
- `outbox` — delivery state, attempts, lease token, retry availability and terminal status;
- `inbox` — consumer-scoped durable message receipts.

Every writer obtains `BEGIN IMMEDIATE`. This serializes competing SQLite writers across store instances/processes before reading the aggregate head. Event hash computation follows the V7 canonical envelope shape and preserves compatibility with `adapt_v7_event_store`. On initialization, the store verifies all persisted events, aggregate heads and outbox-to-event references; corrupt state fails closed.

A file-backed database is required. `:memory:` is intentionally rejected because independent operation connections would not share the same durable state. SQLite WAL and a configurable busy timeout are enabled.

## 3. Atomic append + outbox

`append(event, destination, topic, enqueue=True)` performs, in one transaction:

1. validate event identity, payload, evidence IDs and timezone-aware timestamps;
2. read the aggregate head and require the exact next sequence;
3. validate any supplied previous hash;
4. compute the canonical SHA-256 event hash;
5. insert the immutable event and update its aggregate head;
6. insert a deterministic outbox message ID for `(event_id, destination)`.

If any step fails, the transaction rolls back. The event cannot commit while its requested outbox record fails to commit. `enqueue=False` is available for an intentionally local-only event; callers must opt into that behavior explicitly.

## 4. Outbox lease protocol

`claim_outbox(limit, lease_seconds, now)` claims pending messages whose retry time has arrived, or inflight messages whose lease expired. Each claim increments attempts and receives a fresh random lease token.

The worker then sends the message to its configured transport. After the transport confirms acceptance, the worker calls `ack_outbox(message_id, lease_token)`. A stale worker cannot acknowledge a message after another worker has reclaimed it because the lease token has changed.

On a transient failure, `fail_outbox(...)` schedules a retry. Once the configured maximum attempt count is reached, the message moves to `DEAD` for operator review. The module does not invent exponential backoff; callers supply retry delay and maximum attempts so policy remains explicit.

**Crash window:** if a remote broker accepts a message but the sender crashes before local acknowledgement, the message will be delivered again after lease expiry. This is expected at-least-once behavior, not a bug.

## 5. Transactional inbox protocol

`consume_inbox(consumer, message, handler)`:

1. validates the envelope and recomputes the event hash;
2. opens a write transaction;
3. checks `(consumer, message_id)` for an earlier receipt;
4. runs the handler using the exact SQLite connection/transaction supplied;
5. inserts the inbox receipt;
6. commits the handler's local database effects and receipt together.

An exact duplicate returns `False` and does not rerun the handler. Reuse of a message ID with a different event hash is rejected. If the handler raises, both its database writes and the inbox receipt roll back, allowing a safe retry.

**Handler contract:** it must use only the supplied SQLite connection and must not perform network calls, payments, filesystem writes or other external side effects. The inbox can atomically protect only local effects in the same database transaction. Any subsequent external effect requires its own outbox.

## 6. Integrity, authority and security boundaries

- SHA-256 detects accidental/tampered content relative to a trusted hash; it does not prove who authored the event.
- No event signature, key rotation, broker authentication, transport encryption, authorization policy or multi-tenant access control is implemented here.
- Event persistence and delivery do not authorize journal posting, cash movement, lending, token issuance, custody or ownership changes.
- A future Financial OS adapter must independently validate entity/account mapping, authorization evidence, effective date, source evidence, currency and posting idempotency.
- The current durable store is a single-host SQLite reference. Do not place a SQLite WAL database on an arbitrary network filesystem and treat it as a distributed database.

## 7. Operational boundaries and next work

Before production deployment, add:

1. a PostgreSQL backend for multi-process/multi-host deployment with explicit transaction isolation and migrations;
2. broker adapter(s), authenticated transport, TLS, signatures and key lifecycle;
3. dead-letter inspection/replay tooling and operator audit records;
4. retention, backup, restore drills, WAL checkpoint policy and disk-capacity monitoring;
5. consumer versioning, schema registry and poison-message quarantine;
6. transactional checkpoint/snapshot protocol for bounded replay;
7. chaos tests for process kill, disk-full, lock contention, broker-ack loss and restore from backup.

The SQLite implementation is a durable local reference and contract testbed, not a claim that the distributed federation problem is solved.

## 8. Verification

`tests/test_synergy_sues_event_transport.py` covers persistence across store reconstruction, atomic event/outbox creation, sequence/idempotency constraints, competing store instances, lease expiry and fencing, retry/dead-letter transitions, inbox deduplication, rollback on handler failure, tamper rejection and compatibility with the V7→SUES event adapter.
