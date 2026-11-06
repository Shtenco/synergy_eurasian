# SYNERGY V7.4 — Time-Expanded MILP Production Scheduler

**Status:** mixed-integer linear optimization prototype; not an enterprise ERP, calibrated production plan or investment authorization.  
**Date:** 2026-11-06

## Purpose

V7.1 validates a fixed production schedule. V7.4 adds a solver that chooses integer production batches across a discrete planning horizon to maximize:

`demand value − batch production cost − inventory holding cost`

The model uses SciPy's MILP interface (HiGHS backend). Inventory conservation couples periods; resource constraints are shared across recipes; lead times determine when output becomes available.

## Decision variables

- Integer batch count for each recipe and eligible start period.
- End-of-period inventory for each product.
- Fulfilled quantity for each customer demand.

## Constraints

- Material inventory balance at every product-period.
- Shared firm resource capacity for every resource-period.
- Positive recipe lead time; output is available only after completion.
- Integer batch limits supplied explicitly for every recipe.
- Demand due dates must lie inside the horizon.
- Product units and objective currency must be consistent.
- Only OBSERVED/COMMITTED inventory receipts and resource capacities are firm by default. Missing/non-firm resource capacity blocks the affected recipe-period decision.

## Objective interpretation

Demand `unit_value × priority_weight`, batch costs and holding costs must all use the declared objective currency and consistent time horizon. These are scenario/economic inputs, not automatically recognized revenue or collected cash. The optimizer does not include taxes, financing, working capital, quality, spoilage, labor shifts, machine setup, transport, storage capacity, emissions, or risk aversion yet.

The objective is single-horizon and deterministic. It is not NPV unless the caller has explicitly converted all inputs to a consistent discounted basis. The optimizer reports an optimality flag and MIP gap; a feasible incumbent at time limit is not represented as proven optimal.

## Reproducible integrated factory example

The demonstration schedules one steel-smelting batch and three machine-part batches:
- 100 kg ore received in period 0;
- 80 kg steel produced after one period;
- 60 kg steel and 30 MWh electricity consumed by machining in period 1;
- 12 machine parts available for customer demand in period 2.

The example's values are illustrative only. The objective is a modeled value less batch and holding costs, not observed cash.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
python -m synergy_v7.planner_cli examples/synergy_v7_4_milp_factory_plan.json
```

## Deliberate limitations and next steps

- Deterministic recipe yields; no scrap, yield uncertainty, maintenance or breakdown.
- No inventory lot traceability, shelf life, safety stock, supplier shipment lead times, substitution or transport network.
- No cash constraints or credit terms in the MILP.
- No stochastic or robust optimization and no CVaR constraint yet.
- No multi-objective Pareto set; current objective is a weighted scalar.

V7.4.1 should add safety stock, supplier lead times, storage limits and production availability. V7.5 should add scenario-based disruptions, chance constraints and a Pareto frontier across value, output, cost, resilience and essential demand fulfillment.
