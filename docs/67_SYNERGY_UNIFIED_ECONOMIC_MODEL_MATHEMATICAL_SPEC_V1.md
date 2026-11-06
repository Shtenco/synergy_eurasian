# SYNERGY Unified Economic Model — Mathematical Specification V1

**Status:** research specification; not a calibrated or executable whole-economy model.  
**Date:** 2026-11-06.  
**Companion:** SUES Architecture V1, Audit V1, Contracts & Journal V1.

## 1. Purpose

This specification connects the existing seven-sector economy, EIIOM, Productivity Flywheel, V6 network policies and V7 production/cash/credit/resilience kernels into one consistent multi-agent model.

The system is **collectively coordinated but not centrally owned**. Participants retain their assets, legal obligations, local decision rights and the right to reject a proposed contract. Federation-level optimization coordinates shared constraints and externalities; it does not grant an optimizer authority to seize or reallocate assets.

The mathematical model has three coupled but separately audited layers:
1. Physical economy: goods, services, resources, capacity, inventory and delivery.
2. Financial economy: money, claims, debt, equity, reserves, cash and settlement.
3. Governance economy: ownership, consent, authorization, rights, obligations and appeals.

## 2. Sets and indices

- (i in mathcal{N}): participants (households, cooperatives, enterprises, public bodies, project SPVs).
- (s in mathcal{S}): sectors/products/services; the current seven-sector reference is a subset.
- (r in mathcal{R}): scarce resources (labor skill-hours, MWh, water, machine-hours, compute-hours, land, logistics).
- (l in mathcal{L}): locations and logistics nodes.
- (t in mathcal{T}): discrete planning periods.
- (omega in Omega): uncertainty scenarios.
- (c in mathcal{C}): currencies.
- (a in mathcal{A}): financial accounts.
- (e in mathcal{E}): immutable economic events and evidence references.

All quantities carry explicit unit, location and period. All money values carry currency and valuation date. No implicit unit or currency conversion is permitted.

## 3. Physical economy

### 3.1 Production and resource feasibility

Let (y_{i,s,t,omega}) be output of product/service (s) by participant (i). Let (a_{r,s}) be resource (r) required per unit of output, and (K_{i,r,t,omega}) be the participant's verified capacity.

[
sum_s a_{r,s} y_{i,s,t,omega} le K_{i,r,t,omega}
quad orall i,r,t,omega
]

Capacity is split into observed, committed, scenario and unavailable portions. Only observed and contractually committed capacity can support firm promises.

### 3.2 Inventory conservation

Let (I_{i,s,l,t}) be closing inventory, (R) receipts, (P) production, (D) deliveries/consumption, (W) write-offs and (T) net transfers.

[
I_{i,s,l,t}=I_{i,s,l,t-1}+R_{i,s,l,t}+P_{i,s,l,t}
-D_{i,s,l,t}-W_{i,s,l,t}+T_{i,s,l,t}
]

Internal transfers must cancel across source/destination locations and must preserve item identity, unit and carrying cost. A production schedule that violates this identity is infeasible even if its financial objective is positive.

### 3.3 Inter-industry requirements

Let (A_{s,k}) be intermediate input (s) required per unit of output (k). For a static Leontief approximation:

[
x=(I-A)^{-1}d
]

This representation is allowed only when (A) is finite, square, non-negative, correctly dimensioned and (ho(A)<1). It is a planning approximation, not a substitute for recipes, inventory timing, capacity and quality constraints.

## 4. Entity and consolidated cash

### 4.1 Entity cash conservation

For participant (i), currency (c), period (t):

[
Cash_{i,c,t}=Cash_{i,c,t-1}
+Receipts^{external}_{i,c,t}
+FundingDraws_{i,c,t}
-Payments^{external}_{i,c,t}
-CAPEX_{i,c,t}
-DebtService_{i,c,t}
-Taxes_{i,c,t}
-Distributions_{i,c,t}
]

Internal transfers are shown separately. They can change the location/owner of cash but cannot create consolidated external cash.

A positive cash balance is not profit. A financing draw is not revenue. An invoice is not collected cash. A valuation mark is not settlement.

### 4.2 General-ledger identity

For every posted journal entry (j), in entity functional currency:

[
sum_{a in Debit(j)} Amount^{functional}_{j,a}
=
sum_{a in Credit(j)} Amount^{functional}_{j,a}
]

Each entity maintains its own ledger. The consolidated journal is a separate reporting layer, not a replacement for member books.

### 4.3 Trade and cash evidence chain

[
ObservedOutput ightarrow AcceptedDelivery ightarrow Invoice
ightarrow Receivable/Payable ightarrow BankAllocation ightarrow Cash
]

