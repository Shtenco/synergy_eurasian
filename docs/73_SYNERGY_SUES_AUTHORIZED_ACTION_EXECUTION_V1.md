# SYNERGY SUES — Authorized Action Execution V1

Status: executable single-host reference executor. It consumes a signed authorization request once and commits a local SQL effect with an append-only execution receipt. It is not a distributed transaction coordinator or a payment execution rail.

## Why a decision is not an execution token

A positive `AuthorizationDecision` is a policy evaluation result, not a reusable bearer credential. If an executor accepts the same signed request repeatedly, a valid signature and approval quorum could accidentally authorize duplicate journal postings or other repeated effects. V1 therefore adds a durable request-consumption boundary.

## Execution contract

`AuthorizedActionExecutor` receives:
- the signed `AUTHORIZATION_REQUEST`;
- signed `AUTHORIZATION_APPROVAL` events;
- the deny-by-default policy evaluator;
- the trusted identity/key registry;
- a handler that receives the executor's SQLite connection, signed request and authorization decision.

The executor re-evaluates authorization before attempting execution. Denied requests do not call the handler and do not create receipts.

For an allowed request, it opens a write transaction with `BEGIN IMMEDIATE`, checks the request ID and signed event identity, executes the handler using the same SQLite connection, writes the immutable receipt and commits. The request ID, event ID and event hash are bound together. The same request ID with the same event hash returns `ALREADY_EXECUTED` without calling the handler again. Reusing a request ID with a different event hash is a hard conflict. A different request ID cannot consume the same event ID.

If the handler raises or its result cannot be encoded as canonical JSON, the transaction rolls back: both local effects and the consumption receipt are absent, allowing a safe retry after the cause is corrected.

## Atomicity and external effects

The handler must perform only local SQL work through the supplied connection. It must not perform network calls, send payments, write files, or trigger other external side effects. For an external operation, call `AuthorizedActionExecutor.enqueue_outbox(connection, idempotency_key, destination, topic, payload)` from the handler. This inserts a deterministic message ID and PENDING outbox row in the same database transaction as the local effect and execution receipt. Repeating the same idempotency key/scope with the same payload is idempotent; reusing it with a different payload fails and rolls back the protected action. A separate dispatcher must claim and deliver pending rows after commit. Delivery is at-least-once; the downstream receiver must have its own idempotency key and inbox.

This is not a distributed exactly-once guarantee. A database commit cannot atomically include a remote bank, blockchain, broker, or unrelated service. The action executor is a local idempotency boundary.

## Execution receipts

Each committed receipt records request ID, request event ID/hash, action, resource type/ID, requester identity, execution timestamp, canonical JSON handler result and the full authorization decision evidence: matched policy rule IDs, distinct approver identities, and the exact signed approval event IDs/hashes. This preserves the evidence trail needed to reconstruct why the action was allowed. Receipts are append-only at the SQLite application layer and form a SHA-256 hash chain. Startup verifies the chain and fails closed if inconsistent.

The chain and triggers detect ordinary application-level mutation; they do not protect against an administrator who can rewrite the database, drop triggers or replace backups. Production requires OS-level file protection, externally anchored checkpoints, backups/restore drills and a managed database service.

## Security boundaries

- Authentication comes from the trusted Ed25519 registry.
- Authorization comes from explicit tenant/action/resource policy and signed independent approvals.
- Execution idempotency comes from the durable receipt transaction.
- The handler's local SQL effects are not a license to bypass the canonical Financial OS or Pay System.
- No positive decision automatically authorizes a payment, loan, token mint/burn, custody transfer or ownership change.
- Financial OS remains the canonical accounting authority; Pay System remains the payment execution authority.

## Limitations

V1 is single-host SQLite. It does not provide distributed locking, cross-database atomicity, policy-store snapshot isolation, a remote action dispatcher, HSM/KMS signing, mTLS, PostgreSQL, or multi-region consensus. Rules are supplied by the in-memory policy evaluator. Before production, policy version must be pinned into each decision and executor transaction, and external actions must be represented by transactional outbox messages with receiver-side deduplication.

## Tests

Tests cover one-time consumption, request-ID conflict, event-ID reuse prevention, denied request non-execution, handler rollback and retry, concurrent executor instances, append-only receipts, hash-chain tamper detection, canonical JSON result validation and transactional outbox idempotency/rollback.


## Versioned policy snapshot guard

When the executor receives a decision carrying `policy_version` and `policy_hash`, it requires the policy store table to exist in the **same SQLite database**. After acquiring `BEGIN IMMEDIATE` and before invoking the handler, it compares the decision's tenant policy version/hash with the latest persisted snapshot. A missing store or stale snapshot fails closed. Because the policy store uses the same database, the write lock prevents a concurrent policy mutation between this check and the execution receipt commit.

This closes the local check-to-commit race for the single-host SQLite reference. It is not a distributed transaction: separate databases, hosts or regions require a managed shared transactional authority or a separately designed consensus/fencing protocol. The execution handler still may perform only local SQL effects in the executor transaction.
