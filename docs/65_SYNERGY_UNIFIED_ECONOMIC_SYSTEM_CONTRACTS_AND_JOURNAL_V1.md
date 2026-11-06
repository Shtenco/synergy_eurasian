# SUES V1 — Typed Economic Contracts and Double-Entry Journal

**Status:** initial executable reference implementation on `research/sues-audit-v1`.  
**Date:** 2026-11-06.  
**Purpose:** establish strict shared types and a balanced journal before integrating the V6/V7 model families.

## 1. Typed economic values

- `Money` stores a Decimal amount and explicit currency/asset code. Arithmetic across currencies is rejected.
- `Quantity` stores a Decimal amount and explicit unit. Arithmetic across units is rejected.
- `EconomicPeriod` has a stable ID and inclusive date boundaries.
- `FXRate` identifies base/quote currencies, a positive rate, timestamp and source. Conversion is explicit.
- `EvidenceRecord` stores provenance, status, capture time, effective dates and optional content hash.

The code intentionally does not infer FX rates, unit conversions, periods or evidence quality.

## 2. Double-entry journal

Each journal entry has a functional currency and at least two lines. Each line stores:
- transaction-currency amount;
- functional-currency valuation;
- debit/credit side;
- account, entity, source and optional counterparty;
- FX-rate reference for foreign-currency lines;
- evidence IDs.

The journal rejects unbalanced functional-currency entries, duplicate entry IDs, duplicate idempotency keys, unknown accounts, duplicate line IDs, unknown or reverse-direction FX references, post-dated FX observations and functional valuations that do not match the referenced rate. A posted entry is immutable. Corrections use a new reversing entry linked to the original; a source entry can be reversed only once.

The trial balance reports functional-currency debits and credits by account.

## 3. Physical-flow dimensional integrity

The `PhysicalFlow` contract carries source, target, resource, typed quantity, period, boundary and optional evidence. Aggregation is keyed by resource × unit × period × boundary. Internal transfer volume is never collapsed into one scalar across unlike units or time buckets.

## 4. Cross-project benefit attribution

A `BenefitEvent` identifies the underlying measurement, enterprise, period, metric and counterfactual. Multiple projects may receive a documented share of one measured benefit, but the sum of attribution weights cannot exceed 1.0. A measurement ID can be registered only once. Evidence status is preserved; scenario benefits are never silently relabelled as observed cash.

## 5. Intercompany reconciliation

The intercompany engine pairs seller and buyer records by a stable transaction ID and reciprocal entity identities. It separately reconciles P&L revenue/expense, balance-sheet receivable/payable and cash-in/cash-out pairs. Only the amount present on both sides is eligible for elimination; unmatched residuals remain explicit exceptions. Cross-currency netting is rejected.

This is an elimination control, not yet a full multi-entity consolidation engine. It does not translate subsidiary trial balances, calculate CTA, consolidate ownership/non-controlling interests, or post elimination journals automatically.

## 6. Deliberate limitations

This is an in-memory reference kernel, not yet a production ledger. It does not yet implement persistence, concurrent posting locks, account-period close, tax rules, accrual automation, subledger reconciliation, FX revaluation, consolidation, intercompany elimination, authorization/signatures or statutory reporting. It does not hold customer funds or initiate payments.

The journal balances one entity's functional currency. Multi-entity consolidation must translate subsidiary trial balances under a documented FX policy and eliminate matched intercompany balances and transactions.

## 7. Acceptance tests

The tests cover:
- rejection of mixed-currency and mixed-unit arithmetic;
- explicit FX conversion and dated evidence;
- balanced and unbalanced journal entries;
- exact mirrored reversals and forged-reversal rejection;
- physical-flow dimensional separation;
- cross-project benefit attribution capped at 100%;
- reciprocal intercompany P&L, balance-sheet and cash matching;
- foreign-currency functional valuation;
- idempotency and duplicate prevention;
- single reversal and trial-balance conservation.

Run:

```bash
python -m pytest -q tests/test_synergy_sues.py
```

## 8. Next increments

1. Add chart-of-accounts hierarchy and normal-balance reporting.
2. Add journal-to-AR/AP and bank-statement reconciliation.
3. Add multi-entity consolidation and intercompany eliminations.
4. Add period close, accruals, depreciation and inventory valuation.
5. Add persistence, concurrency, authorization and signed evidence.
