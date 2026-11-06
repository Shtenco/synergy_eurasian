# SYNERGY Unified Economic System (SUES) — Architecture V1

**Status:** target architecture / research specification.  
**Date:** 2026-11-06.  
**Companion:** [Audit V1](64_SYNERGY_UNIFIED_ECONOMIC_SYSTEM_AUDIT_V1.md), [Typed Contracts and Journal V1](65_SYNERGY_UNIFIED_ECONOMIC_SYSTEM_CONTRACTS_AND_JOURNAL_V1.md), [Mathematical Specification V1](67_SYNERGY_UNIFIED_ECONOMIC_MODEL_MATHEMATICAL_SPEC_V1.md).

## 1. Design objective

SUES is a federated operating system for a productive economy. It coordinates people, households, cooperatives, enterprises, projects, infrastructure, capital providers and public institutions without collapsing their legal identity, property rights, accounts or decision authority into one central operator.

The system's optimization target is not token price, internal turnover, gross transaction volume or a single GDP proxy. It is a feasible and auditable improvement in:
- real goods and service availability;
- productivity and quality;
- household and participant welfare;
- capital reproduction and long-run productive capacity;
- resilience and recovery;
- innovation and knowledge diffusion;
- ecological and resource constraints;
- fairness of access and distribution.

SUES must expose trade-offs instead of hiding them inside one opaque score.

## 2. Architectural principles

1. **Federation, not one owner:** each member retains its legal identity, accounts, assets, liabilities and local decision rights.
2. **Subsidiarity:** a decision stays at the lowest level able to handle its externalities and resource constraints.
3. **One economic fact, one canonical identity:** shared facts are referenced, not copied into competing ledgers.
4. **Physical reality before financial claims:** capacity, inventory, deliveries and output require quantity, unit, location, period and evidence.
5. **Double-entry money accounting:** every posted financial event balances in functional currency; cash, accrual, debt and equity are distinct.
6. **No implicit conversion:** currencies, units, periods and evidence classes cannot be silently mixed.
7. **Internal transactions are eliminated on consolidation:** transfers may allocate value between participants but do not create new external output.
8. **Scenario is not fact:** model assumptions never silently become observed data or collateral.
9. **Optimization is advisory:** solvers propose; authorization and execution are separate.
10. **Open protocols, controlled rights:** interfaces may be interoperable while intellectual property, access, privacy and licenses remain explicit.
11. **No hidden cross-subsidy:** transfers, grants, common services and solidarity pools are separately visible and governed.
12. **Failure containment:** local insolvency, software failure or malicious actors must not automatically disable the entire federation.

## 2A. Federation authority firewall

SUES is the real-economy research and integration specification inside the existing federation. It does **not** absorb the canonical authorities already assigned in `config/federation_v4.json`.

| Authority | Canonical owner | SUES relationship |
|---|---|---|
| Federation architecture, constitution and authority map | `Shtenco/synergy_system` | Consumes standards; cannot redefine authority unilaterally |
| Real-economy resource state, project proposals and physical model | `Shtenco/synergy_eurasian` | SUES research/reference models live here |
| Accounting, liabilities, liquidity, profit recognition and capital capacity | `Shtenco/synergy_financial_os` | SUES journal/subledgers are reference contracts until formally adopted |
| Payment execution, routing and settlement receipt | `Shtenco/synergy_pay_system` | SUES emits intents/required flows; it does not execute payments |
| Technology candidate evidence and hypothesis state | `Shtenco/nexus_science_agent` | SUES consumes qualified technology evidence |
| Business intents and demand signals | `Shtenco/synergychain` and distributed sources | SUES consumes permissioned demand signals |
| Network transport state | `Shtenco/synergynet` | Transport is not economic truth or financial authority |
| Service lifecycle and node health | `Shtenco/synergy_meta_os` | Runtime orchestration is not accounting or settlement authority |

