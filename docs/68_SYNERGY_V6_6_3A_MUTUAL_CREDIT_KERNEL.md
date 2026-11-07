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

Cash is never allowed to become negative. A bank draw is recorded explicitly and cannot exceed the cell's approved undrawn limit. A cell may repay drawn bank credit only from available cash; repayment reduces both cash and bank debt and is included in the consolidated cash identity. There is no implicit overdraft.

## 3. Authorization rules

### Production
`authorize_production(cell, variable_cost, day)` authorizes only if the cell is not in default and cash plus undrawn approved bank credit covers the modeled variable cost. The cost is charged before output authorization. Rejection leaves cash and external payments unchanged.

### Supplier purchase
`authorize_purchase(buyer, seller, amount, due_day, day, invoice_id)` applies a cash-first funding waterfall. Available cash is paid immediately; the uncovered remainder may be carried as trade credit if it fits the buyer's unused limit. If the remainder exceeds trade-credit capacity, an approved bank line may fund the full purchase for immediate payment. The request is rejected without spending any cash if neither path can fund it. Buyer and (if internal) seller must be known cells, the amount must be finite and positive, the due date cannot precede issue, the invoice ID must be unique, and neither party may be defaulted. Internal trade-credit balances create matching buyer AP and seller AR; cash-funded portions settle immediately. An external supplier is represented by `seller=None`.

### Settlement and default
At each `process_day(day)`, due customer invoices are collected first, followed by payable invoices in stable due-date / invoice-ID order. A payable is settled only if cash plus unused approved bank credit covers the full remaining amount. Otherwise it remains outstanding; after the configured grace period the buyer defaults and is frozen from new production authorization and purchases.

Interest, collateral, guarantees, legal recovery, priority classes, supplier-side contagion and automatic debt-service sweeps are intentionally not yet modeled. V6.6.3-C adds partial payable settlement and seller-side receivable exposure limits on top of this kernel. Manual bank principal repayment is supported.

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

## 6. Relationship to V6.6.3-B

This document specifies the standalone kernel introduced in V6.6.3-A. The subsequent V6.6.3-B increment integrates it into `network.simulate` when a `credit_config` is supplied. Production authorization now occurs before recipe inputs are consumed or output is created; procurement authorization occurs before supplier stock is consumed or a shipment is created. Omitting `credit_config` preserves the unconstrained V6.6.2 baseline. See [V6.6.3-B integration specification](69_SYNERGY_V6_6_3B_CASH_CONSTRAINED_PHYSICAL_NETWORK.md).

The kernel remains a research primitive rather than a complete credit institution. Partial payments, interest, collateral, guarantees, legal recovery, automatic debt-service sweeps and multi-cell default contagion remain future increments.