Unmatched cash remains suspense/unexplained. It is not revenue by inference. AR/AP is not netted unless legal right of set-off and matching conditions are evidenced.

## 5. Capital stock and reproduction

Let (K_{s,t}) be productive capital, (delta_s) depreciation/physical deterioration, (Inv_{s,t}) new productive investment, (Imp_{s,t}) impairment and (Rec_{s,t}) verified recovery.

[
K_{s,t+1}=(1-delta_s)K_{s,t}+Inv_{s,t}-Imp_{s,t}+Rec_{s,t}
]

Required renewal is not automatically equal to book depreciation. It must reflect physical condition, maintenance, technological obsolescence, safety and service-level targets.

A basic reproduction constraint is:

[
Inv_{s,t}+Maint_{s,t} ge RenewalNeed_{s,t}
]

This may be relaxed only by an explicit, approved asset-life extension decision with a recorded risk and service impact.

## 6. Credit and mutual-credit clearing

### 6.1 Debt stock

[
Debt_{i,t}=Debt_{i,t-1}+Draw_{i,t}-PrincipalRepayment_{i,t}
]

[
Debt_{i,t} le min(FacilityLimit_{i,t}, BorrowingBase_{i,t})
]

Interest is computed on contractually defined beginning/average balances. Maturity, covenant, collateral eligibility, concentration and default are separate constraints.

### 6.2 Mutual-credit balance

Within a closed clearing domain and one currency, participant balances satisfy:

[
sum_i Balance^{mutual}_{i,c,t}=0
]

Participant limits apply:

[
-Limit^{debit}_{i,c,t} le Balance^{mutual}_{i,c,t}
le Limit^{credit}_{i,c,t}
]

A negative member balance is a liability/credit exposure, not free purchasing power. Clearing nets eligible obligations but does not erase gross contracts until legally effective settlement or novation. Defaults and uncollectible balances require loss allocation; they cannot be covered by silently issuing more credit.

### 6.3 Reserve separation

- Social reserve: grants and emergency support.
- Liquidity reserve: payment/settlement timing.
- Credit-loss reserve: expected/realized credit loss.
- Maintenance/replacement reserve: productive asset continuity.
- Disaster/recovery reserve: correlated system shocks.
- Investment capital: long-term risk-bearing productive assets.

Each pool has a purpose, owner, eligible use, liquidity profile, replenishment source and withdrawal authority. No pool can be double-counted as cash, collateral and equity at the same time.

## 7. Currency and consolidation

Each entity has a functional currency; each reporting group has a reporting currency. Translation policy uses closing rates for assets/liabilities, average rates for income/expenses and historical rates for equity, subject to applicable accounting standards and materiality.

Currency translation adjustment is a separate equity/OCI-type item, not operating profit or cash.

Cross-border settlement must account for:
- FX quote direction, source, timestamp and executable spread;
- currency mismatch between CAPEX, OPEX, revenue, debt and collateral;
- settlement finality and correspondent/partner dependencies;
- legal eligibility, sanctions and capital controls;
- DvP/PvP where applicable.

The model does not presume a single common currency. Interoperability and settlement corridors precede any shared monetary instrument.

## 8. Value-added, benefits and welfare

### 8.1 External value added

Internal sales and intermediate transactions are not counted repeatedly as new federation output. Consolidated value added is measured from external production and final use under a defined national-accounts-compatible perimeter.

GVA-equivalent model coefficients are scenario parameters until independently calibrated. They must not be reported as observed GVA, revenue or distributable cash.

### 8.2 Benefit attribution

For every underlying measurement event (m), project-level attributed shares satisfy:

[
sum_{p} Attribution_{p,m} le 1
]

The same productivity improvement cannot be fully credited to automation, R&D, infrastructure, supplier localization and the final enterprise simultaneously.

### 8.3 Welfare and distribution

Track outcomes separately for:
- household disposable income and necessary-cost burden;
- essential-service availability, affordability and quality;
- employment, skill development and voluntary labor-hour release;
- regional and cohort access;
- health, education, housing and mobility;
- ecological footprint, water/energy security and waste.

A productivity gain does not automatically imply a welfare gain. Distribution, prices, job transitions and service access must be measured.

## 9. Uncertainty, resilience and recovery

For scenario (omega), define system loss (L_omega) from unmet essential demand, production shortfall, liquidity deficit, credit loss, asset impairment and recovery cost. Avoid double-counting the same event across categories.

[
CVaR_alpha(L)=min_eta left[
eta+rac{1}{1-alpha}mathbb{E}(L-eta)^+
ight]
]