**Hard prohibitions:** modelled GVA is not cash; own-token market capitalization is not collateral; internal AMM marks are not external profit; flash-loan principal is not owned capital; a blockchain commitment is not proof of physical/economic truth; an AI recommendation is not capital authorization. These are explicit federation invariants, not merely UI labels.

The SUES in-memory journal, AR/AP, inventory, translation and consolidation modules are research reference implementations. They must not be represented as the canonical accounting ledger or payment service until independently reviewed and formally adopted by the relevant authority owners.

## 3. Federation levels

| Level | Economic unit | Primary responsibilities | Authority boundary |
|---|---|---|---|
| L0 | Person / household | Work, consumption, skills, savings, care, voluntary membership | Personal consent and private property |
| L1 | Cooperative / team / micro-enterprise | Joint work, shared tools, service provision, mutual aid | Member-approved charter and local limits |
| L2 | Enterprise / project / asset operator | Production, contracts, payroll, maintenance, investment | Board/owner mandate, legal duties, creditor rights |
| L3 | Cluster / municipality / regional network | Shared infrastructure, logistics, workforce, resource coordination | Delegated public/cooperative mandate |
| L4 | National / cross-border federation | Standards, interoperability, cross-region infrastructure, settlement corridors | Treaty, law, member agreements and jurisdictional controls |
| L5 | Global protocol federation | Open identity, data, trade, technology and clearing standards | Protocol governance; no unilateral authority over member assets |

A higher level may coordinate shared externalities but cannot directly seize or reassign lower-level assets through an optimizer output.

## 4. Bounded contexts and source of truth

| Context | Canonical records | Owner of truth |
|---|---|---|
| Identity & Membership | Member, legal entity, household, role, jurisdiction, beneficial owner | Identity registry / authorized member |
| Economic Graph | Enterprise, project, asset, technology, ownership, dependency, supply edge | Graph registry, derived from signed events |
| Physical Economy | Product, recipe, resource, capacity, inventory, production, shipment, quality | Operator systems with evidence |
| Market & Coordination | Demand, offer, order, allocation, procurement, capacity reservation | Contract/order service |
| Trade & Contracts | Purchase/sales contract, acceptance, invoice, payable, receivable, dispute | Contract and trade subledger |
| Accounting & Evidence | Chart of accounts, journal, evidence, audit trail, reconciliation | Entity's books; federation-wide canonical accounting authority remains Financial OS |
| Money & Clearing | Payment instruction, account movement, netting obligation, FX execution | Member ledgers and licensed/contracted providers; canonical settlement execution remains Pay System |
| Capital & Risk | Equity, debt, facility, collateral, reserve, guarantee, default, recovery | Contractual capital provider / borrower |
| Investment & Innovation | Project proposal, R&D, technology package, deployment cohort, benefit event | Project owner and evidence registry |
| Optimization & Simulation | Scenario, model, parameters, solution, solver status, confidence, model card | Versioned model registry |
| Governance & Authorization | Charter, mandate, vote, policy, threshold, approval, appeal | Member/federation governance |
| Observability & Audit | Metrics, event replay, checkpoints, incident, audit finding | Independent audit and monitoring roles |

A projection can combine facts from several contexts, but it must retain source IDs and not become a competing source of truth.

## 5. Canonical ontology and identifiers

Every persistent object receives a globally unique immutable ID. Human-readable codes are aliases, not primary keys.

Minimum canonical entities:
- `Party`: person, household, cooperative, enterprise, public body, financial institution.
- `Membership`: party, federation, role, start/end, rights, jurisdiction.
- `Asset`: physical, financial, intellectual or contractual asset; owner/operator/custodian are distinct.
- `Resource`: measurable capacity such as labor-hours, MWh, water, machine-hours, compute-hours, storage or logistics.
- `Product`: goods/services with versioned units, quality and recipe definitions.
- `Project`: bounded investment or operating initiative with scope, owner, milestones and risk.
- `Contract`: counterparties, price, quantity, delivery, payment, dispute and termination terms.
- `EconomicEvent`: immutable event envelope with effective and recorded time, source and evidence.
- `JournalEntry`: balanced financial postings.
- `PhysicalFlow`: typed quantity between nodes, resource and period.
- `BenefitEvent`: measured outcome with a baseline/counterfactual and attribution constraints.
- `Decision`: proposal, model run, authority, approval, execution result and appeal.

