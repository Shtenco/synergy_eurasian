# 15 — Developer Guide

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
python src/eiiom_optimizer.py --config config/base_scenario.json --output outputs/base
```

Expected BASE characteristics:

```text
status = optimal
total CAPEX = 650bn USD scenario envelope
compute <= data-center shell
max country compute share <= 60%
productive escrow implementation in this repo = false
```

Exact allocation can change when coefficients/constraints change; that is expected. Hard invariants should not silently weaken.

## Repository contract

### Inputs

- versioned scenario config;
- external datasets with metadata;
- project candidates;
- physical conversion coefficients;
- risk/policy constraints.

### Outputs

- optimal allocation;
- binding/slack constraints (future extension);
- ProjectProposal candidates;
- physical KPI targets;
- evidence requirements;
- scenario summary.

### Not outputs

- token mint transactions;
- security issuance;
- bank transfers;
- regulatory approvals;
- claims of guaranteed returns.

## Adding a sector

1. Add sector name to `config/base_scenario.json`.
2. Add the model coefficient with explicit status/source.
3. Add country suitability assumptions or dataset-derived scores.
4. Add physical input/output dependencies.
5. Add demand/overbuild cap.
6. Add at least one invariant test.
7. Compare BASE before/after.
8. Document why the sector exists and what physical KPI proves success.

## Adding a country/location

v2 supports the five EAEU states. Spatial v3 should move to nodes rather than merely adding country-level averages.

A spatial node should provide:

```text
node_id
country
region
lat/lon
power headroom
grid headroom
water
transport
labor
land
industry demand
agro land
housing stock
legal constraints
source metadata
```

## Solver philosophy

Prefer linear constraints until a nonlinear relationship is genuinely necessary.

For diminishing returns, use piecewise-linear blocks before introducing opaque nonlinear objectives.

For minimum efficient plant sizes / discrete projects, move to MILP binaries.

## Unit discipline

Every variable name should expose units where ambiguity is possible:

```text
capex_bn_usd
compute_it_mw
energy_twh_y
area_million_ha
housing_million_m2
water_m3
```

Never mix nominal and real currencies without explicit conversion metadata.

## Scenario comparison

Recommended future command:

```text
solve BASE
solve STRESS
solve ACCELERATION
solve LOW_CAPEX
solve HIGH_WACC
solve COMPUTE_RESTRICTED
solve CLIMATE_STRESS
```

Report both absolute outputs and delta vs BASE.

## Economic falsifiability

A solver result must be falsifiable.

For every selected project/sector define:

- measurement date;
- physical KPI;
- financial KPI;
- baseline;
- counterfactual where possible;
- external verifier;
- stop condition.

If success cannot be independently measured, the project is not ready for Productive Escrow or scale financing.
