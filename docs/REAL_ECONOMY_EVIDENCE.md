# Real-Economy Evidence Boundary

The Eurasian layer distinguishes modeled demand from observed production and externally settled value.

## Evidence classes

- `SCENARIO` — counterfactual or planning assumption;
- `MODEL_ESTIMATE` — calibrated estimate not directly observed;
- `OBSERVED_OPERATIONAL` — physical/operational evidence such as inventory, production or delivery;
- `EXTERNALLY_SETTLED` — independently settled financial flow;
- `AUDITED` — externally reviewed/reconciled evidence.

## Goods observability

Useful records include orders, delivered quantities, returns, warehouse stock, manufacturer/origin evidence, customs declarations, invoices, settlement currency, fiscal receipts and payment confirmations.

A domestic sales channel does not prove domestic origin. Imported inventory can increase goods availability while simultaneously creating FX and replenishment dependencies.

## Revenue recognition handoff

This repository may assert that an externally settled event occurred only when evidence is linked to an immutable/referenceable settlement record. The canonical financial ledger remains responsible for recognizing the accounting entry.

```text
operational event
 -> evidence
 -> settlement/reconciliation
 -> SettlementReceipt / external reference
 -> canonical balanced journal
 -> FinancialSnapshot
```

## Conditional authorization

A project authorization limit is not a hard asset, circulating money or realized revenue. Release should be bounded by verified milestones and the canonical financial constitution.

## Stress evidence

Negative scenarios are preserved. If a project or bank becomes unprofitable under stress, the model must expose that result rather than repair it by assuming additional issuance or undisclosed external support.
