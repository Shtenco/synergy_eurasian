# SYNERGY V6.6.2 — 20-cell, two-region inventory network

**Status:** executable synthetic research kernel; physical submodel only.  
**Model ID:** `SYNERGY_V6.6.2_20_CELL_INVENTORY_NETWORK`  
**Scope:** 20 cells, 2 synthetic regions, 3 production sectors, multi-stage recipes, lot inventory, delivery lead times, shared regional storage and transport constraints.

This increment replaces the seven-cell make-to-order simplification with a stock-and-flow network. It exposes physical bottlenecks before contracts, working-capital finance, delayed settlement and governance are added. It is not calibrated to observed EAEU enterprise data and is not a forecast.

## 1. Network topology

Each synthetic region (`WEST`, `EAST`) contains ten cells:

| Cell suffix | Role | Core sector / function |
|---|---|---|
| `AG1` | Grain farm | Primary production |
| `AG2` | Oilseed farm | Primary production |
| `PR1` | Flour mill | Processing |
| `PR2` | Oil press | Processing |
| `MF1` | Bakery | Manufacturing |
| `MF2` | Packaged-food factory | Manufacturing |
| `WH` | Shared regional storage pool | Support constraint |
| `LG` | Logistics | Support capacity |
| `EN` | Energy supply | Support supply |
| `SV` | Maintenance service | Support cell; behavior not yet modeled |

The three production sectors are exactly `primary`, `processing` and `manufacturing`. Support cells are counted in the 20-cell topology, not as production sectors.

The two regions can source grain, oilseed, flour and oil across the regional boundary. Local routes have a one-day minimum lead time; cross-region routes have a two-day minimum. Severe-regime route extensions may add one day. Energy replenishment has a one-day lead time. Destination-region logistics capacity is charged for shipments; explicit corridor capacity and origin/destination dual-sided transport accounting remain future work.

## 2. Production recipes

| Cell role | Output | Inputs per output unit |
|---|---|---|
| Flour mill | `flour` | 1.25 `grain` + 0.04 `energy` |
| Oil press | `oil` | 1.15 `oilseed` + 0.05 `energy` |
| Bakery | `bread` | 0.92 `flour` + 0.08 `energy` |
| Food factory | `packed_food` | 0.55 `flour` + 0.22 `oil` + 0.10 `energy` |

Recipe coefficients and capacities are synthetic initial parameters, not engineering norms or national industry averages.

## 3. Daily event order

1. Receive shipments with `arrival_day <= current_day`.
2. Expire lots whose expiry date is earlier than the current day.
3. Generate primary harvest and energy supply, then run production against currently available stock.
4. Dispatch replenishment and energy shipments subject to source stock, reorder targets, lead times, warehouse headroom and daily logistics capacity.
5. Serve current-day final demand from finished-goods inventory. Unmet demand is not backfilled from future days.
6. Record the daily ledger and peak storage / transport utilization.

A shipment dispatched today cannot be received today. Newly arrived inputs can only be consumed in a subsequent production phase. A prefix-invariance test verifies that appending future exogenous days does not change the earlier daily ledger.

## 4. Inventory and physical accounting

Inventory is represented as lots with `lot_id`, `sku`, quantity, birth day, expiry day and source. Consumption uses earliest-expiry-first ordering, then birth day and stable lot ID. A shipment carries the earliest expiry among consumed source lots, conservatively avoiding an artificial shelf-life reset in transit.

The shared regional warehouse capacity is an aggregate ceiling over all on-hand regional lots plus shipments in transit to that region. It is a capacity abstraction, not a claim that every lot physically passes through the `WH` cell. The synthetic regional storage ceiling is 450 quantity units; regional logistics capacity is 30 transport units per day multiplied by that day's exogenous capacity factor.

For every SKU:

`initial stock + produced = consumed in recipes + sold + expired + closing stock + in-transit stock`

Internal deliveries are transfers between cells, not new production or system-level consumption. The implementation reports the residual per SKU and in aggregate.

## 5. Reproducibility and commands

`make_environment(seed, days, regime)` creates deterministic regional demand, cell capacity factors and route lead times. Regimes are `normal`, `volatile` and `severe`. The canonical environment is hashed with SHA-256.

```python
from synergy_v66.network import run

report = run(seed=2026, days=45, regime="severe")
result = report["result"]
print(result["physical_balance_error_by_sku"])
print(result["unmet_demand_by_sku"])
```

Run tests from the repository root:

```bash
python -m pytest -q tests/test_synergy_v66_network.py
```

## 6. Implemented checks

- Exactly 20 stable cell IDs across two regions and three production sectors.
- Deterministic environment generation and replay.
- Per-SKU and aggregate physical conservation.
- Guarded FIFO consumption and earliest-expiry lot ordering.
- Conservative expiry propagation through shipments.
- Warehouse and logistics capacity limits.
- Shipment dispatch / arrival audit and no same-day delivery.
- Prefix invariance: future environment rows cannot alter the earlier daily ledger.
- Invalid regime, horizon and initial-stock inputs are rejected.

## 7. Explicitly not implemented

This physical kernel does **not** yet model prices, invoices, ownership transfer, receivables/payables, cash balances, working-capital limits, credit lines, payment delays, contractual penalties, renegotiation, default, insolvency, FX, customs, taxes, tariffs, border queues, legal jurisdiction, functioning maintenance services, multi-echelon warehouse handling, explicit corridor routing, governance voting, DAO incentives, federation authority, calibrated country/sector data or empirical validation.

The next V6.6.2 increment should add a dated commercial ledger on top of these physical events: purchase orders, invoices, payment terms, receivables/payables, working-capital constraints and default rules. Every financial claim must reconcile to a physical shipment or a clearly labeled service/financial contract. Policy comparisons should wait until this accounting layer is tested.

## 8. Research interpretation

Higher output alone is not evidence of a better coordination policy. Experiments must compare service level, unmet demand, spoilage, working-capital pressure, concentration, regional balance, transport utilization and downside resilience under paired environments. No coordination regime is presumed to win.
