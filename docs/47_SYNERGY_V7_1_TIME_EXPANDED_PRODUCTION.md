# SYNERGY V7.1 — Time-Expanded Production and Resource Feasibility

**Status:** deterministic research evaluator; not an optimizer or calibrated enterprise simulator.  
**Date:** 2026-11-06

## Purpose

V7.1 adds a time-expanded production feasibility layer to the V7 event-sourced economic graph. It answers whether a proposed set of production orders can be executed using the material inventory and firm resource capacities available in each discrete period.

It is deliberately a **validator**, not a scheduler optimizer. Orders are processed deterministically by `order_id`; customer demand is processed by ascending integer priority and then `demand_id`. A future solver can search for alternative schedules and use this evaluator as its feasibility oracle.

## Domain objects

- `ProductionRecipe`: output product, output quantity per batch, input material coefficients, resource coefficients and positive integer lead time.
- `ProductionOrder`: recipe, start period and integer batch count.
- `InventoryReceipt`: product quantity and period when it becomes available, with evidence status.
- `ProductDemand`: required product, quantity, due period and priority.
- `ResourceCapacity`: reuses the V7 resource state; period keys are stringified integers such as `"0"`, `"1"`.

## Period execution semantics

For each period (t):

1. Firm external receipts become available.
2. Batches completed at the start of period (t) enter inventory.
3. Production orders starting at (t) are checked in stable order. Each order must have all input materials and firm resource capacity. A blocked order consumes neither inputs nor capacity and creates no output.
4. Demand due at (t) is fulfilled by priority and then demand ID. Unmet demand is a shortfall, not an implicit backorder.
5. Inventory is carried into the next period.

Production lead time must be at least one period. This prevents zero-time circular production. A batch finishing in period (t) is available to orders and demand evaluated later in that same period.

## Hard invariants

- Only `OBSERVED` or `COMMITTED` inventory receipts and resource capacity are firm by default.
- `PLANNED`, `ANNOUNCED`, `UNDER_CONSTRUCTION` and `SCENARIO` receipts are excluded unless scenario inclusion is explicitly enabled.
- Resource capacity is shared across all production orders in the same resource-period bucket.
- Product units must be consistent across recipes, receipts and demand.
- Material shortage, missing resource capacity, unit mismatch, non-firm capacity, capacity overrun and demand shortfall make the plan infeasible.
- A blocked order produces no output.
- This version uses integer batch counts; fractional production is not silently assumed.

## Deliberate limitations

- Deterministic priority is not an economic optimum. The evaluator can block a low-ID order while a different combination could fulfill more valuable demand.
- No inventory expiry, shelf life, lot quality, substitutions, safety stock, yield uncertainty, scrap, work-in-progress, labor calendars, machine setup, transport time, storage capacity or financial working-capital model yet.
- Capacity is represented in discrete buckets; no intra-period scheduling.
- No optimization objective is solved here.
- The evaluator does not establish that source evidence is authentic; it only respects the supplied evidence status and IDs.

The input interchange contract is [`interfaces/synergy_v7_production_plan.schema.json`](../interfaces/synergy_v7_production_plan.schema.json). It describes the recipe, order, receipt, demand and resource-capacity envelope; semantic cross-record checks are performed by the Python evaluator.

## Run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
```

## Next

V7.1.1 should add supplier shipment lead times, inventory lot traceability, safety stock and substitution rules. V7.2 should connect this physical plan to receivables/payables, cash conversion cycle, replacement CAPEX and enterprise cash waterfall. Only after these constraints are explicit should a MILP/CP-SAT optimizer choose order timing and allocation.
