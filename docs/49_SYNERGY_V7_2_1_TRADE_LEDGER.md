# SYNERGY V7.2.1 — Invoice, Settlement and Counterparty Exposure Ledger

**Status:** deterministic management-control ledger; not statutory bookkeeping, a credit rating, or an audited loss allowance.  
**Date:** 2026-11-06

## Purpose

The working-capital snapshot and cash waterfall in V7.2 need invoice-level evidence. V7.2.1 introduces a dated subledger projection for receivables (AR), payables (AP), partial settlements, credit adjustments, disputes, aging and counterparty concentration.

## Records

- `TradeDocument`: receivable or payable, enterprise, counterparty, issue/due dates, currency, original amount and source reference.
- `SettlementEvent`: dated partial or full cash settlement, cash account, currency and source.
- `DocumentAdjustment`: dated credit adjustment that reduces the open document balance; use only for documented credit notes or approved adjustments.
- `DisputeEvent`: OPEN or RESOLVE event that classifies a portion of the still-open balance as disputed. A dispute is not an extra asset/liability.
- `CreditRiskAssessment`: dated counterparty PD and LGD assumptions, explicitly sourced.

## Replay semantics

All settlements, adjustments and dispute events are replayed in chronological order, with event ID as a deterministic tie-breaker. Future events are ignored at the selected `as_of` date. Settlements and adjustments cannot exceed the open balance at the point of replay. Dispute opening cannot exceed open balance; resolution cannot exceed the disputed balance.

Balances are maintained separately by document, enterprise, counterparty, side and currency. AR and AP are **not netted** merely because the same counterparty appears on both sides. Cross-border or multi-currency exposure is not converted without an explicit FX source and valuation date.

## Aging and exposure

Open balances are assigned to:
- `NOT_DUE`;
- `DUE_1_30`;
- `DUE_31_60`;
- `DUE_61_90`;
- `DUE_90_PLUS`.

The output reports gross outstanding, disputed and undisputed portions, overdue exposure, aging buckets and counterparty totals. For receivables only, if a dated assessment exists, an illustrative expected credit loss is calculated:

`ECL = Outstanding AR × PD × LGD`

This is a simple exposure estimate, not an IFRS 9 allowance, cash outflow, legal claim valuation or guarantee of recovery. It omits probability-weighted forward-looking scenarios, discounting, collateral, guarantees, cure rates and staging rules. No PD/LGD is inferred if absent.

## Controls and limitations

- Every document, settlement, adjustment, dispute and assessment has an explicit source reference.
- Currency mismatches, unknown documents, duplicate IDs, over-settlement, invalid dispute transitions and conflicting same-day risk assessments are rejected.
- Events after `as_of` do not change the projection.
- This module is an in-memory projection; it is not yet a durable append-only database and does not replace double-entry accounting.
- Tax, FX, interest, factoring, write-offs, insolvency ranking, invoice ageing disputes and payment allocation across multiple documents are not modeled.
- Legal set-off rights are not assumed. Netting requires contract/legal validation and an explicit later module.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Next

V7.2.2 should add explicit cash-account transaction reconciliation and invoice allocation rules. V7.3 should join invoice-level realized collections with production orders, customer contracts and causal benefit evidence without counting internal transfers or financing as operating output.