Report expected loss, VaR/CVaR, reserve exhaustion, liquidity runway, recovery time and service-level distributions. Scenario probabilities require empirical calibration. Without calibration, label outputs as sensitivity analysis.

Essential-service constraints should be explicit:

[
Service_{s,t,omega} ge MinimumEssentialService_{s,t}
]

where feasible. If infeasible, the model must report the deficit and required emergency action, not silently relax the floor.

## 10. Federated coordination and decentralization

### 10.1 Local optimization

Each participant solves its own feasible problem under its legal obligations, resource constraints, contracts and member mandate. It may accept, reject or counter-propose a federation offer.

### 10.2 Shared resource coordination

For a shared resource with capacity (ar R_r), local plans (x_i) produce aggregate use:

[
U_r=sum_i a_{i,r}x_i
]

A federation coordinator may publish a scarcity signal or shadow price (lambda_r). A simple dual update is:

[
lambda_r^{k+1}=max(0,lambda_r^k+eta(U_r^k-ar R_r))
]

The price signal coordinates demand; it does not transfer ownership. Contracts, reservations and member approvals create binding commitments.

### 10.3 Subsidiarity and consent

- Local matters remain local unless externalities cross boundaries.
- Shared infrastructure decisions require the delegated mandate.
- Capital rights are contractual and do not automatically grant constitutional control.
- One-token-one-vote is not assumed.
- AI recommendations do not execute transactions.
- Emergency powers have scope, duration, review and expiry.

## 11. Unified optimization hierarchy

A single weighted scalar can hide unacceptable trade-offs. Use lexicographic feasibility first:

**Tier 0 — hard admissibility:** legal rights, authorization, physical possibility, solvency, safety, data permissions.

**Tier 1 — essential continuity:** minimum food, energy, water, health, housing, mobility and communication service.

**Tier 2 — capital preservation:** maintenance, replacement, liquidity, maturity and collateral constraints.

**Tier 3 — Pareto optimization:** productivity, external value added, welfare, innovation, resilience, ecological outcomes and regional balance.

**Tier 4 — optional preferences:** published stakeholder weights for trade-offs that remain after hard constraints.

Produce a Pareto set, binding constraints, shadow prices, slack, solver status, infeasibility explanation and sensitivity. Do not hide infeasible requirements by changing assumptions silently.

## 12. Integration map

| Existing family | Mathematical role | SUES interface |
|---|---|---|
| Seven-sector economy V1 | Static resource/inter-industry baseline and reproduction accounting | Sector/resource/product/unit/period inputs |
| Productivity Flywheel V1–V3 | Capital reinvestment, adoption, project cohorts and shock sensitivity | CapitalStock, BenefitEvent, ScenarioRun |
| Sector Optimizer V4 | One-period project allocation | InvestmentProposal, ConstraintSet, ModelRun |
| EIIOM executable V2 | LP investment allocation reference | Typed resource, CAPEX and evidence inputs |
| EIIOM V4 design | Target stochastic spatial MILP | ScenarioTree, ResourceBalance, NonAnticipativity |
| V6.4 | Network coordination and inventory/production policies | Demand, capacity, FIFO and verified outcome events |
| V6.5.3–V6.5.6 | Credit, liquidity, concentration and resilience policies | Loan, Receivable, Reserve, Default, Recovery |
| V7.0–V7.8 | Event, production, trade, cash, collateral and stochastic planning kernels | EconomicEvent, PhysicalFlow, Journal, TradeSubledger, InventoryLedger |

## 13. Implementation gates

A coupled simulator is not accepted until:
- physical quantity balances reconcile by item/unit/location/period;
- each entity GL balances and subledgers reconcile to control accounts;
- intercompany balances eliminate only matched reciprocal amounts;
- external cash is distinguished from financing and internal transfers;
- capital stock roll-forward reconciles to additions, depreciation, impairment and recovery;
- credit and mutual-credit balances obey limits and maturity;
- benefits are attributed once;
- FX translation and CTA reconcile under a declared policy;
- optimizer inputs include provenance and evidence class;
- scenario outputs are reproducible and clearly labeled;
- local autonomy, approval and execution boundaries are tested;
- real-world calibration and independent validation precede operational claims.

## 14. Current implementation boundary

The present repository contains separate research kernels and SUES reference primitives. It does not yet contain one calibrated, fully coupled whole-economy simulator. In particular, full BOM/production capitalization, multi-entity consolidation close, cross-border settlement execution, legal mutual-credit issuance, calibrated EIIOM V4 stochastic spatial MILP and real-world welfare measurement remain future work.

**This specification defines the target model and its invariants. It is not a forecast, investment recommendation, monetary issuance authorization or claim of a deployed federation.**
