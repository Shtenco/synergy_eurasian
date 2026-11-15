# SDU Accounting Core V2 — research implementation

**Status:** isolated research prototype on feat/sdu-accounting-core-v2.  
**Not deployed:** this is not a token contract, production ledger, live AMM, audited monetary policy, or promise of redemption or price appreciation.

## Scope of this increment

This increment adds:

- src/sdu_accounting_core.py — dependency-free in-memory event ledger.
- tests/test_sdu_accounting_core.py — focused invariant, retry, reversal, and concurrency tests.

It does not modify the existing Synergy economic models or the canonical asymmetric AMM snapshot.

## 1. Monetary representation

Amounts are signed integer atomic units. Floating-point values are rejected. Each asset declares a decimal precision through AssetSpec; the final SDU on-chain decimal count remains an explicit configuration decision and must match the eventual token implementation.

A posting is (account_id, asset, signed_integer_amount). Positive amounts credit an account; negative amounts debit it.

Every event must balance separately for each asset:

\[
\forall c:\quad \sum_{p \in Event,\ p.asset=c} p.amount=0
\]

A multi-asset swap therefore has an SDU-balanced leg set and a USDC-balanced leg set. The ledger does not infer an exchange rate or silently net unlike assets.

## 2. Supply accounting

The circulating/accounted token supply is derived from balances of accounts marked counts_toward_supply=True:

\[
S_c=\sum_{a:\ a.asset=c,\ a.counts\_toward\_supply} Balance(a,c)
\]

The technical issuance and burn contra-accounts are excluded.

For completed operations:

\[
S_{t+1}=S_t+Mint_t-Burn_t
\]

Transfers, AMM reserve movements, fee transfers and LP movements do not change total supply. A burn reduces supply only when a real source-account debit and burn-counter credit are committed.

Account.burnable=False blocks burn from a protocol reserve. Reserve accounts should be configured as non-burnable unless an explicit protocol rule authorizes a separate operation.

## 3. Event and posting guarantees

- Events are frozen records with monotonically increasing local sequence numbers.
- Each event stores its postings, actor, timestamp, idempotency key, metadata and previous-event hash.
- A SHA-256 hash chain makes accidental or partial modification detectable when checked against a trusted checkpoint.
- Balances are a projection and can be rebuilt from the event list.
- Corrections are new reversal events; history is not edited.
- Reversal is refused if the original event was already reversed. Reversal can also fail when the original recipient has already spent the funds.
- A repeated idempotency key with the same command returns the original event. Reuse for a different command is rejected.
- A command validates every posting and resulting balance before changing the projection or appending the event.

**Hash-chain limitation:** a hash chain stored only in one mutable database does not prevent a privileged attacker from rewriting the entire chain and recalculating hashes. Production must periodically sign and publish/anchor checkpoints outside the ledger's administrative trust boundary.

## 4. Privileged operations and trust boundary

The public post() method rejects technical system_* accounts and reserved event types SDU_MINT, SDU_BURN and REVERSAL. Mint and burn use dedicated command methods; reversals use the internal posting path to restore the exact original postings.

issue() requires and records an approval_ref, but the prototype does not validate the referenced approval, validator signatures, evidence, epoch budget, or constitutional limits. The reference is an audit link, not proof of authorization. A production issuance service must verify those conditions before calling the ledger.

Python's underscore naming is not a security boundary. The module must remain behind a trusted command service; untrusted users must never receive direct access to account creation or internal posting methods. The prototype also does not authenticate actor_id or prove that the actor owns the source account for a transfer or voluntary burn. Owner authorization and key/signature verification belong in the command/API layer.

## 5. Atomicity and concurrency scope

The prototype uses an in-process reentrant lock. It prevents two threads in this process from spending the same available balance concurrently.

It does not provide:
- persistence across process restarts;
- coordination between multiple processes or servers;
- database-level atomic commit;
- durable idempotency across restarts;
- distributed consensus or finality.

A production implementation needs a transactional database write that commits the event, all postings, the idempotency record and the balance projection together. Unique constraints must protect idempotency keys, and account locking or serializable/optimistic concurrency control must protect against concurrent overspending. The current in-memory lock is a test harness, not a substitute.

## 6. What is deliberately not implemented yet

### AMM

No trade-pricing function is included in this increment. The ledger can atomically record a multi-asset settlement after an independent quote has been validated, but it does not calculate the quote.

Before implementing the canonical asymmetric AMM, the following details must be resolved without replacing its core formulas:

1. Whether the buy fee remains in the pool or is transferred to the protocol.
2. The exact gross/net USDC reserve movement on buys.
3. The exact gross/net SDU and USDC movement on sells.
4. The meaning and timing of P_terminal in the sell path.
5. The relationship between q, z=q-burn, and the amount actually removed from the pool.
6. Minimum-output, maximum-slippage, reserve and oracle-staleness checks.

Until those are explicit, a long-horizon AMM simulation would risk internally inconsistent reserve accounting.

### Issuance policy

No AI policy optimizer, DAO voting, Sybil defence, validator selection, epoch budget allocator, CPI estimator, or productive-claim verification is implemented here.

### External assets

USDC is represented only as a separately denominated ledger asset. The prototype does not establish that any USDC reserve exists outside a test fixture or that USDC is redeemable.

## 7. Test coverage in this increment

The focused test file covers:

1. Mint → transfer → burn supply conservation.
2. Required approval reference (without claiming to verify it).
3. Insufficient-funds rejection without partial writes.
4. Idempotent retry.
5. Idempotency-key conflict.
6. Per-asset balance checks.
7. Atomic multi-asset settlement.
8. Account/asset mismatch rejection.
9. Reversal and duplicate-reversal rejection.
10. Concurrent double-spend attempt.
11. Hash-chain continuity and projection replay.
12. Protocol-reserve burn restriction.
13. Non-positive command amount rejection.
14. Projection reconstruction.
15. Public-post attempt to bypass the issuance counter gate.\n16. Forged reversal-event attempt.\n17. Supply-counted account overdraft configuration rejection.\n18. Pre-seeded system-counter configuration rejection.

Run the focused tests:

    pytest -q tests/test_sdu_accounting_core.py

The local implementation check for this increment completed with 19 passing tests. This is not a claim that the repository-wide CI suite has passed.

## 8. Required next engineering steps

1. Add a persistent PostgreSQL adapter with transactionally committed event, postings, idempotency and projection.
2. Add database constraints for per-asset balancing, unique idempotency keys, immutable posted rows and non-negative spendable balances.
3. Add signed authorization objects for minting and protocol-reserve burn.
4. Add durable event sequence allocation and external hash checkpoints.
5. Specify and test the canonical asymmetric AMM fee and reserve movements.
6. Add independent reconciliation reports for token supply, AMM SDU reserve and AMM USDC reserve.
7. Only then connect production agents and long-horizon monetary-policy simulations.

## 9. Constitutional compatibility

This prototype is designed to preserve the existing research constitution:

- **ALL:** any participant may initiate a claim; initiation is not unilateral mint authority.
- **HYBRID:** AI, DAO and independent validators have separated responsibilities.
- **AUTONOMOUS:** AI policy actions must remain inside constitutional bounds.
- **UNLIMITED:** no lifetime supply ceiling; epoch constraints remain possible.
- **UNIVERSAL:** holders may burn their own tokens; protocol reserve burn requires explicit authorization.

No mainnet activation, token-supply change, AMM replacement or redemption promise is introduced by this research increment.
