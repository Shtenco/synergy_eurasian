# SYNERGY V7.6.2 — Revolving Credit Facility in Cash-Constrained Production Planning

**Status:** deterministic facility draw, repayment and interest constraints inside the V7.6 MILP.  
**Date:** 2026-11-06

## Purpose

V7.6.2 distinguishes operating cash from borrowing capacity. A facility can bridge the timing gap between production outlays and later customer collections, but borrowing creates a debt balance, interest expense and repayment obligations. The optimizer now models those mechanics explicitly rather than treating a credit line as free cash.

## Facility variables

For each period (t), the MILP may choose:
- credit draw (D_t);
- repayment (R_t);
- ending facility balance (B_t).

Debt conservation:

`B[t] = B[t-1] + D[t] - R[t]`

At period zero, prior balance is the declared opening facility balance. The ending balance cannot exceed the facility limit. Draws and repayments can also have period-specific caps. Repayment is constrained by debt outstanding at the **start** of the period; a draw cannot be immediately repaid in the same period.

## Interest and cash

Interest is charged on the opening balance for period zero and on the previous period's ending balance thereafter:

`Interest[t] = PriorPeriodDebt[t] × InterestRate[t]`

Cash conservation now includes borrowing and financing:

`Ending cash = Prior cash + external inflows + customer collections + credit draws - production costs - holding costs - committed outflows - repayments - interest`

Interest is included in the optimization objective as a financing cost. Principal repayment is a cash outflow and reduces debt, but is not an expense in the operating objective.

## Inputs

- `credit_limit`: total facility limit; setting it enables the credit model.
- `credit_opening_balance`: opening drawn balance, default 0.
- `credit_draw_limits_by_period`: maximum new draw by period; defaults to facility limit.
- `credit_repayment_limits_by_period`: maximum repayment by period; defaults to facility limit.
- `credit_interest_rates_by_period`: per-period decimal interest rate. For example, 0.10 means 10% for that modeled period, not automatically an annual rate.
- `terminal_credit_balance_limit`: optional maximum debt at the end of the final period. Set to zero to require full repayment by the horizon end.

All maps use zero-based period indices. In JSON, keys are strings and the CLI converts them to integer period indices.

## Demonstration

`examples/synergy_v7_6_2_credit_factory_plan.json` models a $20 production outlay, $20 revolving facility, $100 customer demand and a one-period collection lag after delivery. The facility draws $20 in period zero; the model applies 10% interest to the debt in period two, when customer cash arrives. The illustrative interest is $2. The fixture explicitly sets a zero terminal debt limit, so the $20 principal is repaid in period two and ending cash is $78. Without that terminal limit, repayment is not required by the model.

This is a timing demonstration, not a recommendation to borrow or a real facility offer.

## Controls and limitations

- Credit limit, opening debt, per-period draw/repayment caps and interest rates are validated.
- Repayment cannot exceed prior-period outstanding debt.
- Debt and cash are modeled in the single objective currency; FX, fees, collateral, covenants, default, guarantees and lender discretion are not represented.
- No terminal debt repayment is forced unless `terminal_credit_balance_limit` is supplied. The optional limit constrains ending debt in the final period; an external treasury policy must set maturity/repayment requirements.
- Interest is a simple period rate on beginning-period debt; compounding conventions and day-count calendars are not modeled.
- The model is not a loan underwriting decision or legal credit approval.
- Actual facility drawdowns and repayments must be reconciled to bank statements; optimizer choices are not cash actuals.

## Run

```bash
python -m synergy_v7.planner_cli examples/synergy_v7_6_2_credit_factory_plan.json
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Next

V7.6.3 should add facility maturity, terminal debt limits, minimum repayment schedules, fees and covenant headroom. V7.7 should optimize adaptive recourse under V7.5 shocks while keeping both cash and facility constraints active.
