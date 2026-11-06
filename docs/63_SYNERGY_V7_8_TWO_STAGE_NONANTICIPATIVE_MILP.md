# SYNERGY V7.8 — Two-Stage Non-Anticipative Mean-CVaR MILP

**Status:** implemented and tested as a deliberately narrow single-product, one-epoch prototype.  
**Date:** 2026-11-06

## What changes from V7.7

V7.7 solved every scenario independently after the shock was known. That is a wait-and-see benchmark and does not constrain decisions made before uncertainty is revealed.

V7.8 introduces a joint mixed-integer optimization with:
- one shared first-stage commitment quantity (x);
- scenario-specific internal production (p_s);
- scenario-specific emergency procurement (e_s);
- scenario-specific lost sales (u_s);
- common first-stage cost;
- expected recourse cost and a discrete CVaR tail-risk term.

The same (x) appears in every scenario. This is the non-anticipativity condition for the first-stage decision in this prototype.

## Mathematical formulation

For each scenario (s), with probability (pi_s), demand (D_s) and realized capacity (A_s):

`min x*c_pre + (1-lambda)*sum_s pi_s*C_s + lambda*CVaR_alpha(C)`

subject to:

`0 <= x <= PrecommitCapacity`

`0 <= p_s <= x`

`p_s <= A_s`

`p_s + e_s + u_s = D_s`

`C_s = c_prod*p_s + c_emergency*e_s + c_lost*u_s`

All quantities (x,p_s,e_s,u_s) are non-negative integers. The scenario probabilities must sum to one.

CVaR is linearized using a free threshold (eta) and non-negative excess variables (z_s):

`z_s >= C_s - eta`

`CVaR_alpha = eta + sum_s pi_s*z_s/(1-alpha)`

The risk weight `lambda` blends expected recourse cost and CVaR. The common first-stage commitment cost is added outside the recourse risk measure.

## Reference experiment

Input: `examples/synergy_v7_8_two_stage_milp.json`.

- Precommitment capacity: 100 units.
- Precommitment cost: 2 per unit.
- Internal production cost: 1 per unit.
- Emergency procurement cost: 5 per unit.
- Lost-sales penalty: 20 per unit.
- Normal scenario: probability 0.8, demand 100, capacity 100.
- Capacity shock: probability 0.2, demand 100, capacity 40.
- CVaR confidence: 95%; risk weight: 50%.

Expected reference behavior:
- risk-neutral common commitment: 100 units, objective 348;
- risk-aware common commitment: 40 units, mean-CVaR objective 420;
- risk-aware scenario recourse: 40 internal + 60 emergency units in each scenario;
- wait-and-see expected cost: 324;
- expected value of perfect information: 24.

This example demonstrates the trade-off: a risk-neutral policy commits more capacity to exploit the high-probability normal state, while the mean-CVaR policy is more conservative about the severe capacity shock.

## Value of perfect information

The model separately solves each scenario with a scenario-specific commitment to compute a wait-and-see benchmark. This is not an implementable policy because it chooses the commitment after learning the scenario.

`EVPI = RiskNeutralStochasticOptimum - ExpectedWaitAndSeeCost`

The reported EVPI is a lower-bound information-value comparison under this small model and its declared assumptions, not a forecast of real-world savings.

## Run

```bash
python -m synergy_v7.two_stage_optimizer_cli examples/synergy_v7_8_two_stage_milp.json
python -m pytest -q tests/test_synergy_v7_kernel.py
```

Input schema: `interfaces/synergy_v7_8_two_stage_optimizer.schema.json`.

## Scope boundary

V7.8 is a formal two-stage non-anticipative MILP for a single product and one planning epoch. It is **not yet** the full SYNERGY recipe-network optimizer. It does not yet include:
- multiple products, recipes, bills of material or production lead times;
- multi-period inventory balance and storage;
- supplier payment calendars and working capital;
- cash balance, credit facilities, collateral and maturity;
- substitution, overtime, backlogs and service-level constraints;
- shared first-stage financing and capacity reservation across the existing V7.6 planner.

The model must not be described as an integrated stochastic optimization of the full economy until those constraints are brought into the same joint formulation.

## Next: V7.8.1

1. Generalize from one product to multiple products and recipe arcs.
2. Add multi-period inventory and resource-capacity balances.
3. Add common first-stage supplier commitments and capacity reservations.
4. Add scenario-specific emergency procurement, substitution, overtime, backlog and lost sales.
5. Add cash, credit, maturity and collateral constraints in every scenario.
6. Enforce non-anticipativity for every decision made before each scenario reveal time.
7. Add scenario provenance, stress calibration, bounds, solver gaps and decomposition when the extensive form becomes too large.

V7.7 remains useful as a wait-and-see comparison; V7.8 is the first actual joint non-anticipative stochastic MILP prototype.
