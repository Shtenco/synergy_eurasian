# SYNERGY Unified Economic System — Audit V1

**Status:** preliminary source-level audit; research branch only.  
**Date:** 2026-11-06  
**Branch:** `research/sues-audit-v1`  
**Base:** `main` at `00ca22ba48790a1a39f536f59336d560e448efbd`  
**Scope:** current main plus open research PR #9 and PR #10. No research branch is merged by this document.

## 1. Executive conclusion

SYNERGY already contains three substantial but separate model families:

1. The main EIIOM / seven-sector / productivity / capital-allocation family.
2. V6.4–V6.5.6 network economics, liquidity and resilience experiments (PR #9).
3. V7.0–V7.8 event, production, cash, trade-evidence, credit and stochastic-planning kernels (PR #10).

They are complementary, not yet one executable economy. The highest-priority task is not to add another optimizer. It is to establish one canonical economic state, evidence model, unit/currency model, transaction ledger and cross-module reconciliation contract.

No model result in these branches is a calibrated forecast or proof of real enterprise performance. The synthetic assumptions, scenario outputs, observed evidence and actual cash must remain separate.

## 2. Repository and branch inventory

| Surface | Snapshot | Contents / status |
|---|---|---|
| `main` | base SHA above | Existing EIIOM, seven-sector model, productivity flywheel V1–V3, sector optimizer V4, configs, schemas, tests and federation map |
| PR #9 | `research/self-healing-economy-v6.4-v6.5.6`, head `9c8e4cb503d33e82cc4bb9add729514db1a42587` | 61 changed files; 25,569 additions; 4 deletions; V6.4 and V6.5.3–V6.5.6 |
| PR #10 | `research/synergy-v7-economic-graph`, head `9c0aed72857493bac0a99ba6247ed726c554870e` | 66 changed files; 8,923 additions; 1 deletion; V7 core through V7.8 |

The main branch tree previously inspected contained 110 blobs and 13 directories. PR #10's research tree contains 188 entries. PR #9 adds 61 files, including large raw CSV result sets. These are different snapshots; counts must not be added as though they were unique files.

### Verification evidence

- PR #9 reports 30 local unit-test methods passed across five research versions. Its EIIOM CI run 42149696277 completed successfully at the PR head after the pandas dependency correction.
- PR #10 reports 128 tests passed at code head `82078ed244f1d8af928a0b6343894f860713f85a`; CI run 42168437910 completed successfully.
- PR #10 README integrity run 42182157569 completed successfully at `9c0aed72857493bac0a99ba6247ed726c554870e`.
- A successful test run at an earlier commit does not prove that a later branch head has been tested. Re-run the full suite at the exact final merge candidate.

## 3. Model-family map

### Main branch

- EIIOM-v2: executable LP research optimizer.
- EIIOM-v4: spatial stochastic MILP specification / data requirements, not a calibrated production solver.
- Seven-sector economy: food, housing, energy/water, health, education, mobility and compute.
- Productivity flywheel V1–V3: dynamic reinvestment and Monte Carlo research.
- Sector capital optimizer V4: portfolio allocation under model assumptions.
- Federation contracts, project/evidence schemas and authority boundaries.

### PR #9 — network economics

| Version | Scope | Experiment scale stated in research registry |
|---|---|---:|
| V6.4 | 7-node, 60-day supply-chain kernel; FIFO; supplier choice; paired policy comparisons | 9,300 scenario combinations, 1,600 repeated verification reruns, 360 post-update invariant scenarios |
| V6.5.3 | Early payment, non-recourse factoring, liquidity gaps, concentration and correlated defaults | 15,000 paired scenarios / 45,000 policy paths |
| V6.5.4 | Liquidity pool, supplier firewall, adaptive reserve | 3,100 policy paths |
| V6.5.5 | Self-healing production network; repair and liquidity heuristics | 2,400 policy paths |
| V6.5.6 | Joint repair/liquidity intervention heuristics | 1,600 policy paths |

All are synthetic experiments. V6.5.5's network ranking is heuristic. V6.5.6's rolling-horizon and cvar_robust labels are explicitly not globally optimal or formal CVaR-constrained solvers.

### PR #10 — event-sourced productive economy

- V7 core: event envelope, per-aggregate sequence, idempotency key, hash chain, graph projection and physical-flow primitives.
- V7.1: time-expanded production feasibility.
- V7.2–V7.2.2: working capital, cash waterfall, AR/AP documents and bank-line reconciliation.
- V7.3–V7.3.1: realization evidence chain and matched-pair DiD estimator.
- V7.4–V7.6.6: production MILP, cash, credit facility, maturity and evidence-qualified borrowing base.
- V7.7: scenario-by-scenario recourse benchmark.
- V7.8: two-stage non-anticipative mean-CVaR MILP prototype for one product and one planning epoch.

V7.8 is not yet a full recipe-network, multi-period, cash/credit/collateral stochastic optimizer. The documentation correctly states this limitation.

## 4. Findings and required remediation

Severity is architectural, not a statement that a particular test currently fails.

### F-01 — No canonical double-entry general ledger (CRITICAL)

V7.2 cash waterfall is a period-level liquidity allocation calculator. V7.2.1 is an AR/AP management subledger. V7.2.2 explicitly allocates bank statement lines to documents. None is a complete general ledger with journal entries, chart of accounts, trial balance, accruals, FX revaluation, intercompany eliminations and period close.

**Risk:** modules can each produce internally plausible figures while the consolidated economic state does not reconcile.

**Required:** implement a canonical append-only journal with balanced debit/credit postings, immutable source IDs, account/currency/period dimensions, reversal/adjustment entries, and trial-balance checks. Preserve the existing cash waterfall as a policy calculator, not as the accounting source of truth.

### F-02 — Cross-module currency and unit contracts are incomplete (CRITICAL)

V7 planner enforces a single objective currency for demand, but batch costs, holding costs, cash flows and several other amounts are untyped scalars. Physical flows group external flows by resource and unit, but internal transfer volume is returned as one scalar across all resources, units and periods.

**Risk:** USD can be added to KZT; tonnes can be added to MWh; period totals can be compared without a conversion or timing rule.

**Required:** introduce typed Money(amount, currency), Quantity(amount, unit), FXRate(base, quote, rate, timestamp, source), and Period identifiers. Never aggregate incompatible currencies or units. Change internal physical transfer totals to be keyed by resource, unit, period and boundary.

### F-03 — Benefit de-duplication is too narrow (HIGH)

V7 BenefitLedger prevents a duplicate claim only for the same enterprise × benefit_stream_id × period. Two different stream IDs can still describe the same underlying energy saving, cost reduction, technology effect or network spillover.

**Risk:** the same incremental benefit can be counted more than once across projects, sectors, V1–V6 flywheel models and V7 evidence claims.

**Required:** canonical benefit-event IDs, source measurement IDs, counterfactual IDs, attribution weights that sum to at most one, and a cross-project/network consolidation rule. Maintain separate physical, accrual, cash and welfare measures.

### F-04 — V7 event store is an in-memory reference kernel (HIGH)

The V7 documentation explicitly states that it is not a distributed event database. Hash chaining alone does not provide durable storage, signatures, trusted timestamps, access control, concurrency control, consensus or legal non-repudiation. Current graph projection handles node/edge registration but not the full lifecycle of corrections, supersession, ownership transfers and state transitions.

**Required:** durable append-only event storage, aggregate concurrency/version checks, signed evidence envelopes, independent hash checkpoints, schema evolution, replay and disaster recovery. Corrections must be compensating events.

### F-05 — V7.2.2 bank reconciliation is not a full account reconciliation (HIGH)

The module reconciles explicit allocations to trade documents and exposes unmatched line residuals. It does not by itself prove statement opening/closing balance agreement, ledger cash-account balance agreement, bank fees/FX postings, or complete account-level reconciliation.

**Required:** add statement-level opening balance + signed movements = closing balance checks; reconcile each cash account and currency to the general ledger; model fees, reversals, FX and transfers between own accounts.

### F-06 — V7.3 realization chain needs stronger temporal and attribution controls (HIGH)

The current chain links observed output, accepted deliveries, invoice allocations, settlements and collection attribution. It does not yet provide a full multi-party accounting standard or a complete causal attribution framework. Output period is a free-form string; several links are checked for quantity and amount ceilings but do not establish independent evidence quality or a unique causal benefit across multiple projects.

**Required:** enforce typed periods, date chronology, evidence sign-off, allocation completeness rules where required, and cross-claim de-duplication. Keep pre/post deltas separate from causal estimates.

### F-07 — V7 planner's economic objective and cash model depend on external assumptions (HIGH)

The planner accepts recipe batch costs, holding costs, dated cash flows, collection lags and collection fractions as inputs. It does not derive all costs and collections from the invoice, supplier-payment and bank-reconciliation ledgers automatically. Currency metadata is not attached to every cost input.

**Risk:** a schedule can be mathematically optimal for incomplete or inconsistent cost assumptions.

**Required:** create a single validated input builder that projects verified inventory, supplier payment commitments, invoices, bank cash, payroll/tax, maintenance, replacement and credit terms into the MILP. Reject missing cost coverage for production recipes in production-grade mode.

### F-08 — V7.8 has a deliberately narrow stochastic scope (HIGH)

The common first-stage commitment correctly enforces non-anticipativity for its single decision. Scenario recourse is limited to one product and one planning epoch.

**Required progression:** multi-product recipes, BOM arcs, lead times, inventories, shared resource reservations, dated supplier commitments, cash/credit/collateral/maturity constraints, substitution, backlog and service levels; scenario reveal times and non-anticipativity for every pre-reveal decision; solver bounds/gaps and out-of-sample validation.

### F-09 — V6.5.3 report/table break-even discrepancy (HIGH)

The V6.5.3 report states approximate break-even fees of 0.35% (factoring) and 0.25% (early pay) at PD 5% / recovery 30%, and 0.63% / 0.44% at PD 10% / recovery 30%. The committed `policy_break_even_grid.csv` reports 0.25247598% for factoring and 0% for early pay at PD 5% / recovery 30%; and 0.51011988% for factoring and 0.36181228% for early pay at PD 10% / recovery 30%.

**Required:** trace the report calculation to its source rows and metric definition, regenerate the report from raw data, and fail CI when published tables disagree with computed outputs. Do not silently choose either figure.

### F-10 — V6.5 resilience experiments omit several real-world balance-sheet mechanisms (HIGH)

V6.5.4–V6.5.6 explicitly omit some combination of inventory, lead times, invoice-level double-entry settlement, supplier prices, taxes, payroll, collateral, external financing, household sector and calibrated real default processes.

**Required:** preserve these models as controlled experiments, then replace their simplified interfaces with V7 physical-flow, trade, cash and evidence contracts. Do not directly promote their heuristic rankings into live capital allocation.

### F-11 — No integrated system-wide calibration dataset (CRITICAL)

The repo contains scenario fixtures, synthetic assumptions, manifests and research CSVs, but these are not a shared, independently validated company-level dataset.

**Required:** create a source registry and data lineage contract for observed demand, resource capacity, prices, contracts, inventory, invoices, settlements, assets, maintenance, employment, taxes, FX, defaults and recovery. Every value must carry source, timestamp, unit, currency, coverage and evidence status.

### F-12 — Governance and optimizer authority must remain separated (CRITICAL)

An optimizer's output must not automatically authorize credit, payments, token issuance, asset transfers, securities or changes in ownership. Existing project documentation already states this boundary; the unified system must preserve and enforce it in software.

**Required:** independent authorization service, role/threshold policy, conflict-of-interest controls, human approval for regulated/high-impact actions, audit log and kill switch.

## 5. Canonical SUES target architecture

The unified system is divided into bounded contexts with explicit contracts:

1. **Identity & Membership:** person, household, cooperative, enterprise, federation, beneficial owner, role and jurisdiction.
2. **Economic Graph:** assets, enterprises, projects, technologies, contracts, dependencies, ownership and supply relationships.
3. **Physical Economy:** products, recipes, BOM, resources, capacity, inventory, production, logistics, quality and final use.
4. **Market & Coordination:** demand, offers, orders, matching, procurement, capacity exchange and cooperative rules.
5. **Trade & Contracts:** purchase/sales contracts, delivery acceptance, invoices, payables, receivables, disputes and settlement terms.
6. **Accounting & Evidence:** double-entry journal, bank reconciliation, evidence registry, source lineage, benefit attribution and consolidation.
7. **Money & Clearing:** payment instructions, account balances, multi-currency settlement, mutual credit, multilateral netting and FX.
8. **Capital & Risk:** equity, debt, leasing, factoring, collateral, reserves, guarantees, default and recovery.
9. **Investment & Innovation:** project pipeline, R&D, technology diffusion, capital budgeting and productivity measurement.
10. **Optimization & Simulation:** EIIOM, MILP, stochastic/robust optimization, agent-based experiments and counterfactual analysis.
11. **Governance & Authorization:** federated voting, delegated mandates, limits, appeals, emergency powers and separation of duties.
12. **Observability & Audit:** event replay, immutable checkpoints, model registry, metrics, stress tests and public/private reporting.

No single database or token is the system of record for every domain. Each bounded context owns its facts and exposes versioned events/contracts. A federated index builds cross-domain projections.

## 6. Economic conservation identities

The first implementation must enforce at least these identities:

### Double-entry journal
For each journal entry and currency:
`sum(debits) = sum(credits)`.

### Cash account
`closing_cash = opening_cash + posted_inflows - posted_outflows`.

### Inventory
`closing_inventory = opening_inventory + receipts + completed_output - consumed_inputs - accepted_shipments - writeoffs`.

### Physical capacity
`committed_usage <= evidence_qualified_available_capacity`, with resource, unit, location and period matching.

### Credit
`closing_principal = opening_principal + draws - principal_repayments - writeoffs`; interest is separately accrued/paid.

### Asset capital
`closing_gross_asset_cost = opening_gross_asset_cost + additions - disposals`; net book value separately includes depreciation, impairment and revaluation policy.

### Consolidation
Intercompany balances, sales, purchases and cash transfers are eliminated on consolidation; external customer receipts and external supplier payments remain.

### Benefit attribution
For one measured benefit event, total attribution weights across claims must not exceed 1.0 unless a documented non-overlapping decomposition is supplied.

### Evidence
Scenario values cannot silently satisfy an observed/verified hard constraint. Evidence status transitions must be explicit and auditable.

## 7. Integration sequence

1. **Freeze and inventory:** preserve PR #9 and #10 heads; generate checksums and exact run manifests.
2. **Contract foundation:** money, quantity, time, identity, evidence and event schemas.
3. **Accounting kernel:** double-entry journal, cash accounts, AR/AP, intercompany elimination and bank reconciliation.
4. **Physical kernel:** inventory lots, production receipts, BOM/yield, capacity and logistics.
5. **Cross-ledger bridge:** production-to-delivery-to-invoice-to-settlement-to-bank evidence.
6. **Capital and credit:** debt/equity, credit facilities, collateral, reserves, defaults and recovery.
7. **Unified optimizer:** cash/credit/production/resource constraints in one horizon model.
8. **Network resilience:** V6.5 paired counterfactual policies re-run against the integrated kernel.
9. **Federated governance:** membership, mandates, decision rights, authorization and dispute resolution.
10. **Calibration and validation:** real enterprise pilots, independent review, out-of-sample tests and operational controls.

## 8. Acceptance gates before any production claim

- Exact commit SHA and reproducible environment for every experiment.
- Unit, property, integration, adversarial and regression tests.
- Balanced journal and bank-to-ledger reconciliation.
- Inventory and resource conservation across periods.
- No duplicate benefit attribution across model families.
- Currency and unit conversion provenance.
- Out-of-sample validation and sensitivity analysis.
- Documented model risk, solver gap and infeasibility reporting.
- Human/legal authorization independent of optimization.
- Data protection, security, backup, recovery and access-control review.
- Calibration against real records with explicit permission and privacy controls.

## 9. Immediate work queue

| ID | Work item | Priority | Completion evidence |
|---|---|---|---|
| SUES-001 | Correct V6.5.3 break-even report/table discrepancy | P0 | Regenerated report and automated consistency test |
| SUES-002 | Define Money, Quantity, FXRate, Period and Evidence contracts | P0 | Versioned schemas + validation tests |
| SUES-003 | Implement double-entry journal and trial balance | P0 | Balanced entries, reversals, currency-separated controls |
| SUES-004 | Fix physical-flow aggregation dimensions | P1 | Unit/resource/period-separated summaries |
| SUES-005 | Cross-project benefit attribution registry | P1 | Duplicate and overlap adversarial tests |
| SUES-006 | Durable event persistence and signed evidence | P1 | Replay, concurrency, checkpoint and recovery tests |
| SUES-007 | Full bank/GL reconciliation | P1 | Account opening/movement/closing proof |
| SUES-008 | Build planner input adapter from canonical ledgers | P1 | End-to-end cash/production fixture |
| SUES-009 | Expand V7.8 to multi-product, multi-period | P2 | Non-anticipativity and cash/credit integration tests |
| SUES-010 | Re-run V6.5 resilience against shared V7 kernel | P2 | Paired counterfactual results + model cards |

## 10. Explicit non-goals of this audit

This document does not merge PR #9 or PR #10, does not claim the whole economy has been fully calibrated, does not authorize payments/credit/token issuance, and does not replace statutory accounting, legal review or independent model validation.


## 11. Reproducible quantitative audit — main branch CI snapshot

The following outputs were read from the GitHub Actions EIIOM CI execution at code head `7854c6d8b7bc610b9ea2f2cb7821f3d0ba204506`. They reproduce the repository's scenario assumptions; they are not observed enterprise results.

### 11.1 Seven-sector economy V1

| Metric | CI result |
|---|---:|
| Productive capital | $32,900,000 |
| Gross annual cashflow | $993,500 |
| Annual replacement CAPEX | $1,089,500 |
| Net after replacement | -$96,000 |
| Repair-target residual | +$22,092.50 |
| Repair-target replacement coverage | 102.1123% |
| Public productive capital | $15,805,000 |
| Public net after replacement, baseline | -$49,100 |
| Leontief input-output spectral radius | 0.25066886 |
| Modelled basket cost reduction | 6.6714375% |
| Modelled labor-hour release | 7.43155% |
| 30-year productive capital with configured crises | $41,762,343.92 |
| 30-year cumulative dividends | $5,317,406.35 |
| Final financial reserve | $2,548,202.76 |

The repair scenario applies a uniform 7.5% cashflow uplift and 4% replacement-cost reduction target. It is a target scenario, not a measured improvement. The baseline public portfolio is separately negative even though the whole system is being repaired. The 30-year simulation uses one weighted replacement rate and one gross-yield assumption for the entire portfolio.

### 11.2 Productivity Flywheel V2

| Scenario | Year-10 residual | Final reserve | Cumulative unfunded gap |
|---|---:|---:|---:|
| Stagnation / 2% replacement inflation | -$206,958.14 | $643,189.94 | $0 |
| Moderate growth / 2% | +$133,184.87 | $1,836,141.30 | $0 |
| Strong growth / 2% | +$635,621.10 | $2,412,523.45 | $0 |
| Moderate growth / 5% | -$336,547.17 | $96,242.74 | $0 |
| Strong growth / 5% | +$56,275.36 | $1,744,337.90 | $0 |
| Strong growth / 10% | -$973,167.29 | $0 | $2,586,184.48 |

The V2 model records automation/R&D contributions and expected project returns as separate cohorts. It does not automatically convert the unfunded gap into productive-capital impairment. The gap is a financing/reproduction shortfall measure, not a simulated enterprise default or physical shutdown.

### 11.3 Productivity Flywheel V3 Monte Carlo

20,000 paths per annual shock-probability scenario, with the configured common shock process:

| Annual shock probability | Reserve exhaustion probability | P95 cumulative unfunded gap |
|---:|---:|---:|
| 0% | 0% | $0 |
| 1% | 1.405% | $0 |
| 3% | 5.48% | $60,609.05 |
| 5% | 10.115% | $526,661.76 |
| 10% | 25.005% | $1,925,654.79 |

The P95 gap is zero at 1% despite nonzero reserve-exhaustion probability. This is possible because exhaustion can occur in a small tail while at least 95% of paths still have zero unfunded gap. Do not use the exhaustion probability and P95 gap as interchangeable risk metrics.

### 11.4 Sector Capital Optimizer V4

| Budget | Direct annual residual | Estimated network spillover | Total scenario residual |
|---:|---:|---:|---:|
| $100,000 | $13,050 | $12,300 | $25,350 |
| $250,000 | $37,100 | $34,700 | $71,800 |
| $500,000 | $78,950 | $63,650 | $142,600 |

At the $500,000 budget, the model allocates $90,000 to energy, $70,000 to mobility, $65,000 to compute, $25,000 to education, $15,000 to health, $10,000 to food and $225,000 to shared projects.

These are linear scenario yields. The configuration explicitly says project data is illustrative, deployment has thresholds/diminishing returns, network spillovers require independent verification, and deployment lag is not part of the one-period optimization objective. The reported spillover must be deduplicated across beneficiary enterprises before it can enter consolidated value.

### 11.5 EIIOM V2 reference scenario

| Metric | CI result |
|---|---:|
| Total CAPEX | $650.000bn |
| Annual GVA-equivalent in 2045 | $160.798bn |
| Compute IT capacity | 1,496.245 MW |
| Data-center shell capacity | 1,496.245 MW |

CAPEX by stage is $120bn (2026–30), $290bn (2031–40) and $240bn (2041–45). Country allocations are RU $320.446bn, KZ $119.442bn, BY $130bn, AM $65bn and KG $15.111bn. The solution is mathematically optimal for the supplied LP assumptions, not a forecast or financing commitment.

The `annual_gva_equivalent_2045_bn_usd` output is an undiscounted sum of sector/country suitability-weighted annual yield assumptions across stage allocations. The LP objective separately applies stage time weights (1.0, 0.78, 0.58). These are different metrics and must both be exposed in future reports. The GVA-equivalent coefficient is not observed GVA, revenue or a national-accounts estimate.

## 12. Additional model-specific audit findings

### F-13 — Seven-sector Leontief runtime guard (HIGH)

The current fixture has spectral radius 0.25066886, safely below 1. The runtime computes the inverse of `I-A` before it reports the spectral radius; it should explicitly reject `rho(A) >= 1`, negative coefficients, malformed dimensions and ill-conditioned matrices before solving.

### F-14 — Seven-sector labor and basket proxies (MEDIUM)

The same sector labor-share vector participates in basket cost savings and labor-hour release calculations. This is a transparent scenario proxy, not an empirically estimated labor-demand function. Released hours are not automatically cash savings, employment losses or a guaranteed reduction in working time.

### F-15 — V2/V3 unfunded-gap interpretation (HIGH)

V2 and V3 explicitly report unfunded renewal gaps without automatically converting them into productive-capital impairment. This is useful as a financing-gap stress indicator, but it is not a full solvency, default, production-shutdown or capital-destruction simulation. Future models must branch the same shortfall into alternative policies: emergency credit, insurance recovery, asset impairment, maintenance deferral, production curtailment and insolvency.

### F-16 — V3 dependence structure needs calibration (HIGH)

Annual cashflow growth and replacement inflation are sampled separately; the configured common shock adds a correlated stress component. The dependence structure is hypothetical. It requires empirical estimation, sensitivity to tail dependence and out-of-sample backtesting before risk probabilities are used for reserves or credit pricing.

### F-17 — V4 objective is a one-period linear score (HIGH)

The optimizer uses configured normalized metric weights and linear per-dollar project coefficients. Project deployment lag and diffusion reach are reported but do not enter the LP objective. It omits project-specific failure, diminishing returns, timing, financing, cash constraints, maintenance and interactions. The network spillover term can be double-counted across projects unless connected to the cross-project benefit registry.

### F-18 — EIIOM suitability and yield calibration (CRITICAL)

Country-sector suitability values, GVA-equivalent yields, country bounds and several technology dependency ratios are model inputs, not measured country productivity. The LP's mathematical optimum only proves optimality relative to these coefficients and constraints. A source/evidence registry is required for each parameter, and the optimizer needs sensitivity, dual/slack and out-of-sample reporting.

### F-19 — EIIOM lacks a full capital-to-output transition (HIGH)

The reference LP allocates staged CAPEX and computes an annual GVA-equivalent indicator. It does not yet model commissioning curves, asset depreciation, project completion risk, operating labor, maintenance, working capital, debt service, FX exposure, actual production, imports/exports or an input-output consistency check between the 23 investment sectors and the seven-sector operating economy.

### F-20 — V4 network spillover accounting needs beneficiary-level evidence (HIGH)

V4 adds direct residual yield and network spillover yield to rank projects. The configuration states that spillover is counted once at consolidated network level only if independently verified, but the optimizer itself does not identify unique beneficiary measurement events. SUES BenefitEvent attribution must become the source for this component; otherwise the spillover remains scenario-only.

## 13. Recalculation policy

All headline numbers in the README and reports must be generated from versioned output JSON/CSV, not copied manually. Each run must record:
- repository, branch and exact commit SHA;
- Python/dependency/solver versions;
- config and source-data hashes;
- random seed and path count;
- solver status, objective, feasibility residuals and runtime;
- complete output artifacts;
- evidence class and calibration status.

A report build must fail if any displayed value differs from the generated artifact beyond an explicit numeric tolerance.
