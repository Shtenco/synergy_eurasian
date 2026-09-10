# SYNERGY EURASIAN — EIIOM-2045 / Real Economy OS

> **Евразийская интеллектуально-производственная система**: семья → капитал → наука → энергия → материалы → compute → AI → промышленность → сельское хозяйство → жильё → логистика → экспорт → проверяемый cashflow → новый капитал.

**Current architecture:** EIIOM-v4 Federation MegaSystem  
**Runnable coarse optimizer:** EIIOM-v2 LP  
**v4 status:** `MODEL_SPEC_READY / DATA_CALIBRATION_PENDING`  
**Federation:** 45 technical repositories + `synergy_project` master dossier  
**Role of this repository:** canonical **Real Economy OS**

---

## 1. Идея

`synergy_eurasian` должен отвечать не на вопрос «какую отрасль объявить приоритетной», а на более строгий вопрос:

> **Куда направить следующий капитал, в каком месте и в какой последовательности, чтобы получить максимальный прирост проверяемой реальной стоимости при ограничениях энергии, сетей, материалов, воды, кадров, жилья, логистики, спроса, финансирования и риска?**

Главный цикл:

```text
OBSERVED DEMAND + REAL RESOURCES
              ↓
      EIIOM ECONOMIC COMPILER
              ↓
         PROJECT FACTORY
              ↓
        ProjectProposal
              ↓
UNDERWRITING / HUMAN / REGULATORY AUTHORIZATION
              ↓
         REAL SETTLEMENT
              ↓
           REAL ASSET
              ↓
       GOODS / SERVICES
              ↓
       PAYING CUSTOMERS
              ↓
     SETTLEMENT EVIDENCE
              ↓
         FINANCIAL OS
              ↓
      CASH / HardNAV / DELTA
              ↓
         REINVESTMENT
              ↺
```

---

# 2. Четыре масштаба одной экономики

## L0 — Человек / семья

```text
Income - NecessaryExpenses = Delta
```

Сначала резерв и финансовая устойчивость. Затем диверсифицированный капитал и только допустимая часть свободной Дельты — в долгосрочные productive instruments.

## L1 — Бизнес / проект

```text
ExternalRevenue
- OPEX
- Taxes
- DebtService
- Maintenance
= BusinessDelta
```

## L2 — Регион / кластер

Энергия + grid + water + labor + housing + logistics + suppliers + industry + data.

## L3 — ЕАЭС / Евразия / внешний мир

Cross-border value chains, transport corridors, trade, FX, project finance, external markets and external cashflow.

Единая идея Дельты масштабируется от семьи до whole-system capital allocation.

---

# 3. Пять стран — динамическая сеть

| Страна | Стартовые portfolio hypotheses |
|---|---|
| Россия | energy/grid, heavy engineering, industrial AI, machine tools, robotics, materials, large industrial/agro scale |
| Казахстан | materials/refining, uranium/copper downstream, dryland AI-agro, water, logistics, selective compute |
| Беларусь | machine tools, robotics, agricultural machinery, industrial automation, food processing |
| Армения | AI/software/math, semiconductor/EDA design, science commercialization, high-value agriculture |
| Кыргызстан | hydro/water, mountain agriculture, processing, edge AI, rural clusters, new logistics connectivity |

Это **не фиксированное политическое разделение труда**.

В v4:

```text
Suitability[country, sector, time, scenario]
 = f(power, grid, logistics, skills, wages/productivity,
     water, suppliers, finance, market access, law, risk)
```

Специализация должна меняться вместе с реальной экономикой.

---

# 4. 35 value-chain domains

v4 расширяет 24 LP-сектора до полноценной карты:

