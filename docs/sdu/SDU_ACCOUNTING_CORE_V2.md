# SDU Accounting Core V2 — persistent-ledger research increment

**Status:** isolated research implementation on `feat/sdu-accounting-core-v2`.  
**Not deployed:** no token contract, production payment processor, live AMM, audited monetary policy, redemption promise or price guarantee is introduced.

## Scope and files

| File | Responsibility |
|---|---|
| `src/sdu_accounting_core.py` | Dependency-free in-memory reference ledger and invariant model |
| `migrations/001_sdu_ledger.sql` | PostgreSQL schema, deferred balance checks, immutable journal triggers and non-negative balance guard |
| `src/sdu_postgres_ledger.py` | Transactional PostgreSQL adapter, epoch-budget enforcement, journal replay audit and checkpoint persistence |
| `src/sdu_issuance_authorization.py` | Threshold validator approval of canonical issuance claims |
| `src/sdu_ledger_checkpoints.py` | Signed checkpoint creation and signature/progression verification |
| `tests/test_sdu_accounting_core.py` | In-memory accounting invariants |
| `tests/test_sdu_issuance_authorization.py` | Validator threshold and tamper tests |
| `tests/test_sdu_ledger_checkpoints.py` | Checkpoint signature and monotonicity tests |
| `tests/test_sdu_postgres_ledger.py` | PostgreSQL integration, independent-connection concurrency and database guard tests |
| `.github/workflows/sdu-accounting.yml` | Dedicated Python + PostgreSQL CI job |

This is an additive branch. It does not edit the existing Synergy economy models or replace the canonical asymmetric AMM.

## 1. Monetary representation and journal invariants

Amounts are signed integer atomic units. Python floating-point values are not accepted. PostgreSQL stores integer-valued amounts in unconstrained `NUMERIC`, so the research schema does not introduce an arbitrary fixed precision/scale ceiling. The final SDU decimal count remains a token-level configuration decision.

Every event must balance separately for every asset:

\[
\forall c:\quad \sum_{p\in Event,\ p.asset=c}p.amount=0
\]

A swap therefore has one balanced SDU posting group and one balanced USDC posting group. Unlike assets are never netted against one another.

The ledger's accounted supply is:

\[
S_c=\sum_{a:\ a.asset=c,\ a.counts\_toward\_supply}Balance(a,c)
\]

Transfers and AMM reserve movements do not change supply. Only a dedicated SDU mint or burn command changes it. The issuance and burn contra-accounts are excluded from supply.

## 2. PostgreSQL transaction model

All writes use one database transaction. The adapter locks the singleton `sdu_ledger_state` row with `FOR UPDATE` before allocating a sequence number. It then:

1. checks the idempotency key and request fingerprint;
2. locks affected accounts/balance rows in sorted order;
3. checks per-asset balance and spendable-balance constraints;
4. validates the dedicated command's authorization and epoch budget, if applicable;
5. appends the event and all postings;
6. updates balance projections and idempotency records;
7. updates the journal head sequence/hash;
8. commits everything together.

The global journal-head lock serializes all writes across independent processes and prevents two servers from double-spending the same balance. This is intentionally conservative and will limit throughput. Do not remove it or shard the sequence/hash chain until a separately reviewed concurrency design exists.

The SQL migration adds:
- unique event sequence, event hash and idempotency key constraints;
- integer-valued `NUMERIC` amounts;
- deferred event-completeness and per-asset balancing triggers;
- append-only triggers for events, postings, idempotency records, issuance claims and checkpoints;
- a database-level guard against negative balances in accounts that do not explicitly allow overdrafts.

The adapter also checks account policy and balances before writing. Database triggers are defense in depth, not a substitute for least-privilege database roles.

### Applying the migration

Use a dedicated schema-migration role, not the runtime service role:

```bash
psql "$SDU_DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_sdu_ledger.sql
```

The runtime role must not own the schema/tables, alter triggers, disable triggers, truncate journal tables, or update/delete event and posting rows. Grant only the minimum required SELECT/INSERT/UPDATE permissions. The migration does not create or manage database roles because that must be adapted to the deployment's identity and secret-management environment.

### Adapter initialization