IDs are never reused after deletion or dissolution. Corrections use new events and compensating entries.

## 6. Event and data architecture

### 6.1 Event envelope

Every domain event should carry:
- event ID, aggregate type and aggregate ID;
- aggregate sequence and idempotency key;
- event type and schema version;
- effective time and recorded time;
- source system and actor;
- evidence IDs and data classification;
- payload hash and previous aggregate hash;
- authorization/approval references where relevant.

The current V7 event store is a reference kernel. Production requires durable append-only storage, signatures, trusted time, concurrency control, independently anchored checkpoints, schema migration, backup and deterministic replay.

### 6.2 Commands and events

Commands express intent and may be rejected. Events record accepted facts. Example:

`CreatePurchaseOrder` → policy/limit checks → `PurchaseOrderApproved` → `SupplierCommitmentRecorded` → `GoodsDispatched` → `GoodsReceived` → `InvoiceIssued` → `PaymentSettled`.

A model recommendation is not an event that changes a balance. Only an authorized command can create a binding event.

### 6.3 Evidence classes

- `OBSERVED`: source system or instrument reports a fact.
- `VERIFIED`: independent or authorized validation has checked the fact.
- `UNDERWRITTEN`: a named institution accepts a risk/valuation under stated terms.
- `SCENARIO`: assumption or simulation input.

A status transition requires a new evidence event with actor, basis and timestamp. It must never overwrite the original classification.

## 7. Accounting and value model

### 7.1 Distinct measurement layers

SUES reports these separately:
1. Physical production and final use.
2. External sales and purchases.
3. Accrual revenue, expenses and profit.
4. Collected cash and paid cash.
5. Financing proceeds, principal repayment and interest.
6. Asset cost, depreciation, impairment and net book value.
7. Internal transfers and intercompany positions.
8. Token/market valuation, where legally and technically applicable.
9. Social, ecological and welfare indicators.

None is a substitute for another.

### 7.2 Entity accounting

Each legal entity maintains its own functional-currency double-entry ledger. The ledger owns posted balances. Subledgers (AR/AP, inventory, payroll, fixed assets, loans) reconcile to control accounts. Bank statements reconcile to cash accounts. Reversals and adjustments are new linked entries.

### 7.3 Federation consolidation

Consolidation has separate stages:
- validate reporting entity perimeter and ownership;
- translate subsidiary trial balances under a documented FX policy;
- match intercompany revenue/expense, AR/AP, loans/interest and cash transfers;
- eliminate only matched reciprocal amounts;
- preserve unmatched differences as exceptions;
- calculate non-controlling interests and ownership attribution;
- publish consolidated statements with traceable elimination journals.

Do not net unrelated counterparties, periods or currencies. Do not eliminate a mismatch merely to force the group totals to balance.

### 7.4 Physical consolidation

Internal physical transfers are not new production. Report external imports, external exports, final use, internal movement, inventory change, losses and production separately, keyed by resource, unit, location and period.

## 8. Production and coordination

Production planning is built from:
- demand signals with source, confidence and due date;
- versioned recipes/BOM, yield, scrap and quality limits;
- observed/committed inventory receipts and lead times;
- firm resource capacity by unit, location and period;
- labor skills, energy, water, compute and logistics;
- maintenance and outage calendars;
- customer acceptance and service-level requirements;
- cash and supplier payment constraints.

A feasible plan must satisfy material, capacity, inventory, cash and contractual constraints simultaneously. A plan with missing or non-firm critical resources is not a firm commitment.

## 9. Money, mutual credit and clearing