1. generation;
2. grid;
3. industrial heat;
4. critical materials;
5. advanced materials;
6. power electronics;
7. machine tools;
8. robotics / Physical AI;
9. industrial AI / digital twins;
10. compute / data centers;
11. semiconductor / electronics design;
12. XPU / TURBO research;
13. Data Fabric;
14. SynergyNet;
15. NEXUS / agents;
16. cybersecurity / digital trust;
17. civil remote sensing;
18. agro genetics;
19. precision agriculture;
20. agro robotics;
21. water;
22. food processing;
23. chemicals / fertilizers / industrial inputs;
24. construction materials;
25. construction technology;
26. urban renovation;
27. rural AI settlements;
28. logistics;
29. MetaPay / trade infrastructure;
30. household finance;
31. SME / supplier finance;
32. education / training;
33. science / commercialization;
34. budget / procurement evidence;
35. circular + service economy.

Полная карта: [docs/26_SECTOR_AND_VALUE_CHAIN_MASTER_MAP.md](docs/26_SECTOR_AND_VALUE_CHAIN_MASTER_MAP.md)

---

# 5. Семь superchains

```text
POWER → GRID → POWER ELECTRONICS → INDUSTRY / COMPUTE

MATERIALS → MACHINE TOOLS → COMPONENTS → ROBOTICS → FACTORIES

POWER → COMPUTE → AI → DIGITAL TWINS → PHYSICAL PRODUCTIVITY

GENETICS → SEEDS → PRECISION FARMING → ROBOTICS → PROCESSING → FOOD EXPORT

CONSTRUCTION MATERIALS → RENOVATION / HOUSING → HUMAN CAPITAL → PRODUCTIVITY

FACTORY/FARM → LOGISTICS → CUSTOMS → METAPAY → EXTERNAL CUSTOMER → SETTLEMENT

SCIENCE → EVIDENCE → TRL → PILOT → PRODUCTION → EXPORT / LICENSING
```

---

# 6. EIIOM-v2: runnable coarse LP

Текущий рабочий solver остаётся воспроизводимым coarse model:

- 5 стран;
- 24 сектора;
- 3 фазы;
- 360 decision variables;
- power/grid/DC/compute dependencies;
- agriculture/housing constraints;
- concentration limits;
- versioned assumptions.

BASE-v2 research envelope:

| Метрика | Scenario output/target |
|---|---:|
| gross CAPEX 2026–2045 | $650bn |
| modeled annual GVA-equivalent 2045 | ~$160bn/y |
| compute | ~1.5 GW IT |
| urban renovation | 100m m² |
| rural swing housing | 8m m² |
| precision agriculture | 60m ha |
| deep agro-robotics | 15m ha |
| rural AI clusters | 160 |

**GVA-equivalent ≠ revenue ≠ cash ≠ NAV ≠ investor return.**

