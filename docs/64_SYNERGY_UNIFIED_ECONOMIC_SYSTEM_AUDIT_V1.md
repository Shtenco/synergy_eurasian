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


### F-21 — V2 deterministic scenario domain excludes recession/deflation (MEDIUM)

`simulate_case` rejects negative annual cashflow growth and negative replacement inflation. This prevents the deterministic scenario engine from expressing declining operating cashflow or falling replacement prices. V3 has a wider stochastic growth domain, but V2 should accept explicit negative scenarios with bounded validation.

### F-22 — V4 input validation is incomplete (HIGH) — FIX IMPLEMENTED, CI PENDING

The optimizer checks budget positivity, non-negative objective weights, weight sum, unique project IDs, non-negative maximum investment and direct yield. It does not fully validate finite values, strictly positive normalization denominators, criticality weights, spillover/operational metrics, sector caps/floors or integer deployment fields. NaN values can bypass ordinary comparison checks and reach the solver.

### F-23 — V4 timing and diffusion inputs do not influence allocation (MEDIUM)

`deployment_lag_months` and `diffusion_reach_enterprises` are emitted in the allocation report but do not affect the LP objective or constraints. They are descriptive fields until a time-expanded, adoption-aware model uses them.

### F-24 — V1 supply feasibility does not guard the Leontief stability condition (HIGH)

The current input-output fixture is stable, but `leontief_results` and `solve_supply` invert `I-A` before checking the spectral radius. The runtime should validate non-negative finite coefficients, square dimensions, `rho(A) < 1` and matrix conditioning before using the inverse.

### F-25 — EIIOM output needs a full objective/metric bridge (HIGH)

EIIOM reports both a weighted LP objective and an unweighted 2045 annual GVA-equivalent total. The distinction is explainable by stage weights, but the output does not publish a clear reconciliation between these values or a full project commissioning/capital-stock bridge. Future reports must publish both measures, stage contribution and assumptions side by side.


## 14. Remediation commits in the research branch

Two findings have now been addressed in executable code:
- F-13: seven-sector Leontief matrix now checks rectangular/square shape, finite non-negative coefficients, sector dimensions, spectral radius below 1, and conditioning before solving. Capacity multipliers and critical-service constraints are validated.
- F-22: V4 optimizer now validates finite budgets/weights/project metrics, positive normalization denominators, project criticality, integer lag/diffusion fields, sector caps/floors and project capacity before calling the LP solver.

The new adversarial tests for these controls are committed in `research/sues-audit-v1`. They are not considered accepted until the exact branch-head CI run completes successfully.