```python
import os
import psycopg
from sdu_postgres_ledger import PostgresLedger

ledger = PostgresLedger(
    lambda: psycopg.connect(os.environ["SDU_DATABASE_URL"])
)
ledger.register_asset("SDU", 6)
ledger.register_asset("USDC", 6)
ledger.create_account("wallet:alice", "SDU")
ledger.create_account("wallet:bob", "SDU")
```

The example is an integration pattern, not a production deployment recipe. Account provisioning and user authentication must be exposed only through a trusted service.

## 3. Threshold issuance authorization

An issuance claim binds:
- unique claim ID and epoch ID;
- destination account;
- positive integer amount;
- SHA-256 digest of the supporting evidence;
- purpose;
- expiry timestamp.

Validators sign the canonical serialized claim. The verifier rejects duplicate signers, unknown validators, invalid signatures, expired claims, claims over the per-claim maximum and insufficient threshold approvals.

The PostgreSQL adapter independently enforces the configured epoch budget in the same transaction as the mint. It locks the epoch row, prevents claim reuse, increments `spent`, and commits the mint, claim record and accounting postings atomically. A failed mint rolls back the budget increment too.

**Cryptographic limitation:** the current dependency-free prototype uses HMAC-SHA256. HMAC keys are symmetric and do not provide public verifiability. This is not the final validator-key architecture. Production requires asymmetric signatures (for example Ed25519), HSM/KMS-backed key custody, validator key rotation/revocation, domain-separated signing, audit logs and a separately specified validator-selection process. The current module domain-separates issuance signatures but does not manage key custody.

The evidence digest proves only that validators signed a particular digest. It does not independently prove the underlying productive contribution is real, unique or correctly valued. Evidence verification, anti-Sybil controls, appeals and independent audits remain separate work.

## 4. Journal audit and checkpoints

`PostgresLedger.verify_integrity()` replays the event journal and verifies:
- contiguous event sequence;
- previous-hash linkage and each event hash;
- per-asset balance of every event;
- idempotency fingerprints;
- replayed balances against stored balance projections;
- absence of negative balances in ordinary accounts;
- one-to-one correspondence between mint events and verified claim records;
- claim metadata, minted amount and epoch spent/budget totals;
- database journal head against the last event.

`create_and_store_checkpoint(key)` signs the current ledger sequence and event hash and stores a local checkpoint record. The method is idempotent for a sequence and verifies the stored signature before reusing it.

**Checkpoint limitation:** storing a signed checkpoint only in the same database does not protect against a database superuser who can rewrite both journal and checkpoint rows. Export each checkpoint to an independent trust domain (separate provider/account, immutable object lock, public transparency log or other independently administered anchor). HMAC is only a prototype signature; production should use an asymmetric signing key so independent auditors can verify checkpoints without possessing the signing secret. The verifier checks checkpoint authenticity and monotonic sequence; proving continuity between two checkpoints still requires auditing the intervening event chain.

## 5. Holder and protocol-reserve burn authorization

`src/sdu_burn_authorization.py` separates two burn paths:

- **Holder burn:** the source account owner signs the exact source account, amount, purpose and expiry. The PostgreSQL adapter accepts only a valid holder signature for that account.
- **Protocol-reserve burn:** requires a threshold of independent validator approvals. The source must be an explicitly burnable account whose kind is `amm_*` or `protocol_*`. A reserve configured `burnable=False` remains unburnable even when a claim is signed.

Both paths are limited to SDU, create an immutable `SDU_BURN` event, debit the real source account, credit a non-supply burn counter and persist a unique burn claim in the same database transaction. The integrity audit checks the burn claim against the exact journal postings. Repeating a request with the same idempotency key returns the original event; a new key cannot consume an already-used burn claim.

The prototype uses HMAC-SHA256 for both holder and validator signatures. Key ownership/identity registry, asymmetric signatures, hardware key custody, wallet challenge binding and recovery are still production requirements. The holder key map is not a replacement for an authenticated wallet/account registry.

## 6. External deposit attestation and crediting

