# SYNERGY V7.6 — Cash-Constrained Time-Expanded Production Optimization

**Status:** executable MILP extension of V7.4/V7.4.1; scenario-level cash constraints, not a bank-connected treasury system.  
**Date:** 2026-11-06

## Why V7.6 exists

A production plan can be physically feasible and economically attractive while being impossible to finance at the time inputs and production costs must be paid. Revenue at delivery is not cash at delivery. V7.6 adds a dated cash-balance equation to the time-expanded production MILP.

## Decision variables and constraints

The inherited V7.4 model chooses integer recipe batches, fulfilled demand quantities and end-period inventories. V7.6 adds a non-negative end-period cash variable (C_t) for each period when cash constraints are enabled.

For each period:

`C[t] - C[t-1] + ProductionCashCost[t] + InventoryHoldingCashCost[t] - CustomerCollections[t] = ExternalCashInflows[t]`

For period zero, prior cash is the declared opening balance. Cash must remain above the specified minimum floor. Production batch cost is paid at the start period; inventory holding cost is paid at period end; demand cash is collected only at its modeled collection period.

Customer collection period is:

`collection_period = demand_due_period + collection_lag`

Cash collected per fulfilled unit is:

`unit_value × collection_fraction`

The collection fraction defaults to 1.0 only when the user explicitly enables cash modeling but omits a per-demand override. It is a scenario assumption, not a measured collection ratio. Collections beyond the modeled horizon are reported as deferred and do not finance in-horizon production.

## Inputs

- `cash_opening_balance`: available opening cash, in objective currency.
- `cash_minimum_balance`: one non-negative floor for all periods, or a map of period-specific floors.
- `cash_inflows_by_period`: externally sourced or scenario inflows by zero-based period. Keys in JSON are strings.
- `collection_lag_by_demand`: non-negative integer period lag per demand.
- `collection_fraction_by_demand`: fraction of demand value collected, from 0 to 1.
- Existing `batch_costs` are interpreted as cash paid at the recipe start period. They should include the modeled procurement/production cash outlay relevant to the decision; omitted cash costs are not magically financed.

If all cash inputs are omitted, V7.4 behavior is retained and cash constraints are disabled.

## Example

`examples/synergy_v7_6_cash_constrained_plan.json` demonstrates one factory batch with a $20 production cash cost, $20 opening cash, $100 demand value, one-period production lead time and one-period collection lag after the due period. The expected end cash is $0, $0, $100.

With zero opening cash and no external inflow, the same production decision is blocked: the sale's later collection cannot finance the earlier production outlay.

## Run

```bash
python -m synergy_v7.planner_cli examples/synergy_v7_6_cash_constrained_plan.json
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Accounting and model boundaries

- This is a deterministic cash-feasibility constraint inside an optimizer, not cash reconciliation. Bank statement lines and verified settlements remain in V7.2.2.
- Scenario collection values do not become actual cash. Actuals must be reconciled through the bank/AR/AP evidence chain.
- No automatic credit line, overdraft, factoring, tax, payroll, debt service, FX conversion, supplier deposit, payment terms per input lot, or financing interest is inferred.
- Batch costs are paid at start period; a future extension should split procurement deposits, supplier invoices, payroll, energy and production costs by actual payment calendars.
- Customer collections are tied to fulfilled demand value, not invoice-by-invoice collection evidence.
- Cash flows are single-currency. Multi-currency planning requires dated FX rates and separate currency cash accounts.
- The optimizer's objective remains demand value less modeled batch and holding costs. Cash feasibility does not mean positive profit, solvency, or a positive NPV.
- No financial, legal, credit or payment action is authorized by the optimization output.

## Next development

V7.6.1 should model supplier payment terms and procurement deposits by input requirement, so working capital is consumed before production rather than abstractly at the production start. V7.6.2 should add debt service, credit-line limits and financing cost. V7.7 should optimize production recourse under the V7.5 shock scenarios while preserving minimum cash and essential-service constraints.
