# SYNERGY V7.5 — Monte Carlo Production Resilience Stress

**Status:** fixed-schedule conditional Monte Carlo stress evaluator; not calibrated failure forecasting or a CVaR-constrained optimizer.  
**Date:** 2026-11-06

## Purpose

A deterministic MILP optimum can be fragile when electricity, water, logistics or suppliers fail. V7.5 takes a fixed V7.1 schedule and replays it under supplied resource-capacity shocks and supplier receipt delays.

## Scenario mechanisms

- Common shock: with a specified probability, every resource capacity is multiplied by a common factor.
- Resource-specific shock: each configured resource independently receives a capacity factor with its configured probability.
- Receipt delay: each configured firm inventory receipt can be delayed by a random integer number of periods.

A single fixed schedule is replayed in every scenario. No rescheduling, overtime, substitution or emergency procurement recourse is optimized.

## Metrics

- Mean weighted demand service level.
- p05 / p50 / p95 service-level quantiles.
- Probability of complete demand service.
- Mean service shortfall and empirical upper-tail CVaR of service shortfall.
- Per-demand average service and shock/delay occurrence counts.

Demand weights are explicit scenario inputs; if omitted, each demand line receives equal weight. Different physical units are never summed directly: each demand is normalized by its own requested quantity before aggregation.

## Interpretation boundaries

- Shock probabilities and severity factors are assumptions, not inferred frequencies.
- Monte Carlo frequencies are conditional on the supplied schedule, horizon, data and shock model.
- The engine does not optimize recourse or establish formal chance constraints.
- Empirical CVaR is descriptive; no CVaR constraint is enforced in the MILP.
- A 100% service level in a small scenario sample does not prove resilience.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
python -m synergy_v7.stress_cli examples/synergy_v7_5_stress_test_demo.json
```

## Next

V7.5.1 should add recourse actions (rescheduling, supplier substitution, reserve release and overtime) with explicit costs and lead times. V7.6 should optimize a multi-scenario policy with formal chance/CVaR constraints and out-of-sample stress validation.
