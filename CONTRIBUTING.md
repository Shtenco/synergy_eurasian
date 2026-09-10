# Contributing

## Purpose

Contributions should make the Real Economy OS more reproducible, falsifiable and useful for project selection.

## Contribution types

Welcome:

- new official baseline datasets;
- corrected coefficients with sources;
- alternative scenarios;
- new physical constraints;
- spatial data adapters;
- project archetypes;
- evidence adapters;
- risk tests;
- solver improvements;
- visualization/reporting;
- documentation fixes.

## Required classification

Every new numeric assumption must be tagged in code/docs as one of:

```text
EXTERNAL_FACT
MODEL_ASSUMPTION
SCENARIO_TARGET
SOLVER_OUTPUT
```

## Pull-request checklist

- [ ] State the economic question being changed.
- [ ] Link external sources where applicable.
- [ ] Do not present model assumptions as facts.
- [ ] Add/update invariant tests.
- [ ] Run `pytest -q`.
- [ ] Run the BASE scenario.
- [ ] Report material changes in allocation/output.
- [ ] Explain new legal/social assumptions.
- [ ] Confirm no modelled GVA is treated as cash.
- [ ] Confirm no own-token market cap is treated as collateral.

## Coding style

Prefer:

- small deterministic functions;
- versioned config;
- explicit units in names;
- machine-readable outputs;
- no hidden network calls inside solver;
- no credentials in repo;
- reproducible random seeds where simulation is used.

## Economic model changes

Any change that materially raises output by relaxing a constraint must explain **which physical bottleneck disappeared and why**.

A model is not improved merely because its objective value increased.

## Financial boundary

This repository may produce `ProjectProposal` and evidence requirements. It must not implement unlicensed securities issuance, monetary minting or autonomous approval of financing.
