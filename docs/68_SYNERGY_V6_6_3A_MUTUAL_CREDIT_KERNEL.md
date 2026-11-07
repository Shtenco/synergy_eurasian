# SYNERGY V6.6.3-A — mutual-credit and liquidity authorization kernel

**Status:** executable deterministic credit-control kernel; not yet wired into the physical production loop.  
**Model ID:** `SYNERGY_V6.6.3A_MUTUAL_CREDIT_KERNEL`

## 1. Purpose

V6.6.2-B reported liquidity shortfalls after physical events had already occurred. V6.6.3-A introduces a stateful authorization primitive: a cell cannot authorize modeled production costs without cash or an explicitly approved bank line, and it cannot place a supplier order beyond its unused trade-credit limit. The primitive is a foundation for, not a substitute for, full physical integration.

## 2. Cell account state

Each of the 20 cells has:
- cash balance;
- approved bank credit limit and drawn bank debt;
- trade-credit limit and outstanding trade payables;
- trade receivables from other cells;
- customer receivables;
- default/freeze status.

Cash is never allowed to become negative. A bank draw is recorded explicitly and cannot exceed the cell's approved undrawn limit. There is no implicit overdraft.

## 3. Authorization rules

### Production
`authorize_production(cell, variable_cost, day)` authorizes only if the cell is not in default and cash plus undrawn approved bank credit covers the modeled variable cost. The cost is charged before output authorization. Rejection leaves cash and external payments unchanged.

### Supplier purchase
`authorize_purchase(buyer, seller, amount, due_day, day, invoice_id)` authorizes only if:
- buyer and (if internal) seller are known cells;
- amount is positive and due date is not earlier than issue date;
- invoice ID is unique;
- buyer is not defaulted;
- buyer's existing trade payables plus the new invoice do not exceed the buyer's trade-credit limit.

Internal purchases create matching buyer AP and seller AR. An external supplier is represented by `seller=None`.

### Settlement and default
At each `process_day(day)`, due customer invoices are collected first, followed by payable invoices in stable due-date / invoice-ID order. A payable is settled only if cash plus unused approved bank credit covers the full remaining amount. Otherwise it remains outstanding; after the configured grace period the buyer defaults and is frozen from new production authorization and purchases.

Partial settlement, interest, collateral, guarantees, legal recovery, priority classes, supplier-side contagion and bank-credit repayment are intentionally not yet modeled.

## 4. Accounting invariants

Consolidated cash must satisfy:

`closing cash = opening cash + bank draws + customer collections - external supplier payments`

Internal transfers are cash outflow for the buyer and equal cash inflow for the seller, so their system-level net is zero. Bank debt never exceeds the approved bank limit. Trade payables and receivables update symmetrically for internal invoices. The ledger exposes every authorization, draw, invoice, payment and default as an event.

## 5. Usage

```python
from synergy_v66.credit import CreditLedger

ledger = CreditLedger(
    initial_cash_per_cell=200.0,
    bank_limit_per_cell=50.0,
    trade_credit_limit_per_cell=100.0,
    grace_days=2,
)
order = ledger.authorize_purchase(
    buyer="WEST-PR1", seller="WEST-AG1",
    amount=30.0, due_day=3, day=0, invoice_id="PO-0001",
)
production = ledger.authorize_production("WEST-PR1", variable_cost=12.0, day=0)
ledger.process_day(3)
report = ledger.snapshot()
```

Tests:

```bash
python -m pytest -q tests/test_synergy_v66_credit.py
```

## 6. Boundary of this increment

The credit kernel is not yet called by `network.simulate`. Thus it does not yet change simulated production quantities, procurement dispatch, inventory, delivery or unmet demand. No claim that V6.6.3 is already a fully integrated cash-constrained economy is made.

Next: integrate authorization at the point of each production batch and supplier dispatch, ensuring denied operations do not consume inputs, create shipments or generate output. Then add partial payments, credit repayment, arrears restructuring and multi-cell default propagation.
