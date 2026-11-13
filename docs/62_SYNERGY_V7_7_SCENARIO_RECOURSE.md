# SYNERGY V7.7 — Scenario-Wise Adaptive Recourse and Mean-CVaR Evaluation

**Status:** implemented as an independent scenario re-optimization evaluator.  
**Date:** 2026-11-06

## Why this version exists

A production plan that is feasible under average conditions may fail when demand, supplier deliveries, resource availability, collections or collateral deteriorate together. V7.7 evaluates a declared set of such shocks and re-optimizes the production/finance plan separately after each scenario is revealed.

## Scenario dimensions

A scenario can scale:
- resource capacity by resource ID or resource-and-period key;
- customer demand by demand ID;
- inventory receipts by receipt ID;
- period cash inflows and outflows;
- supplier payment commitments by payment ID;
- receivable collateral by receivable ID;
- inventory collateral by lot ID;
- externally supplied period borrowing-base ceilings.

Multipliers must be finite and non-negative. Unknown IDs for entity-level shocks are rejected. If a borrowing-base multiplier is supplied without an explicit period ceiling, the contractual facility limit is used as the starting ceiling; the shock therefore cannot silently create a zero or unlimited facility. Scenario probabilities must sum to 1.0 within a strict tolerance.

## Re-optimization and reporting

The engine first solves the baseline plan, then applies each scenario's shocks to a deep copy of the input and invokes the existing cash-, credit- and collateral-aware MILP optimizer.

For each scenario it reports:
- a SHA-256 fingerprint of the transformed scenario input and the canonical baseline input fingerprint;
- the full scenario shock specification;
- probability, feasibility and optimality status;
- objective value and change from baseline;
- loss versus baseline;
- served value and unserved demand value;
- production, holding and interest costs;
- demand-level service detail, resource usage and collateral borrowing-base detail;
- production schedule, ending cash and ending debt.

The loss metric is `max(0, baseline_objective - scenario_objective)`. Gains in favorable scenarios do not offset downside losses in the risk measure.

## Mean-CVaR risk

For scenario losses (L_s) with probabilities (p_s), expected loss is:

`E[L] = sum_s p_s L_s`

The discrete CVaR at confidence level `alpha` is calculated using the Rockafellar-Uryasev representation:

`CVaR_alpha(L) = min_eta { eta + (1/(1-alpha)) * sum_s p_s * max(L_s-eta,0) }`

The combined risk score is:

`MeanCVaR = (1-risk_weight)*E[L] + risk_weight*CVaR_alpha(L)`

This is a risk report, not a new objective optimized by the production MILP. The scenario set must be calibrated; probabilities are user-supplied assumptions, not empirically inferred failure rates.

## Critical modeling boundary: not yet a non-anticipative stochastic MILP

V7.7 independently re-optimizes after each scenario is known. It therefore provides a **wait-and-see recourse benchmark**, not a deployable policy selected before uncertainty is observed.

It does not enforce common first-stage decisions across scenarios (non-anticipativity), and it does not optimize the mean-CVaR score across all scenarios in one joint MILP. Its expected scenario objective can overstate what an implementable policy could achieve.

The evaluator marks these limitations explicitly:
- `non_anticipativity_enforced = false`;
- `formal_two_stage_stochastic_milp = false`.

If any scenario is infeasible or fails to prove optimality, the scenario set is marked incomplete and aggregate risk metrics are withheld. The system does not silently replace infeasibility with an arbitrary penalty.

## Run

```bash
python -m synergy_v7.scenario_recourse_cli examples/synergy_v7_7_scenario_recourse.json
python -m pytest -q tests/test_synergy_v7_kernel.py
```

Input schema: `interfaces/synergy_v7_scenario_recourse.schema.json`. The base plan is separately validated against the production optimizer schema.

## Research basis

The architecture follows the established two-stage stochastic programming distinction between decisions made before uncertainty is revealed and scenario-dependent recourse decisions made afterward. A formal next step must introduce shared first-stage variables and non-anticipativity constraints, then formulate expected recourse and CVaR in a joint deterministic equivalent or an appropriate decomposition algorithm. See the INFORMS tutorial on two-stage stochastic mixed-integer programming and the PyPSA stochastic optimization documentation for the discrete CVaR linearization.

## Next: V7.8

V7.8 should implement a true two-stage scenario model:
1. common here-and-now production commitments, capacity reservations and financing decisions;
2. scenario-specific recourse decisions after shocks;
3. non-anticipativity constraints linking all scenarios before the reveal time;
4. expected cost and CVaR objective in the same optimization model;
5. explicit emergency procurement, overtime, substitution, backlog, lost sales and service penalties;
6. solver gap, bounds, scenario provenance and computational-size reporting.

Only after that can the model compare an implementable risk-aware policy against the wait-and-see benchmark.
