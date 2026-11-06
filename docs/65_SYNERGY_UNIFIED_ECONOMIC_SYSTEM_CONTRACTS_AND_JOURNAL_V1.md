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

Each journal entry has a functional currency and at least two lines. A journal can be scoped to one entity and rejects cross-entity postings; consolidated elimination journals use a distinct consolidation entity ID. Each line stores:
- transaction-currency amount;
- functional-currency valuation;
- debit/credit side;
- account, entity, source and optional counterparty;
- FX-rate reference for foreign-currency lines;
- evidence IDs.

The journal rejects unbalanced functional-currency entries, duplicate entry IDs, duplicate idempotency keys, unknown accounts, duplicate line IDs, unknown or reverse-direction FX references, post-dated FX observations and functional valuations that do not match the referenced rate. Batch posting validates every entry before committing any, preventing a partially posted trade or consolidation batch. A posted entry is immutable. Corrections use a new reversing entry linked to the original; a source entry can be reversed only once.

The trial balance reports functional-currency debits and credits by account.

## 3. Physical-flow dimensional integrity

The `PhysicalFlow` contract carries source, target, resource, typed quantity, period, boundary and optional evidence. Aggregation is keyed by resource × unit × period × boundary. Internal transfer volume is never collapsed into one scalar across unlike units or time buckets.

## 4. Cross-project benefit attribution

A `BenefitEvent` identifies the underlying measurement, enterprise, period, metric and counterfactual. Multiple projects may receive a documented share of one measured benefit, but the sum of attribution weights cannot exceed 1.0. A measurement ID can be registered only once. Evidence status is preserved; scenario benefits are never silently relabelled as observed cash.

## 5. Intercompany reconciliation

The intercompany engine pairs seller and buyer records by a stable transaction ID, reciprocal entity identities and matching period. It separately reconciles P&L revenue/expense, balance-sheet receivable/payable and cash-in/cash-out pairs. Only the amount present on both sides is eligible for elimination; unmatched residuals remain explicit exceptions. Cross-currency netting is rejected.

This is an elimination control, not yet a full multi-entity consolidation engine. It does not translate subsidiary trial balances, calculate CTA, consolidate ownership/non-controlling interests, or post elimination journals automatically.

## 6. Bank-to-journal reconciliation

A bank statement carries its account, currency, period, opening and closing balances, and signed statement lines. The reconciliation engine verifies the statement's opening + movements = closing identity, then accepts only explicit allocations between statement lines and posted cash journal lines. It checks account type, currency, direction, over-allocation and period membership. Unmatched statement or journal amounts remain exceptions, and the bank-versus-ledger closing difference is reported.

The engine never guesses matches. It is not yet a complete bank-feed ingestion, payment initiation or multi-bank settlement service.

## 7. Multi-currency trial-balance translation

The initial consolidation translator applies closing rates to assets/liabilities, average rates to revenue/expenses and account-specific historical rates to equity. It calculates a separate currency translation adjustment (CTA) to balance the translated trial balance. FX rates must be explicit, correctly oriented and not dated after the reporting date.

This is a controlled translation primitive, not a full IFRS/GAAP consolidation engine. It does not yet implement historical retained-earnings roll-forward, goodwill, non-controlling interests, hyperinflation, tax effects, hedge accounting or local statutory differences. CTA is not operating profit or cash.

## 8. Typed AR/AP subledger and GL bridge

The SUES trade subledger records receivable/payable documents and partial settlements with typed Money, counterparties, issue/due dates and evidence references. It projects outstanding balances and aging. Its posting bridge creates explicit invoice and settlement journal entries, supports source-keyed FX rates per event, and reconciles the AR/AP control-account delta generated by the batch to the subledger's functional-currency delta.

Credit notes, write-offs, discounts, disputes, ECL provisions, taxes and payment-provider fees require separate explicit workflows and account mappings. They are not inferred from a generic reduction in open balance.

## 9. FIFO inventory subledger

The inventory kernel tracks lot-level remaining quantity and functional-currency cost. Receipts create FIFO lots; issues and write-offs consume oldest lots and return the associated cost with exact lot-allocation provenance; internal location transfers consume source lots and create destination lots preserving cost and source-lot links. Pools are keyed by item and location and reject mixed units. Insufficient stock and duplicate movement/lot IDs are rejected before inventory is mutated.

Receipt postings debit inventory and credit an explicitly selected offset account (for example GRNI); issues/write-offs debit an explicitly selected WIP/COGS/loss account and credit inventory. Internal same-entity location transfers do not create new GL expense or revenue. Inventory costs must already be valued in the entity functional currency; procurement FX valuation must be explicit upstream.

The current kernel does not yet implement full BOM consumption, production output capitalization, standard-cost variances, landed-cost allocation, lot expiry/quality, reservations, serial tracking, lower-of-cost/NRV, or inventory close/revaluation. Those are next-stage extensions.

## 10. Deliberate limitations

This is an in-memory reference kernel, not yet a production ledger. It does not yet implement persistence, concurrent posting locks, account-period close, tax rules, accrual automation, subledger reconciliation, FX revaluation, consolidation, intercompany elimination, authorization/signatures or statutory reporting. It does not hold customer funds or initiate payments.

The journal balances one entity's functional currency. Multi-entity consolidation must translate subsidiary trial balances under a documented FX policy and eliminate matched intercompany balances and transactions.

## 11. Acceptance tests

The tests cover:
- rejection of mixed-currency and mixed-unit arithmetic;
- explicit FX conversion and dated evidence;
- balanced and unbalanced journal entries;
- exact mirrored reversals and forged-reversal rejection;
- physical-flow dimensional separation;
- cross-project benefit attribution capped at 100%;
- reciprocal intercompany P&L, balance-sheet and cash matching;
- bank statement opening/movement/closing and journal cash reconciliation;
- closing/average/historical-rate translation with CTA;
- AR/AP document, partial settlement, FX and GL-control reconciliation;
- FIFO lot valuation, internal transfer cost conservation and inventory-to-GL postings;
- foreign-currency functional valuation;
- idempotency and duplicate prevention;
- single reversal and trial-balance conservation.

Run:

```bash
python -m pytest -q tests/test_synergy_sues.py
```

## 12. Next increments

1. Add chart-of-accounts hierarchy and normal-balance reporting.
2. Add journal-to-AR/AP and bank-statement reconciliation.
3. Add multi-entity consolidation and intercompany eliminations.
4. Add period close, accruals, depreciation and inventory valuation.
5. Add persistence, concurrency, authorization and signed evidence.