SUES does not assume one token can safely perform every monetary function. Separate:
- external sovereign/bank money used for legal settlement;
- member account balances and payment claims;
- mutual-credit limits and multilateral clearing obligations;
- investment securities or contractual participation rights;
- utility/reward points, if used;
- crypto-assets and stablecoins, where legally permitted.

Each instrument has its own issuer, holder claim, redemption rule, reserve/liability, governance, jurisdiction, risk and accounting treatment.

Mutual credit is a credit relationship, not free wealth. Each participant has a limit, expiry/renewal, pricing or fee policy, default process and dispute route. Multilateral netting reduces settlement liquidity but does not erase gross contractual claims until legally effective settlement/novation occurs.

The clearing engine must:
- net only eligible obligations with matching parties, currency, due window and legal status;
- preserve gross claims and netting evidence;
- apply participant limits and concentration caps;
- model liquidity and settlement finality;
- fail closed when legal authority or evidence is missing.


### 9.1 Mutual-credit and household-capital discipline

The household → cooperative → SME → project-capital ladder is a funding pathway, not a money multiplier. Each contribution is a separate tranche with owner, currency, callable date, maturity, liquidity class and risk limit.

For a funded loan, the lender records a receivable and the borrower records a liability. Loan principal is not income or consolidated NAV. Credit sustainability requires realized interest/fees and recovered collateral to exceed credit losses, funding cost, OPEX and fraud losses.

Maturity matching is mandatory:

`WeightedFundingMaturity >= LoanMaturity + LiquidityBuffer`

Callable emergency reserves must not finance long-dated illiquid loans unless a separately authorized maturity-transformation and liquidity-reserve policy exists.

Keep at least three separate books:
- **Social reserve:** grants and emergency support.
- **Credit book:** loans, expected credit loss, collateral and loss reserves.
- **Investment book:** long-term productive assets and equity.

A social reserve must not silently recapitalize chronic investment losses. Repayments to earlier participants must be funded from realized income or explicitly disclosed reserve support, never disguised as new principal.

### 9.2 Cross-border currency discipline

SUES does not begin by assuming a common Eurasian currency. The first sequence is common data standards, interoperable payments, transparent FX, cross-border settlement, common project-finance passports, portable evidence/collateral, and only then a review of whether a shared monetary instrument is useful.

Every project carries a currency vector for CAPEX, OPEX, revenue, debt and collateral. FX reference rates are not executable quotes. Currency mismatch, hedge/basis cost, settlement finality and jurisdiction are explicit constraints. DvP/PvP and legal eligibility govern asset/FX netting.

## 10. Capital, reserves and investment waterfall

Capital is partitioned by legal/economic nature:
- member equity and retained earnings;
- secured and unsecured debt;
- revolving facilities and trade credit;
- leasing and asset finance;
- receivables finance/factoring;
- grants and public procurement;
- insurance and guarantee capacity;
- cooperative mutual-aid funds;
- liquidity reserves and repair/recovery reserves.

A reserve is not revenue. A credit line is not equity. Collateral is not cash. A token market price is not a reserve. Borrowing-base eligibility is not a lender's final approval.

Operating cash priority is policy-configurable but must protect mandatory obligations, asset replacement and liquidity. Distributions are gated by solvency, reserve policy, covenants, legal requirements and member approval. The cash waterfall is an allocation policy over actual cash; the journal remains the accounting source of truth.


### 10.1 Delta at each economic scale

SUES adopts the repository's Delta concept as a family of distinct metrics, not one universal cash number:

- Household Delta = income − necessary expenses − debt service.
- Business Delta = external revenue − cash OPEX − taxes − debt service − maintenance/replacement CAPEX.
- Project Delta = realized operating cashflow − senior debt service − lifecycle reserve − required maintenance.
- Regional/System Delta is a planning measure that separately adjusts external sales, import-substitution value, imported inputs, financing cost, infrastructure lifecycle cost and realized losses.

Gross cashflow is not distributable Delta. Internal turnover and transfer payments cannot be counted as new external value. GDP/GVA and realized cashflow remain separate metrics.

### 10.2 Five reinforcing but separately measured loops