\`src/sdu_external_deposits.py\` binds an external deposit attestation to a canonical tuple: chain ID, transaction hash, asset, integer amount, destination account, block number, confirmation count, proof digest and expiry. A configured quorum of independent verifiers must sign the exact tuple. The verifier enforces chain/asset allowlists, minimum confirmations, per-asset amount limits, expiry and unique signer IDs.

The PostgreSQL adapter's \`credit_external_deposit()\` method then writes the external-asset credit, contra-account posting, event, idempotency key and unique deposit claim in one transaction. A unique database constraint on (chain ID, transaction hash, asset) prevents the same external transaction from being credited twice under a different claim ID or idempotency key. SDU issuance cannot be used to create USDC.

**Critical boundary:** the current module verifies a quorum of signed attestations; it does not independently query a blockchain, validate Merkle inclusion, verify bridge contracts or prove finality. The verifiers must be independent and must themselves validate the real chain transaction and destination. Production requires independent chain clients/light clients or audited bridge attestations, asymmetric signatures, chain reorg handling, confirmation/finality policy, token contract allowlists and operational monitoring. A ledger credit is not proof that an AMM pool reserve holds those funds; external wallet balances and actual AMM reserves must remain separate.

## 7. What remains deliberately outside this increment

- No production identity provider, wallet signature verification or account-ownership authorization.
- No production key management, validator election, DAO governance, anti-Sybil or evidence oracle.
- No AMM quote engine, LP accounting, fee routing or oracle integration.
- No AI monetary-policy optimizer or long-horizon simulation.

The in-memory core remains a reference model, not the persistence layer. Python underscore naming is not a security boundary; never expose internal posting methods or database credentials to untrusted callers.

## 8. Canonical asymmetric AMM compatibility

The existing asymmetric AMM formulas remain the canonical research baseline. They are not replaced with a constant-product `x*y=k` curve.

Before implementing the PostgreSQL swap settlement path, the following accounting semantics must be specified and tested:
1. whether the buy fee remains in the pool or is transferred to protocol revenue;
2. gross/net USDC movement on buys;
3. gross/net SDU and USDC movement on sells;
4. exact timing and meaning of `P_terminal` in the sell path;
5. the relationship between `q`, `z=q-burn` and SDU actually removed from pool reserves;
6. slippage/min-out, reserve, oracle-staleness and sandwich-risk checks.

Issuance does not automatically add SDU to AMM reserves. External voluntary burns reduce total supply but not pool SDU reserve unless those tokens are actually removed from the pool. AMM quote, SDU reserve, USDC reserve, external reference price and mark-to-market TVL must remain separate measurements.

## 9. Test and CI commands

Pure-Python tests:

```bash
python -m pytest -q \
  tests/test_sdu_accounting_core.py \
  tests/test_sdu_issuance_authorization.py \
  tests/test_sdu_burn_authorization.py \
  tests/test_sdu_ledger_checkpoints.py
```

PostgreSQL integration tests require PostgreSQL 16+, psycopg 3 and `SDU_TEST_DATABASE_URL`:

```bash
python -m pip install "pytest>=8,<9" "psycopg[binary]>=3.2,<4"
python -m pytest -q tests/test_sdu_postgres_ledger.py
```

The dedicated GitHub Actions workflow starts an ephemeral PostgreSQL 16 service and runs all SDU test files plus Python compilation. The current source contains 61 test functions across the six SDU test modules; the final pass count must be taken from the latest completed Actions run, not inferred from test-file counts.

The repository-wide EIIOM CI has a separate pre-existing test-collection failure involving missing `synergy_v66.credit` on the base branch. This SDU workflow does not hide or claim to repair that unrelated failure.

## 10. Constitutional compatibility

This increment preserves the intended research constitution:
- **ALL:** anyone may initiate an issuance claim; initiation is not unilateral mint authority.
- **HYBRID:** AI, DAO and independent validators have distinct roles.
- **AUTONOMOUS:** AI actions must remain inside constitutional limits.
- **UNLIMITED:** no lifetime supply ceiling; epoch budgets remain possible.
- **UNIVERSAL:** holders may burn their own tokens; protocol-reserve burn requires explicit authorization.

No mainnet activation, token-supply change, AMM replacement, redemption promise or guaranteed price appreciation is introduced.
