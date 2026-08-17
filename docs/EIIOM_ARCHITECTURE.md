# EIIOM Architecture

## Purpose

EIIOM is the real-economy simulation and planning layer. It models production dependencies, capacity constraints and investment scenarios. It does not replace the canonical financial ledger.

## State

A reference economic state may contain:

```text
production
productive capacity
inventory
final demand
imports / exports
energy availability
labor availability
capital stock
credit availability
FX requirements
transport capacity
prices / deflators
technology/productivity factors
```

Country and sector dimensions are explicit.

## Input-output core

For gross output vector `x`, technical coefficient matrix `A` and final demand `y`:

```text
x = A x + y
x = (I - A)^(-1) y
```

The implementation must detect singular/ill-conditioned matrices and must not treat unconstrained Leontief output as physically feasible when energy, labor, logistics or capital constraints bind.

## Constraint layer

Candidate constraints include:

- installed productive capacity;
- electricity and fuel;
- compute/data-center availability;
- labor and skill supply;
- rail/road/port capacity;
- working capital and long-term funding;
- import dependency;
- FX settlement capacity;
- project lead times;
- technology availability;
- concentration and country/sector risk.

## AI productivity layer

AI/automation effects are scenario variables with provenance. They may alter labor productivity, scrap rates, utilization, maintenance, logistics or forecasting quality. They must be reported separately from observed output until measured.

## Scenario discipline

Every scenario records:

- baseline date and data vintage;
- sector/country matrix version;
- assumptions;
- CAPEX schedule;
- productivity assumptions;
- constraints;
- uncertainty ranges;
- output metrics;
- evidence status.

No scenario result is automatically a forecast or realized revenue.

## Capital-allocation handoff

EIIOM identifies projects/bottlenecks where incremental capital may create value. It exports project proposals; `synergy_financial_os` applies funding, maturity, solvency and risk gates.

## Feedback loop

```text
observed economy
 -> calibrated state
 -> scenario / project proposals
 -> financial gate
 -> approved investment
 -> implementation
 -> observed goods / capacity / settlement
 -> updated calibrated state
```

The observed update must be distinguishable from the simulated proposal that preceded it.