1. Financial loop: external realized P&L → Financial OS → reserves/reinvestment.
2. Productive loop: capital → capacity → goods/services → customer cashflow → reinvestment.
3. Human-capital loop: health/education/housing/mobility → productivity → household/business Delta.
4. Science/IP loop: research → reproducible evidence → technology/IP → deployment → productivity/export → next research.
5. Demand-localization loop: observed demand/import bottleneck → supplier candidate → verified local production → delivered-cost/resilience change.

A loop may reinforce the next, but the same benefit event cannot be credited multiple times.

## 11. Governance and authorization

Governance is federated and layered:
- member constitutional rights and charter changes;
- one-member/one-vote or another explicitly chosen democratic rule for membership matters;
- capital-provider rights limited to contractual economic rights;
- elected/delegated boards with revocable mandates;
- technical committees with published scope;
- independent audit and risk roles;
- conflict-of-interest declarations and recusal;
- appeals, dispute resolution and emergency powers with expiry.

Economic voting must not silently convert into ownership rights. Token holdings must not automatically grant unlimited control over member property, personal data or essential services.

Authorization checks must include role, jurisdiction, policy version, value threshold, risk tier, quorum/approval, segregation of duties and kill switch. The optimizer has no private key or payment credential.


### 11.1 Institutional decision chain

EIIOM is a planning core, not an investment committee. A major project moves through:
- read-mostly project observatory and evidence baseline;
- EIIOM scenario/portfolio recommendation;
- technical domain review;
- independent economic underwriting;
- legal and jurisdictional opinion;
- risk and environmental/social review where material;
- authorized investment committee decision;
- regulated execution and settlement;
- delivery evidence and post-investment audit.

Project SPVs or bounded project perimeters should make assets, debt, equity, contracts, offtake, insurance and cashflow waterfalls explicit. Project sponsors cannot be the only evidence source.

Public capital is primarily catalytic: common infrastructure, R&D, standards, certification, or narrowly justified first-loss support. Guarantees are contingent liabilities; lifecycle OPEX and maintenance must be funded. PPP is justified only when risks are allocated to parties able to manage them, and availability payments depend on service/quality evidence.

## 12. AI and optimization stack

### Model roles

- **EIIOM:** resource/production/investment allocation under explicit constraints.
- **V6.4–V6.5.6:** network coordination, liquidity and resilience research policies.
- **V7:** event/production/cash/evidence substrate and planning kernels.
- **AI-CFO:** entity-level forecasts, liquidity, working capital and reporting.
- **NEXUS / AI Council:** analysis, critique, scenario review and policy recommendations.
- **Human/authorized institutions:** approvals and execution.

### Solver outputs must include

- input snapshot IDs and evidence statuses;
- model and code version;
- objective components and Pareto alternatives;
- constraints, binding constraints and slack;
- infeasibility explanation;
- solver status, gap and runtime;
- scenario weights and calibration source;
- sensitivity and out-of-sample performance;
- decision authority required before execution.

A solver may not convert scenario assumptions into observed facts or authorize its own recommendation.


### 12.1 Current EIIOM implementation boundary

The repository's executable `src/eiiom_optimizer.py` is a reference LP allocation model. The much broader EIIOM V4 stochastic spatial MILP described in `docs/23_EIIOM_V4_STOCHASTIC_MILP.md` is a target specification, not an implemented production optimizer. SUES must not report planned variables, scenario-tree logic, non-anticipativity or full commodity/resource balance as already deployed.

## 13. Unified optimization objective

Do not compress the economy into one unreviewable scalar. Use a constrained multi-objective formulation:

`maximize (essential_service, external_value_added, productivity, resilience, innovation, welfare)`

subject to:
- physical material and capacity balances;
- cash and solvency constraints;
- debt, collateral and maturity limits;
- minimum essential-service levels;
- labor, safety and ecological constraints;
- ownership and contractual rights;
- jurisdictional and authorization constraints;
- distributional fairness and concentration safeguards.

