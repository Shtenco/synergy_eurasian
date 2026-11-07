# SYNERGY V6.6.2-B — dated commercial settlement and working-capital replay

**Status:** executable synthetic accounting overlay. It replays invoices and payment timing over the V6.6.2 physical event ledger. It does not yet constrain physical production or shipment decisions.

## 1. Why this layer is separate

Physical production, shipment and sale events are not cash receipts. A cell can deliver goods today, issue an invoice, and receive cash only after the agreed payment term. A customer sale can be accrued while money remains outstanding. V6.6.2-B makes those timing differences explicit without pretending that a cash ledger is already integrated into production planning.

## 2. Invoice classes and timing

| Event | Invoice created | Due date | Cash effect at settlement |
|---|---|---|---|
| Internal shipment | Dispatch day | Local 3 days; cross-region 5 days by default | Buyer pays; seller receives |
| Final customer sale | Sale day | 2 days by default | External customer pays seller |
| Production activity | Production day | 2 days by default | Cell pays external input/operating supplier |

Terms are configurable in days. Default prices and costs are synthetic currency units declared in `src/synergy_v66/settlement.py`. They are not market quotes, actual Kazakhstan/Russia prices, transfer-pricing recommendations or calibrated cost curves.

## 3. Cash and balance reconciliation

For each cell, the replay tracks cash and minimum cash. It also tracks internal invoice receivables/payables, customer receivables and external supplier payables. Internal settlement is a transfer between two cells and must eliminate at consolidated system level.

Consolidated cash identity:

`closing cash = opening cash + external customer collections - external supplier payments`

Internal cash-in and cash-out are separately reported and must net to zero. Outstanding customer receivables reconcile as accrued sales less collections. Outstanding supplier payables reconcile as accrued production costs less payments. Internal receivables and payables must match in aggregate.

`peak_unfunded_working_capital_by_cell` reports the largest amount by which a cell's cash falls below its configured credit limit. The scalar `peak_unfunded_working_capital` is the maximum single-cell requirement, not the sum across all cells. Due payments are processed in a fixed daily order (internal transfers, customer collections, then external supplier payments). Cash minima are sampled at end of day; intraday liquidity and alternative intraday payment ordering are not modeled.

## 4. Important limitation

This is a financial replay, not yet a cash-constrained economy. Negative cash is exposed as an unfunded liquidity requirement; the model does not silently grant a loan, delay an obligation, default on a supplier, or retroactively cancel physical production. The next increment must feed available cash and approved credit limits into production, procurement and shipment authorization, then test default, renegotiation and insolvency rules.

## 5. Reproducible use

```python
from synergy_v66.network import make_environment, simulate
from synergy_v66.settlement import replay_settlement

physical = simulate(make_environment(seed=2026, days=45, regime="severe"))
finance = replay_settlement(
    physical,
    initial_cash_per_cell=200.0,
    customer_terms_days=2,
    supplier_terms_days=2,
    local_terms_days=3,
    cross_border_terms_days=5,
)
print(finance["cash_conservation_error"])
print(finance["peak_unfunded_working_capital_by_cell"])
```

Tests:

```bash
python -m pytest -q tests/test_synergy_v66_settlement.py
```

## 6. Acceptance checks

- Internal settlement cash-in equals cash-out; consolidated internal transfer net is zero.
- Internal AR and AP reconcile.
- Customer AR equals accrued customer sales less collected receipts.
- Supplier AP equals accrued production costs less external supplier payments.
- Cash conservation holds after external flows.
- Payment terms delay collection/settlement; obligations beyond the horizon remain outstanding.
- Negative cash is reported as required working capital rather than hidden by invented credit.

No policy ranking or claims of real-world economic superiority are produced by this overlay.
