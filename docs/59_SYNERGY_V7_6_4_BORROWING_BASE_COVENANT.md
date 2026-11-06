# SYNERGY V7.6.4 — Period Borrowing-Base Covenant

**Status:** implemented as a period-specific hard limit on ending drawn credit.  
**Date:** 2026-11-06

## Purpose

A revolving facility's contractual limit is not always the amount that can actually be borrowed. Asset-based facilities may restrict availability to a borrowing base derived from eligible receivables, inventory, reserves and advance rates. V7.6.4 adds a period-specific maximum debt balance so a plan can model that constraint explicitly.

## Model

For each period (t):

`EndingDebt[t] <= BorrowingBase[t]`

The existing contractual facility limit remains a separate ceiling:

`EndingDebt[t] <= CreditLimit`

The effective maximum is therefore the lower of the contractual facility limit and the supplied borrowing base. The optimizer reports remaining borrowing-base headroom:

`Headroom[t] = BorrowingBase[t] - EndingDebt[t]`

If no borrowing-base value is supplied for a period, the contractual facility limit is used for reporting and no tighter borrowing-base constraint is applied in that period.

## Input

`credit_borrowing_base_by_period` is a map of zero-based period index to maximum permitted ending drawn balance, in the objective currency. Each value must be non-negative and no greater than `credit_limit`.

The borrowing-base values are external inputs. They may be computed upstream from eligible receivables, eligible inventory, contractual advance rates, concentration caps, aging exclusions and reserves. V7.6.4 does not independently certify collateral eligibility or calculate an audited borrowing base.

## Controls

- Contractual facility limit and period borrowing base are independent constraints.
- The maturity and terminal debt caps continue to apply.
- If collateral availability contracts, the optimizer may need to repay debt or curtail production.
- Headroom is reported period by period.
- Missing borrowing-base inputs do not mean the collateral is unlimited; they mean no additional borrowing-base restriction was supplied.

## Tests and run

```bash
python -m synergy_v7.planner_cli examples/synergy_v7_6_2_credit_factory_plan.json
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Boundaries

This is a planning control, not a lender's borrowing-base certificate, valuation, collateral audit or covenant compliance opinion. Eligible assets, reserves and advance rates must come from approved and independently verified source data. Actual drawdowns and repayments remain subject to bank reconciliation and authorized approvals.

## Next

V7.6.5 should calculate a transparent borrowing-base bridge from eligible receivables and inventory, including aging, dilution, concentration, reserves and advance rates. V7.7 should then add scenario-specific adaptive production recourse and quantify the cost of emergency procurement, lost service and liquidity stress.
