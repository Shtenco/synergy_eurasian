# SYNERGY Productivity & Resilience System — Master Map V1–V6

**Consolidation date:** 2026-11-06  
**Status:** linked research model families; not one calibrated end-to-end simulator.

## Strategic objective

SYNERGY should maximize sustainable network-wide productive capability, not isolated participant profit. It must finance the ability to create, test, adapt, diffuse and reproduce technologies while preserving critical-sector reproduction, liquidity and human agency.

## Do not collapse distinct version lines

There are three connected but distinct model families:

1. **EIIOM / real-economy planning:** EIIOM-v2 executable LP; EIIOM-v4 spatial stochastic MILP specification; project factory, sector and resource constraints.
2. **Productivity Flywheel V1–V6:** seven-sector reproduction baseline; V1 static uplift sensitivity; V2 ten-year cohorts/reserves; V3 Monte Carlo stress; V4 sector capital LP; V5 discrete Bass-style technology diffusion MILP; V6 project complementarity, benefit-stream exclusion and research-capability feedback.
3. **Network Economics & Resilience V6.4–V6.5.6:** separate research line in [PR #9](https://github.com/Shtenco/synergy_eurasian/pull/9), covering production coordination, credit/liquidity, early pay/factoring, supplier substitution, self-healing networks and joint reserve allocation. This is not a sequential continuation of Productivity Flywheel V6; the numbering belongs to a different research lineage.

## Productivity line source map

| Version | Main contribution | Source |
|---|---|---|
| Seven-sector baseline | Reproduction accounting across FOOD, HOUSING, ENERGY, HEALTH, EDUCATION, MOBILITY, COMPUTE | `src/synergy_economy_7sector.py`, `docs/38_SYNERGY_ECONOMY_6_3_CONSOLIDATED.md` |
| V1 | Static productivity flywheel | `src/synergy_productivity_flywheel.py`, `docs/39_SYNERGY_PRODUCTIVITY_FLYWHEEL_V1.md` |
| V2 | Dynamic ten-year cohorts, lags, reserves and unfunded gaps | `src/synergy_productivity_flywheel_dynamic_v2.py`, `docs/40_SYNERGY_PRODUCTIVITY_FLYWHEEL_DYNAMIC_V2.md` |
| V3 | Correlated shocks and stochastic R&D success | `src/synergy_productivity_flywheel_monte_carlo_v3.py`, `docs/41_SYNERGY_PRODUCTIVITY_FLYWHEEL_MONTE_CARLO_V3.md` |
| V4 | Sector capital allocation LP | `src/synergy_sector_optimizer_v4.py`, `docs/42_SYNERGY_SECTOR_CAPITAL_OPTIMIZER_V4.md` |
| V5 | Discrete rollout levels and Bass-style adoption diffusion | V5/V6 extension package delivered with the 2026-11-06 consolidation |
| V6 | Exclusive benefit streams, project complementarities and R&D-capability feedback | V5/V6 extension package delivered with the 2026-11-06 consolidation |

## Unified causal architecture

```text
Observed demand + physical resource state
                ↓
Enterprise / asset / sector registry
                ↓
Seven-sector reproduction accounting
                ↓
V1 static → V2 dynamic → V3 stress
                ↓
V4 capital allocation → V5 technology diffusion
                ↓
V6 graph complementarities + research-capability loop
                ↕
Resilience V6.4–V6.5.6: liquidity / suppliers / recovery
                ↓
Independent evidence + benefit-stream ledger
                ↓
Financial authorization → settlement → asset evidence
                ↓
Verified residual, output, resilience and released time
                └──── reinvestment into the next research cycle
```

## Accounting invariants

- Consolidated productive value is not internal transfer volume.
- Debt proceeds, token issuance and asset revaluation are not operating gains.
- Replacement CAPEX and critical-service obligations precede discretionary allocation.
- Duplicate enterprise benefit streams are rejected.
- Research capacity, output indices and labor-time indices are not cash NPV.
- Labor hours released are not assumed to be layoffs or cash savings.
- Optimizers recommend portfolios; they do not authorize issuance, payments or legal commitments.

## Scenario status

The seven-sector repair case moves the illustrative whole-system residual from approximately -$96,000 to +$22,092.50/year. The V5/V6 modelled NPVs are highly sensitive to synthetic per-adopter yields, adoption rates, complementarity values and benefit lives. V6 capability-building trades some short-horizon NPV for a higher research-throughput index. None of these values is observed enterprise performance or a forecast.

The parallel resilience line contains synthetic paired experiments: V6.4 production coordination; V6.5.3 credit/liquidity and factoring; V6.5.4 liquidity pools and supplier rerouting; V6.5.5 self-healing; V6.5.6 joint reserve allocation. Its reports explicitly distinguish external sales, collected cash, operating result, arrears and internal transfers.

## Next target: V7 common economic graph

Build one event-sourced graph with stable `enterprise_id`, `asset_id`, `resource_id`, `technology_id`, `project_id` and `benefit_stream_id`. It must connect suppliers, customers, resources, technology compatibility, physical flows, adoption cohorts, cash settlement and evidence provenance. Add multi-period working capital, depreciation/replacement, stochastic failure, real options, formal CVaR constraints and a Pareto frontier across NPV, output, essential-service continuity, resilience, labor time and innovation capacity.

Until that common data and evidence layer exists, V1–V6 remain a family of related research models, not a single validated economic digital twin.

## Reproducibility and current CI note

V1–V4 source and tests are in this repository. V5–V6 source, config, tests, docs and outputs are included in the companion extension package; its tests were run locally: **23 passed**. The PR #9 resilience branch initially failed test collection because pandas was absent; `pandas>=2.2,<4` was added in commit `9c8e4cb503d33e82cc4bb9add729514db1a42587`. After adding pandas, the follow-up GitHub Actions run 42149696277 completed successfully. PR #9 remains open and has not been merged.