Run:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
python src/eiiom_optimizer.py --config config/base_scenario.json --output outputs/base
```

---

# 7. EIIOM-v4: stochastic spatial economic compiler

v4 introduces:

```text
countries
regions
physical nodes
candidate projects
commodities/services
transport/grid/data edges
time
uncertainty scenarios
household cohorts
financing instruments
labor skills
water basins
external markets
```

Decision families:

```text
BUILD[p,t] ∈ {0,1}
CAPADD[p,t]
FLOW[k,e,t,ω]
PROD[p,k,t,ω]
COMPUTE_ALLOC[workload,node,t,ω]
EQUITY / DEBT / CFA-RWA
HH_INVEST
P2P_LOAN
RENOVATE
TEMP_ASSIGN voluntary only
RND_STAGE
```

Objective concept:

```text
Expected Economic Value
- λ * CVaR
```

with explicit physical/social/legal constraints.

Specification: [docs/23_EIIOM_V4_STOCHASTIC_MILP.md](docs/23_EIIOM_V4_STOCHASTIC_MILP.md)

Scenario matrix: [config/scenarios_v4.json](config/scenarios_v4.json)

**No fake v4 optimum is published before spatial DATASET-v4 is calibrated.**

---

# 8. DATASET-v4 is the next main bottleneck

Every material record has two times:

```text
effective_time  — when it is true in the world
known_at        — when EIIOM could actually know it
```

This prevents economic lookahead bias.

Required dataset families:

- households/demography aggregates;
- labor/skills;
- industry/plants;
- trade/demand;
- energy/grid;
- compute/digital;
- materials;
- logistics;
- agriculture;
- water;
- housing/cities;
- finance;
- science/TRL;
- regulation.

Statuses are never collapsed:

```text
OBSERVED
COMMITTED
UNDER_CONSTRUCTION
PLANNED
ANNOUNCED
SCENARIO
```

See [docs/35_DATASET_V4.md](docs/35_DATASET_V4.md).

---

# 9. Real 2026 baseline

EIIOM is anchored to real external datasets, not only internal scenarios.

Current examples:

- EAEU mutual goods trade reached almost $100bn in 2024 according to EEC materials;
- the formal Eurasian Economic Pathway provides a 2030/2045 integration horizon;
- the EDB Eurasian Transport Network Observatory listed 402 planned/implemented transport projects worth about $345bn as of 1 July 2026, with about another $100bn in pipeline;
- future common electricity-market rules create a new potential cross-border power edge, but country/grid constraints remain physical.

All facts vs assumptions must be tagged.

See [docs/27_REALITY_BASELINE_2026.md](docs/27_REALITY_BASELINE_2026.md).

---

# 10. Project Factory

Grand strategy must become a project pipeline.

Mature capacity target:

```text
1000 raw opportunities
→ 400 qualified
→ 150 pre-feasibility
→ 60 investable candidates
→ 20–30 FID/funded projects
```

These numbers are operational scenario targets, not promises.

Every project passes:

```text
demand
→ resources
→ alternatives
→ technical concept
→ commercial evidence
→ finance
→ legal
→ evidence design
→ ProjectProposal
→ independent underwriting
```

See [docs/29_PROJECT_FACTORY_1000.md](docs/29_PROJECT_FACTORY_1000.md).

---

# 11. AI Agriculture

```text
germplasm
→ genomics / omics
→ phenotyping
→ soil/weather/management
→ G×E AI
→ cross ranking
→ controlled + field trials
→ official registration
→ seed multiplication
→ precision agriculture
→ agro-robotics
→ storage / processing
→ export
```

AI narrows the search. It **does not replace biology, field trials or official registration**.

See [docs/03_AI_AGRICULTURE.md](docs/03_AI_AGRICULTURE.md).

---

# 12. Housing / rural clusters

```text
Urban renovation candidate
→ voluntary temporary swing housing
→ renovation/reconstruction
→ legally protected return/replacement right
→ rural housing remains permanent useful asset
```

Hard social constraints:

- voluntary only;
- no housing-forced labor;
- return rights;
- services before occupancy;
- quality/area protection;
- accessibility and dispute procedure.

See [docs/05_HOUSING_RENOVATION.md](docs/05_HOUSING_RENOVATION.md).

---

# 13. Household capital / Delta / P2P

Household first:

```text
Income - NecessaryExpenses = Free Delta
```

Then:

```text
reserve → diversified capital → suitability-gated productive exposure
```

P2P layer uses independent savings tranches and maturity matching:

```text
savings tranche
→ productive SME/equipment credit
→ external customer revenue
→ principal + interest repayment
→ capital reuse
```

Principal is never income. New investor money is never operating return.

See:

- [docs/06_PEOPLES_CAPITAL_DELTA.md](docs/06_PEOPLES_CAPITAL_DELTA.md)
- [docs/19_P2P_MUTUAL_CREDIT_AND_CAPITAL.md](docs/19_P2P_MUTUAL_CREDIT_AND_CAPITAL.md)
- [docs/20_MULTI_SCALE_CAPITAL_FLYWHEEL.md](docs/20_MULTI_SCALE_CAPITAL_FLYWHEEL.md)

---

# 14. Financial engines around the real economy

SYNERGY federation has three external-value research engines:

### MIDAS

Bounded institutional trading intelligence. Only reconciled **realized external PnL** may enter accounting.

### MetaPay

Compliance-first FX/payment/route/settlement graph. A quote/spread is not profit until execution + settlement + reconciliation.

### Print Machine / AMM / QE research

Opportunity/liquidity amplifier only.

```text
mint != profit
internal AMM mark != HardNAV
flash principal != owned capital
bridge TVL != wealth
```

Real Economy OS never recognizes them directly. Financial OS is the economic judge.

See [docs/13_RESEARCH_PERIMETER.md](docs/13_RESEARCH_PERIMETER.md).

---

# 15. Productive Escrow / SYNA

These are **financing architecture specifications**, not functions executed in this repository.

Potential SYNA-CAP role:

```text
Eligible Audited Assets - Liabilities = Eligible NAV
NAV/unit = Eligible NAV / units outstanding
```

Own-token market cap is excluded from collateral.

Productive Escrow concept:

```text
verified milestone
→ external Financial OS review
→ bounded regulated liquidity authorization
→ real production/cashflow
→ repayment / sterilization
```

EIIOM itself cannot mint, release or self-authorize money.

See [docs/04_FINANCE_AND_SYNA.md](docs/04_FINANCE_AND_SYNA.md).

---

# 16. 46-repository federation

Machine-readable federation: [config/federation_v4.json](config/federation_v4.json)

Static audit:

```bash
python src/federation_audit.py --config config/federation_v4.json
```

Core authority separation:

```text
Architecture          → synergy_system
Real Economy          → synergy_eurasian
Accounting / HardNAV  → synergy_financial_os
Settlement            → synergy_pay_system
Science candidates    → nexus_science_agent
Transport             → synergynet
Runtime orchestration → synergy_meta_os
Trust commitment      → blockchain / metachain
```

Full map: [docs/17_FEDERATION_46_SYSTEM_MAP.md](docs/17_FEDERATION_46_SYSTEM_MAP.md)

---

# 17. Eight/nine canonical exchange objects

v4 standardizes cross-repository semantics:

```text
DemandSignal
ResourceState
TechnologyCandidate
ProjectProposal
CapitalAuthorization
PaymentIntent
SettlementReceipt
EvidencePackage
AccountingSnapshot
```

Schemas already included for:

- [interfaces/demand_signal.schema.json](interfaces/demand_signal.schema.json)
- [interfaces/resource_state.schema.json](interfaces/resource_state.schema.json)
- [interfaces/technology_candidate.schema.json](interfaces/technology_candidate.schema.json)
- [interfaces/project_proposal.schema.json](interfaces/project_proposal.schema.json)
- [interfaces/evidence_package.schema.json](interfaces/evidence_package.schema.json)

---

# 18. Digital infrastructure

```text
POWER / GRID
→ PHYSICAL COMPUTE
→ META-OS
→ DATA FABRIC
→ SYNERGYNET
→ AI SERVICES
→ PQ TRUST COMMITMENTS
```

SynergyNet moves evidence/data but has no financial authority. MetaChain commits already-authoritative bytes but does not determine economic truth. XPU/TURBO remain gated R&D until matched benchmarks.

See [docs/21_EURASIAN_DIGITAL_INFRASTRUCTURE.md](docs/21_EURASIAN_DIGITAL_INFRASTRUCTURE.md).

---

# 19. Science → industry

```text
question
→ sources
→ evidence graph
→ hypothesis
→ falsification
→ independent replication
→ laboratory
→ prototype
→ pilot
→ TRL
→ IP/FTO
→ economic pre-feasibility
→ ProjectProposal
→ commercial scale
```

See [docs/22_SCIENCE_TO_INDUSTRY_PIPELINE.md](docs/22_SCIENCE_TO_INDUSTRY_PIPELINE.md).

---

# 20. Eurasian geoeconomic grid

EIIOM does not assume frictionless geography. It explicitly models:

- Northern Eurasian routes;
- INSTC;
- Trans-Caspian / Middle Corridor;
- Central Asian connectors;
- air/high-value freight;
- digital corridors;
- external markets only where legally accessible.

Each edge contains capacity, transit time, cost, reliability and legal/compliance status.

See [docs/18_EURASIAN_GEOECONOMIC_GRID.md](docs/18_EURASIAN_GEOECONOMIC_GRID.md).

---

# 21. Human capital is physical infrastructure

Factory capacity is limited by:

- engineers;
- technicians;
- agronomists;
- AI/data talent;
- construction workforce;
- project finance/audit skills;
- housing/health/education/mobility.

EIIOM-v4 will calculate shadow value of critical skills just like shadow value of MW or water.

See [docs/25_HUMAN_CAPITAL_AND_SOCIAL_INFRASTRUCTURE.md](docs/25_HUMAN_CAPITAL_AND_SOCIAL_INFRASTRUCTURE.md).

---

# 22. Resilience before maximum base-case value

Stress universe includes:

- WACC/FX;
- energy/grid;
- compute supply;
- drought/water;
- logistics closures;
- cyber/bridge failures;
- labor shortages;
- household income shock;
- MIDAS zero/negative alpha;
- MetaPay spread disappearance;
- collapse of internal token marks.

Core economy must remain solvent without speculative engines.

See [docs/34_RESILIENCE_AND_STRESS_TESTING.md](docs/34_RESILIENCE_AND_STRESS_TESTING.md).

---

# 23. Control Tower

The dashboard follows causality:

```text
CAPITAL
→ PROJECT
→ CAPACITY
→ UTILIZATION
→ OUTPUT
→ SALES
→ SETTLEMENT
→ CASH/NAV
→ REINVESTMENT
```

Grey/insufficient evidence is never green.

See [docs/30_CONTROL_TOWER_AND_KPI.md](docs/30_CONTROL_TOWER_AND_KPI.md).

---

# 24. Non-negotiable economic constitution

```text
model != fact
forecast != evidence
GVA != cash
settlement != revenue
new investor capital != operating profit
mint != profit
own-token price != collateral
internal AMM mark != external PnL
flash principal != owned capital
bridge TVL != wealth
backtest != realized PnL
public announcement != commissioned capacity
AI recommendation != authorization
blockchain commitment != economic truth
project sponsor != independent verifier
```

And:

```text
EligibleRealAssets
  > ExternalLiabilities
  + StableLiabilities
  + QEOutstanding
