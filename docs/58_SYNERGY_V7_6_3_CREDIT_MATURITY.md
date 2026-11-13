# SYNERGY V7.6.3 — Explicit Revolving-Facility Maturity

**Status:** implemented as an optional hard constraint in the V7.6.2 cash/credit MILP.  
**Date:** 2026-11-06

## Why this extension matters

A terminal debt cap only constrains the balance at the end of the planning horizon. It does not say when a facility contractually matures. If debt is due in period 2, a plan that leaves it outstanding until period 5 is not financeable even if the terminal balance eventually reaches zero.

V7.6.3 adds an explicit zero-based `credit_maturity_period`.

## Mathematical rule

For maturity period (m), debt must be zero at the end of period (m) and remain zero thereafter:

`B[t] = 0 for all t >= m`

The existing debt conservation remains:

`B[t] = B[t-1] + Draw[t] - Repayment[t]`

Repayments remain limited by debt outstanding at the beginning of the period. A draw made during a period cannot be repaid in that same period. Therefore, if the facility matures in period (m), the model must have enough opening cash, customer collections already received, external inflows, or other permitted funding to repay debt by that period.

## Input

- `credit_maturity_period`: integer period index in `[0, horizon_periods - 1]`.
- It is valid only when `credit_limit` enables the credit facility.
- When omitted, no maturity is inferred. The optional `terminal_credit_balance_limit` continues to operate independently.

## Tests

The tests cover:
1. repayment by a declared maturity date using an external cash inflow;
2. production curtailment when a proposed draw cannot be repaid by maturity;
3. invalid maturity periods and CLI/schema integration.

## Accounting boundary

Maturity is a planning constraint supplied by the user or contract data. The model does not inspect or interpret a loan agreement, infer a lender's grace period, or authorize refinancing. Actual debt balances and payments must be reconciled to bank evidence. No lender commitment, legal approval, covenant compliance, or solvency conclusion is implied.

## Run

```bash
python -m synergy_v7.planner_cli examples/synergy_v7_6_2_credit_factory_plan.json
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Next

V7.6.4 should add dated facility fees and covenant headroom (borrowing-base constraints, eligible receivables/inventory, and minimum liquidity covenants). V7.7 should combine this financing layer with scenario-specific adaptive production recourse, while explicitly modeling the cost of emergency procurement and service shortfalls.
