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

## V7 implementation status (research branch)

The V7 line has now progressed from architecture into an executable reference kernel. See [PR #10](https://github.com/Shtenco/synergy_eurasian/pull/10); it remains a research branch until reviewed and merged.

| Layer | Implementation | Boundary |
|---|---|---|
| V7 core | Event envelope, per-aggregate sequence/idempotency, hash-chain verification, graph projection, evidence-qualified resource capacity, physical-flow consolidation, benefit ledger, NPV/CVaR/Pareto primitives | In-memory reference kernel; no durable distributed event store |
| V7.1 | Time-expanded recipes, integer batches, inventory receipts, lead times, shared resource buckets, demand fulfillment and executable integrated factory fixture | Deterministic feasibility validator, not a production scheduler optimizer |
| V7.2 | Working-capital metrics, DSO/DIO/DPO/CCC, cash release from NWC movement and prioritized cash waterfall | Period-level liquidity calculator, not double-entry accounting |
| V7.2.1 | AR/AP documents, partial settlements, credit adjustments, disputes, aging, gross counterparty exposure and sourced PD×LGD estimate | In-memory subledger projection; no legal netting, FX conversion or statutory impairment |

V7 acceptance still requires durable event storage, signed evidence, access controls, trusted checkpoints, concurrency/recovery tests, independent accounting/legal/security review and calibration against real enterprise data. Scenario and synthetic examples are not enterprise forecasts.

## Next development frontier

1. **V7.2.2 — cash reconciliation:** bank statement lines, settlement allocation, unmatched receipts, reversals, cash-account controls and reconciliation evidence.
2. **V7.3 — causal operating performance:** link production orders, delivery acceptance, invoice issuance, collections, asset costs and benefit claims to a single evidence chain. Separate physical output, recognized revenue, collected cash and incremental net value.
3. **V7.4 — temporal supply network:** supplier shipment lead times, lot/serial traceability, inventory aging, safety stock, substitutions, transport capacity, storage and disruptions.
4. **V7.5 — constrained optimization:** MILP/CP-SAT over order timing, scarce resources, inventory, cash constraints and essential-service minimums; preserve Pareto alternatives rather than hiding trade-offs in one score.
5. **V7.6 — resilience and learning:** correlated shocks, recovery policies, formal CVaR/chance constraints, verified reusable technology packages and measured R&D-capability reproduction.

No automated optimizer output may authorize credit, token issuance, payments, securities distribution or legally binding commitments.

### V7.2.2 update — cash evidence

The research branch now also includes explicit bank statement reconciliation: manually approved allocations connect signed bank lines to AR/AP documents, generate settlement events, preserve unmatched residuals for review and report gross cash control totals by currency. No automatic fuzzy matching is performed and unexplained cash is not recognized as revenue. See [V7.2.2 specification](docs/50_SYNERGY_V7_2_2_BANK_RECONCILIATION.md) and [PR #10](https://github.com/Shtenco/synergy_eurasian/pull/10).

### V7.3 update — realization evidence chain

V7.3 now validates the explicit chain from observed production output to customer acceptance, invoice allocations, settlement events and sourced cash attribution. It separately reports baseline output deltas, accepted quantities, invoiced revenue, collected cash and cost categories. It does **not** infer causality from a pre/post comparison, prorate cash receipts, or collapse recognized revenue into collected cash. See [V7.3 specification](docs/51_SYNERGY_V7_3_REALIZATION_EVIDENCE_CHAIN.md) and [PR #10](https://github.com/Shtenco/synergy_eurasian/pull/10).

### V7.3.1 update — causal measurement discipline

V7.3.1 adds a matched-pair difference-in-differences estimator with pair-level effects, Student-t confidence intervals and explicit treatment/control identity checks. It records that parallel trends, no spillovers and matching quality require independent review; a single pre-period cannot test parallel trends. It is a design-conditional estimate, not automatic causal certification. See [V7.3.1 specification](docs/52_SYNERGY_V7_3_1_CAUSAL_DID.md).

### V7.4 update — MILP production scheduling

V7.4 adds a SciPy/HiGHS mixed-integer scheduler over recipe batches, inventory balances, lead times, customer demand and shared firm resource capacity. It maximizes explicit demand value less batch and inventory holding costs. It reports solver optimality and MIP gap separately; scenario values are not treated as observed cash. See [V7.4 specification](docs/53_SYNERGY_V7_4_MILP_PRODUCTION_SCHEDULER.md) and the reproducible factory example.

### V7.4.1 update — inventory policy

The V7.4 MILP now supports end-of-period minimum inventory (safety stock) and maximum storage bounds by product. Infeasible combinations are reported as infeasible, not silently relaxed. The factory fixture demonstrates a 10 kg steel safety stock and 30 kg storage ceiling.

### V7.5 update — production resilience stress

V7.5 replays a fixed production schedule under correlated common shocks, resource-specific capacity reductions and supplier receipt delays. It reports demand service distributions, complete-service frequency and empirical tail service shortfall. This is conditional Monte Carlo stress, not calibrated probability forecasting, recourse optimization or a formal CVaR-constrained solution. See [V7.5 specification](docs/54_SYNERGY_V7_5_MONTE_CARLO_RESILIENCE.md).