Produce a Pareto frontier and explain trade-offs. Any weighted score must expose weights, stakeholder mandate and sensitivity.


### 13.1 Resilience and concentration policy

Stress must propagate through connected financial, physical, climate, digital and social dependencies. Report expected loss, VaR/CVaR, liquidity runway, concentration by supplier/country/grid/currency/customer/provider, recovery time and minimum essential-service levels.

A backup supplier or corridor may have negative standalone NPV but positive resilience option value. Household capital contributions must pause safely under income shocks. Trading/AMM/token research is never a base funding assumption for essential production. A core project must remain solvent if trading P&L, arbitrage spreads and speculative token marks fall to zero.

## 14. Integration map from current repository

| Existing model | SUES destination | Integration method |
|---|---|---|
| Seven-sector economy | Physical Economy + Investment | Typed sector/resource/product adapters |
| Productivity Flywheel V1–V3 | Innovation + Capital + Resilience | Cohort and reinvestment events; de-duplicated benefit events |
| Sector Optimizer V4 / EIIOM | Optimization | Common Money/Quantity/Period/Evidence inputs |
| V6.4 | Physical Economy + Market | Recipe/capacity/stock adapter; preserve paired environment |
| V6.5.3 | Trade + Capital & Risk | Invoice-level cashflow adapter; fees and loss decomposition |
| V6.5.4–V6.5.6 | Resilience | Repair/liquidity action interface; replace heuristic scores with counterfactual values |
| V7 Core | Economic Graph + Events | Replace in-memory prototype with durable event platform later |
| V7.2–V7.3 | Accounting + Trade + Evidence | Journal/subledger bridge and realization chain |
| V7.4–V7.6.6 | Production + Capital & Risk | Planner input builder from verified ledgers |
| V7.7–V7.8 | Optimization | Generalize to multi-product/multi-period non-anticipative model |

No legacy model is deleted. Each is versioned, wrapped, tested and compared against its original outputs.

## 15. Implementation roadmap

### Phase A — Foundation
Typed contracts, entity-scoped double-entry journal, atomic batch posting, physical-flow dimensions, benefit attribution, intercompany matching/elimination, bank reconciliation, FX translation, typed AR/AP subledger and FIFO inventory. **In progress in SUES V1 research branch.**

### Phase B — Subledger integration
Complete the AR/AP and FIFO inventory kernels; then add GRNI matching, BOM consumption, production output capitalization, fixed assets, payroll/tax, loans, supplier commitments, collateral and bank feeds reconciled to the journal.

### Phase C — Economic graph and event platform
Durable events, signatures, bitemporal state, stable IDs, replay, projections, access controls and independent checkpoints.

### Phase D — Unified enterprise model
Production, demand, contracts, inventory, payments and cash are connected for one pilot enterprise.

### Phase E — Network and federation
Several enterprises, cooperatives and shared suppliers operate through reciprocal contracts, intercompany eliminations and mutual-credit/clearing pilots.

### Phase F — Integrated optimizer
Multi-product, multi-period, multi-location production MILP with cash, credit, collateral, supplier lead times, non-anticipativity and robust stress.

### Phase G — Independent validation and scale
Real data calibration, privacy review, legal review, cybersecurity, external audit, shadow mode and limited controlled deployment.

## 16. Production-readiness gates

SUES is not production-ready until:
- all subledgers reconcile to a balanced general ledger;
- bank opening/movement/closing and ledger cash balances reconcile;
- intercompany eliminations are reciprocal, period- and currency-specific;
- physical material, inventory and capacity balances conserve;
- benefit attribution cannot double count across projects or model families;
- data is permissioned, source-attributed and versioned;
- events are durable, signed and replayable;
- model outputs are reproducible and out-of-sample validated;
- legal, financial, privacy and security controls are independently reviewed;
- authorization is segregated from model execution;
- rollback, incident response and disaster recovery are tested.

**The architecture is a research target, not a claim of a deployed economy, licensed financial institution or validated economic forecast.**
