# 28 — Institutional Design: как управлять системой без «единого сверхминистерства»

## Принцип

EIIOM — это не проект политической федерации. Поэтому институциональная архитектура должна работать поверх существующих государств, компаний и регуляторов.

Лучший базовый дизайн — **federated project system**.

## Уровни

### 1. Eurasian Project Observatory

Read-mostly слой:

- реестр project candidates;
- реестр operating assets;
- baseline data;
- project status;
- evidence hashes;
- physical KPIs;
- public/non-public classification;
- source provenance.

Не выдаёт деньги.

### 2. EIIOM Planning Core

- scenario modelling;
- bottleneck analysis;
- marginal-capital ranking;
- corridor analysis;
- project portfolio optimization;
- shadow prices;
- stress tests.

Не одобряет инвестиции.

### 3. Domain Councils

Примерные домены:

- energy/grid;
- compute/digital;
- industrial automation;
- materials;
- agriculture/water;
- logistics;
- housing/construction;
- human capital;
- science/IP.

Их функция — техническая экспертиза, а не бухгалтерская власть.

### 4. Financial Underwriting Layer

Канонический контур SYNERGY Financial OS + реальные банки/фонды/инвесторы.

- project cashflow;
- debt capacity;
- equity;
- security/collateral;
- covenants;
- expected loss;
- liquidity;
- investor suitability;
- authorization.

### 5. National Regulatory Layer

Каждая операция остаётся в юрисдикции:

- securities/CFA;
- banking;
- payments;
- currency control;
- AML/KYC;
- construction;
- energy;
- environmental law;
- labor;
- data protection;
- agriculture/seed regulation.

EIIOM cannot override law.

### 6. Independent Evidence & Audit Network

Разделить:

- engineering verifier;
- financial auditor;
- valuation agent;
- environmental/social verifier;
- data/evidence integrity.

Project sponsor не может быть единственным источником evidence.

## Project SPV principle

Крупный проект по возможности изолируется в отдельный SPV/project perimeter:

```text
ProjectSPV
  Assets
  Debt
  Equity
  Contracts
  Offtake
  Insurance
  Evidence
  Cashflow waterfall
```

Это позволяет видеть:

- кто кому должен;
- чем обеспечен долг;
- где находится cash;
- кто несёт construction/market risk;
- что именно принадлежит инвестору.

## Cross-border consortium

Проект в нескольких странах:

```text
Lead SPV / Consortium Agreement
  ├─ Country A project company
  ├─ Country B supplier company
  ├─ Country C logistics company
  └─ Common data/evidence standard
```

Не требуется один юридический супер-SPV на весь ЕАЭС, если местное право делает это неэффективным.

## Capital committee

Рекомендуемый decision stack:

```text
EIIOM score
+ technical opinion
+ independent economic underwriting
+ legal opinion
+ risk opinion
+ environmental/social opinion where material
→ Investment Committee
```

Для public/crowd instruments добавляются retail disclosure and suitability gates.

## Conflict-of-interest register

Для каждого decision maker:

```text
person/entity
project relation
equity relation
supplier relation
family/related-party relation
fee relation
recusal status
```

AI ranking не устраняет конфликт интересов; он только делает часть расчётов прозрачнее.

## Procurement design

Большие проекты не должны автоматически создавать закрытого поставщика.

Модель:

```text
technical specification
→ supplier qualification
→ competitive bid / framework
→ total lifecycle cost
→ performance bond / warranty
→ delivery evidence
```

Для critical technology может быть strategic sourcing, но его исключение должно быть явно обосновано.

## Public-private partnership

PPP целесообразен там, где существует:

- долгий срок;
- публичная инфраструктурная функция;
- измеримый service output;
- частная operational capability;
- понятное распределение рисков.

Не каждый коммерческий завод должен быть PPP.

## Local ownership / participation

Для проектов, влияющих на жителей:

- публичные hearings/consultation where required;
- доступ к понятной project summary;
- grievance mechanism;
- local-benefit metrics;
- minority/local participation if legally and economically appropriate.

## Federation governance

SYNERGY technical federation follows:

```text
Architecture authority    → synergy_system
Real-economy proposals    → synergy_eurasian
Accounting authority      → synergy_financial_os
Settlement authority      → synergy_pay_system
Trust commitments         → blockchain/metachain
AI proposals              → NEXUS/Autopilot
```

No authority may silently absorb another.

## Emergency powers

Для критического инцидента:

- payment pause;
- project release pause;
- bridge quarantine;
- AI automation disable;
- evidence quarantine;
- manual fallback.

Emergency action must be logged, time-limited and reviewable.

## Institutional KPI

- project decision time;
- audit lag;
- percentage projects with independent evidence;
- procurement competition;
- cost overruns;
- delay rate;
- covenant breaches;
- default/loss rate;
- number of related-party exceptions;
- percentage of model recommendations rejected and why;
- number of projects stopped before wasting full CAPEX.

A system that never rejects projects is not an investment system; it is a promotional machine.