```

One asset cannot collateralize multiple claims without explicit seniority and accounting.

---

# 25. Documentation map

Core v1/v2 foundations:

- [00 Context & Vision](docs/00_CONTEXT_AND_VISION.md)
- [01 System Architecture](docs/01_SYSTEM_ARCHITECTURE.md)
- [02 EIIOM Model](docs/02_EIIOM_MODEL.md)
- [03 AI Agriculture](docs/03_AI_AGRICULTURE.md)
- [04 Finance & SYNA](docs/04_FINANCE_AND_SYNA.md)
- [05 Housing Renovation](docs/05_HOUSING_RENOVATION.md)
- [06 People's Capital / Delta](docs/06_PEOPLES_CAPITAL_DELTA.md)
- [07 Investor UX](docs/07_INVESTOR_UX.md)
- [08 Governance / Risk / Compliance](docs/08_GOVERNANCE_RISK_COMPLIANCE.md)
- [09 Roadmap 2026–2045](docs/09_ROADMAP_2026_2045.md)
- [10 Sources & Assumptions](docs/10_SOURCES_AND_ASSUMPTIONS.md)
- [11 Investment Positioning](docs/11_INVESTMENT_POSITIONING.md)
- [12 Project Archetypes](docs/12_PROJECT_ARCHETYPES.md)
- [13 Research Perimeter](docs/13_RESEARCH_PERIMETER.md)
- [14 Crowd-Investment Lessons](docs/14_CROWD_INVESTMENT_LESSONS.md)
- [15 Developer Guide](docs/15_DEVELOPER_GUIDE.md)
- [16 Regulatory Snapshot](docs/16_CROWD_INVESTMENT_REGULATORY_STATUS.md)

Federation v4:

- [17 Federation 46 Map](docs/17_FEDERATION_46_SYSTEM_MAP.md)
- [18 Geoeconomic Grid](docs/18_EURASIAN_GEOECONOMIC_GRID.md)
- [19 P2P Mutual Credit](docs/19_P2P_MUTUAL_CREDIT_AND_CAPITAL.md)
- [20 Multi-Scale Capital Flywheel](docs/20_MULTI_SCALE_CAPITAL_FLYWHEEL.md)
- [21 Digital Infrastructure](docs/21_EURASIAN_DIGITAL_INFRASTRUCTURE.md)
- [22 Science → Industry](docs/22_SCIENCE_TO_INDUSTRY_PIPELINE.md)
- [23 Stochastic Spatial MILP](docs/23_EIIOM_V4_STOCHASTIC_MILP.md)
- [24 Financial Market / Settlement](docs/24_EURASIAN_FINANCIAL_MARKET_AND_SETTLEMENT.md)
- [25 Human Capital](docs/25_HUMAN_CAPITAL_AND_SOCIAL_INFRASTRUCTURE.md)
- [26 Sector Master Map](docs/26_SECTOR_AND_VALUE_CHAIN_MASTER_MAP.md)
- [27 Reality Baseline 2026](docs/27_REALITY_BASELINE_2026.md)
- [28 Institutional Design](docs/28_INSTITUTIONAL_DESIGN.md)
- [29 Project Factory 1000](docs/29_PROJECT_FACTORY_1000.md)
- [30 Control Tower / KPI](docs/30_CONTROL_TOWER_AND_KPI.md)
- [31 Execution Roadmap](docs/31_V4_EXECUTION_ROADMAP.md)
- [32 Climate / Energy / Water](docs/32_CLIMATE_ENERGY_WATER_SECURITY.md)
- [33 Public Investment / Budget OS](docs/33_PUBLIC_INVESTMENT_AND_BUDGET_OS.md)
- [34 Resilience / Stress](docs/34_RESILIENCE_AND_STRESS_TESTING.md)
- [35 DATASET-v4](docs/35_DATASET_V4.md)
- [36 Grand Strategy 2045](docs/36_GRAND_STRATEGY_2045.md)
- [37 Country Portfolios](docs/37_COUNTRY_PORTFOLIOS.md)

---

# 26. Current execution target

The next real bottleneck is:

```text
DATASET-v4
→ 3 pilot regions
→ ≥50 real physical/economic nodes
→ ≥100 edges
→ ≥20 real project candidates
→ first spatial stochastic solve
→ 3 end-to-end ProjectProposal/Evidence traces
```

See [docs/31_V4_EXECUTION_ROADMAP.md](docs/31_V4_EXECUTION_ROADMAP.md).

---

# 27. North Star

```text
REAL ECONOMY
+ VERIFIABLE POINT-IN-TIME DATA
+ PROJECT FACTORY
+ CANONICAL ACCOUNTING
+ BOUNDED AI
+ HUMAN GOVERNANCE
+ MULTI-CURRENCY SETTLEMENT
+ RESILIENT INFRASTRUCTURE
+ CRYPTOGRAPHIC EVIDENCE
= SYNERGY EURASIAN
```

**Status:** R&D / architecture / simulation / sandbox candidate. Nothing in this repository is an offer of securities, guarantee of return, monetary authorization or substitute for national law and regulation.
