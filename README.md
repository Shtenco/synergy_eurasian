# SINERGY Eurasian

**Real-economy, EIIOM and productive-capital demand layer for the SINERGY Financial OS.**

This repository models the productive side of the system: sectors, countries, projects, bottlenecks, investment needs, goods, energy, logistics, productive capacity and externally verifiable cash flows.

It does **not** mint money, classify internal token-price changes as wealth or bypass the canonical Financial OS. Its outputs are project/economic-state proposals and evidence that can be consumed by `synergy_financial_os`.

## Scope

Reference geographic scope includes the EAEU/Eurasian integration research line:

- Russia;
- Kazakhstan;
- Belarus;
- Armenia;
- Kyrgyzstan.

The model is designed to support changing country/region sets without hard-coding political or legal assumptions into accounting.

## Core economic graph

```text
Energy
 -> Compute / Data Centers
 -> AI / Automation
 -> Productivity
 -> Production
 -> Goods / Services
 -> Logistics / Trade
 -> External settlement
 -> Cash flow
 -> Reinvestment / Capital formation
```

Parallel sector chains include agriculture -> processing -> logistics -> retail/exports and construction -> infrastructure -> housing/industrial capacity.

## EIIOM

The Eurasian Integrated Input-Output Model (EIIOM) extends conventional input-output accounting with capacity, energy, labor, capital, FX, logistics, technology and risk constraints.

Reference identity:

```text
x = A x + y
x = (I - A)^(-1) y
```

where `A` is the inter-sector technical-coefficient matrix. The production model may add scenario-dependent productivity multipliers and binding constraints, but it must not present simulated output as realized external revenue.

## Sector model

The historical research evolved from smaller sector sets toward a wider roughly 24-sector architecture. Candidate sectors include:

- energy;
- agriculture;
- food processing;
- mining;
- metallurgy;
- chemicals;
- machinery;
- construction;
- housing;
- logistics;
- rail/roads;
- data centers;
- AI/software;
- electronics;
- finance;
- healthcare;
- education;
- trade;
- telecom;
- water/municipal infrastructure;
- other region-specific productive sectors.

Historical sector matrices and CAPEX scenarios are preserved as lineage when migrated or referenced.

## Project interface

A productive project should expose at least:

- project identifier and jurisdiction;
- sector and dependency graph;
- CAPEX and OPEX;
- funding currency;
- maturity;
- expected cash-flow distribution;
- energy/labor/logistics requirements;
- FX exposure and hedge state;
- private/anchor capital;
- risk score and first-loss structure;
- collateral/receivables where applicable;
- production milestones;
- goods/inventory milestones;
- settlement evidence classes.

The project layer proposes productive demand. The Financial OS decides whether funding is constitutionally and economically admissible.

## Productive Capital Auction boundary

`synergy_eurasian` may generate project demand and scenario economics. `synergy_financial_os` owns the capital-allocation gate and may combine bank/investment-bank bids using cost, maturity, risk, FX, concentration, liquidity and capital-charge constraints.

A low nominal interest rate alone is not sufficient for selection.

## Conditional productive authorization

A project may receive a conditional authorization envelope before money is released. The authorization itself is not circulating money, HardNAV or profit.

Reference flow:

```text
project approval
 -> conditional authorization
 -> verified milestone / goods / productive-base evidence
 -> bounded release
 -> production
 -> external settlement
 -> repayment / realized revenue
```

## Goods and marketplace observability

The wider SINERGY architecture treats real goods and settlements as economic sensors. Useful evidence classes include:

- delivered order quantities;
- refunds/returns;
- warehouse saleable stock;
- manufacturer/country-of-origin evidence;
- customs/HS/import declarations;
- invoice and settlement currency;
- fiscal receipt / merchant settlement;
- bank/payment confirmation.

Domestic sales channel and domestic origin must remain distinct concepts.

## Import and FX boundary

Import exposure should be derived from actual goods origin and settlement evidence where available, not from gross marketplace turnover alone. FX demand must be linked to real invoices/settlement flows rather than manufactured by a model.

## Simulation vs realized state

Every output must state its evidence class:

- `SCENARIO`;
- `MODEL_ESTIMATE`;
- `OBSERVED_OPERATIONAL`;
- `EXTERNALLY_SETTLED`;
- `AUDITED`.

Only externally settled/reconciled flows can become realized external revenue in the canonical financial ledger.

## Cross-repository integration

- `synergy_financial_os` — financial constitution, capital-allocation gate, accounting truth;
- `synergy_matrix_sota` — household-origin funding duration and liquidity capacity;
- `synergy_pay_system` — payment/FX execution and settlement evidence;
- `synergychain` — OGAS/control-plane visualization and orchestration;
- `agi_olga` — scenario analysis, graph reasoning and policy/project proposals;
- `ai_compress` — compressed economic telemetry/history where integrated.

## Non-destructive research rule

Historical EIIOM versions, sector matrices, CAPEX scenarios, project assumptions and negative/stress cases are preserved. New versions are additive and must not rewrite earlier scenarios as if they had predicted realized outcomes.

## Claims boundary

This repository is a research and systems-engineering domain model. It does not itself create legal investment authority, public funding, licences, bank credit, sovereign commitments or guaranteed returns.
