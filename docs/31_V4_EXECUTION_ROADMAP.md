# 31 — EIIOM-v4 Execution Roadmap: 100 дней → 12 месяцев → 2030 → 2045

## Правило

Не начинать с «строительства Евразии». Начинать с доказуемого цифрового контура, который способен правильно отвергнуть плохой проект и правильно провести хороший проект от данных до cashflow.

---

# Первые 30 дней — Data & Authority Foundation

## 1. Заморозить contracts v1

Canonical exchange objects:

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

Для каждого:

- JSON Schema;
- owner authority;
- versioning;
- idempotency key;
- canonical hash profile;
- PII/security classification.

## 2. Dataset Registry

Создать machine-readable manifest минимум для:

- EAEU trade;
- industrial production;
- electricity generation;
- grid/substations where public;
- Eurasian transport projects;
- agriculture;
- water;
- housing;
- labor/skills;
- FX/WACC;
- external demand;
- project CAPEX references.

## 3. Baseline units

Единые единицы:

```text
USD_2026_real
MW / MWh / TWh
tonnes/year
m2
ha
m3 water
person-FTE
hours/days
```

## 4. Authority audit

Проверить 46-repo federation:

```text
one object → one authority
```

и убрать дублирование accounting/settlement/approval semantics.

---

# 31–60 дней — Spatial Graph MVP

## 5. Выбрать 3 пилотных региона

Не как политический рейтинг, а как data-rich testbed:

- один industrial/energy-heavy region;
- один agro/logistics-heavy region;
- один smaller high-skill/digital region.

Критерии:

- публичность данных;
- наличие реальных project candidates;
- разные bottlenecks;
- возможность проверить модель.

## 6. Собрать первые nodes

Минимум 50 real/candidate nodes:

```text
substations
power plants
factories
warehouses
farms
seed/trial sites
transport terminals
water nodes
housing blocks
universities
DC/compute sites
```

## 7. Собрать edges

```text
power
material
transport
water
data
labor mobility
cash/settlement
```

## 8. First spatial solve

Выдать:

- топ-20 project candidates;
- top-10 bottlenecks;
- shadow price power/grid/labor/water/logistics;
- rejected projects + reasons.

---

# 61–100 дней — End-to-End Project Proof

## 9. Три проекта разных типов

Пример классов:

1. industrial AI / retrofit — быстрый;
2. agro/logistics/processing — средний;
3. grid/housing/infrastructure — долгий.

## 10. Полный цифровой trace

Для каждого:

```text
DemandSignal
→ ResourceState
→ ProjectProposal
→ independent review
→ mock/sandbox CapitalAuthorization
→ mock PaymentIntent
→ EvidencePackage
→ AccountingSnapshot
```

Никакой live money не нужен для доказательства архитектуры.

## 11. Failure drill

Искусственно:

- сломать evidence;
- повысить WACC;
- снять power edge;
- закрыть export corridor;
- увеличить CAPEX;
- снизить demand;
- сделать data stale.

Система должна stop/rescope project, а не «оптимистично продолжать».

---

# 3–6 месяцев — Project Factory MVP

## 12. Opportunity intake

Подключить:

- Business/Growth OS;
- public import/trade data;
- industry proposals;
- universities;
- regional authorities;
- transport observatories;
- procurement/open data.

## 13. Capacity target

За полгода:

```text
300 opportunities screened
100 qualified
30 pre-feasibility
10 investment-ready candidates
```

Это operational target, not investment promise.

## 14. Control Tower

Запустить dashboard:

- project funnel;
- bottlenecks;
- forecast vs actual;
- financial authority states;
- evidence freshness;
- household/SME aggregate resilience;
- corridor status.

---

# 6–12 месяцев — Sandbox Federation

## 15. Financial OS integration

Реальный typed handoff:

```text
EIIOM ProjectProposal
→ Financial OS underwriting
→ CapitalAuthorization
```

## 16. MetaPay integration

Paper/shadow first:

```text
PaymentIntent
→ compliance/readiness
→ route
→ settlement simulation
→ receipt
→ reconciliation
```

## 17. SynergyNet / Data Fabric integration

Передавать:

- content-addressed evidence;
- manifests;
- model artifacts;
- project snapshots.

No financial authority escalation.

## 18. MetaChain proof-of-evidence

Anchor hashes of already-authoritative artifacts on testnet/research chain.

## 19. AI-CFO / household pilot

Non-custodial:

- income/expense categorization;
- Delta;
- reserve runway;
- goals;
- stress detection;
- no automatic risk investing.

---

# 2027–2030 — Demonstration Economic Network

## Real-world goals

- 100+ independently measured industrial AI deployments;
- first multi-region Project Factory;
- standardized project passport;
- standardized evidence package;
- first compliant CFA/RWA/project-finance integrations where available;
- first rural AI clusters;
- first renovation projects with voluntary swing model where socially/economically justified;
- first regional seed/genomics data federation;
- first cross-border supplier chains selected through EIIOM;
- integration of real Eurasian Transport Network projects as constraints/edges;
- common power-market mode when/if operative.

## What counts as success by 2030

Not spend target. Evidence target:

```text
≥80% operating projects publish fresh physical KPI evidence
CAPEX forecast error declining
schedule forecast error declining
external/operating cashflow measurable
no hidden double-collateral
no systemic dependence on new retail inflow
household reserve metrics not deteriorating because of project investing
```

---

# 2030–2040 — Scale

- hundreds/thousands of project nodes;
- common industrial/demand graph;
- large supplier-finance network;
- expanded digital twins;
- power/grid/materials bottleneck markets;
- large precision/agro-robotic footprint if unit economics validate;
- more CAPEX financed from retained productive cashflow;
- institutional investors become larger funding share than retail;
- multiple international logistics corridors modeled dynamically.

---

# 2040–2045 — Self-learning Economic Network

Target architecture:

```text
Observed Economy
  ↓ continuously
Digital Twin
  ↓
Stochastic EIIOM
  ↓
Project Factory
  ↓
Human/Institutional Decisions
  ↓
Real Economy
  ↓
Evidence + Accounting
  ↓
Forecast Error Learning
  ↺
```

System becomes useful not because it predicts everything, but because it continually updates from errors.

---

# Funding of the software/system layer

Не путать $650bn economic scenario with software budget.

Сам EIIOM/Federation platform should be built in stages:

```text
Architecture / data MVP
→ spatial pilot
→ sandbox integration
→ regulatory/industrial pilots
→ institutional platform
```

Each stage gets its own budget, KPIs and stop gate.

---

# Final 100-day definition of done

```text
[ ] all canonical schemas versioned
[ ] dataset registry created
[ ] 3 pilot regions selected by objective criteria
[ ] ≥50 physical/economic nodes
[ ] first spatial graph solved
[ ] ≥20 ranked project candidates
[ ] 3 end-to-end project traces
[ ] failure drills pass
[ ] CI green
[ ] no fake cash/NAV from modelled values
[ ] public fact vs model vs forecast labels enforced
```
