# 29 — Project Factory: как превратить master-plan в 1000 проверяемых проектов

## Цель

Макроархитектура не создаёт производство сама. Нужен конвейер, который ежегодно превращает тысячи идей в десятки готовых к финансированию проектов.

Цель `Project Factory` — не обещать построить 1000 объектов, а создать pipeline, способный **обработать ≥1000 кандидатов, отбросить слабые и довести лучшие до investment-ready состояния**.

## Воронка

Иллюстративная годовая capacity target:

```text
1000 raw opportunities
  ↓ data screen
400 qualified opportunities
  ↓ pre-feasibility
150 pre-feasibility packages
  ↓ technical / market / legal gates
60 bankable / investable candidates
  ↓ financing / permits / evidence
20–30 FID / funded projects
  ↓ construction / deployment
operating evidence
```

Процент отсева — признак качества, а не провала.

## Источники opportunities

### Demand mining

- импортные категории;
- дефициты поставщиков;
- крупные B2B закупки;
- EAEU mutual trade;
- export demand;
- procurement;
- logistics bottlenecks;
- energy connection queues;
- industrial maintenance data;
- agriculture input gaps.

### Bottom-up proposals

- предприятия;
- предприниматели;
- университеты;
- регионы;
- technology teams;
- cooperatives;
- households/community groups for local infrastructure.

### Science candidates

Из `Science → Industry Pipeline` после TRL/evidence gate.

### Infrastructure observatories

Например реальные project registries/observatories могут поставлять competing or complementary assets.

## Stage 0 — Opportunity Card

Минимальный объект:

```text
opportunity_id
problem
customer/demand
location
sector
estimated scale
why now
possible alternatives
source evidence
```

Никаких NPV «с потолка».

## Stage 1 — Data Screen

EIIOM автоматически проверяет:

- market size;
- imports / external demand;
- existing competitors;
- power;
- grid;
- water;
- land;
- logistics;
- labor;
- main inputs;
- legal blockers;
- rough CAPEX range.

Output:

```text
DROP
WATCH
PRE_FEASIBILITY
```

## Stage 2 — Pre-Feasibility

Обязательно сравнить минимум с одной альтернативой:

```text
build local
vs import
vs retrofit existing plant
vs contract manufacturing
vs do nothing
```

Project score без alternative case недействителен.

## Stage 3 — Technical Concept

- process flow;
- equipment list;
- material balance;
- energy balance;
- staffing;
- construction schedule;
- technology readiness;
- supplier options;
- commissioning plan.

## Stage 4 — Commercial Case

- customer interviews;
- LOI/offtake;
- price curve;
- volume curve;
- substitutes;
- export route;
- receivables terms;
- working capital.

High upstream CAPEX requires stronger offtake evidence.

## Stage 5 — Finance Case

```text
sources & uses
cashflow
WACC
DSCR
LTV
break-even utilization
FX mismatch
working capital
stress case
liquidation/recovery
```

## Stage 6 — Legal / Regulatory

- land/title;
- licenses;
- permits;
- securities/CFA if used;
- environmental;
- labor;
- data;
- cross-border trade;
- sanctions/compliance where relevant.

## Stage 7 — Evidence Design

До финансирования определить, чем будет доказан каждый milestone.

Example:

```text
M1 land/site control
M2 grid connection
M3 foundation/building
M4 equipment delivery
M5 mechanical completion
M6 commissioning
M7 first commercial output
M8 first external settlement
M9 stable operation
```

Для каждого:

- evidence type;
- independent verifier;
- acceptance threshold;
- release consequence.

## Stage 8 — ProjectProposal

Только после предыдущих стадий candidate экспортируется в канонический `ProjectProposal`.

## Stage 9 — Underwriting / Capital Authorization

Внешняя authority. EIIOM не может self-approve.

## Stage 10 — Build / Operate / Learn

После запуска фактические данные возвращаются в dataset:

```text
estimated CAPEX vs actual
estimated schedule vs actual
estimated output vs actual
estimated revenue vs actual
risk predicted vs realized
```

Это обучает **экономическую модель на собственных ошибках**.

## Project classes

### Fast productivity projects

CAPEX: малый/средний; 6–36 месяцев.

- industrial AI;
- retrofit;
- power-efficiency;
- automation;
- precision agriculture;
- warehouse/logistics optimization.

### Mid-scale industrial projects

- power electronics;
- processing;
- machine tools;
- robotics;
- cold chain;
- regional DC/inference.

### Infrastructure projects

- grid;
- generation;
- transport;
- water;
- renovation;
- large compute.

### Science option projects

Финансируются только до следующего evidence gate.

## Portfolio construction

Не позволять 1000 проектов стать 1000 независимыми island investments.

EIIOM группирует их в value chains:

```text
Power cluster
Materials cluster
Compute/AI cluster
Machine/robotics cluster
Agro/food cluster
Housing/construction cluster
Logistics/export cluster
```

Проект получает дополнительную ценность, если снимает bottleneck у нескольких других проектов.

## Bottleneck multiplier

Концептуально:

```text
SystemUnlockValue[p]
 = Σ downstream project value unlocked by project p
```

Трансформаторный завод с умеренной собственной маржой может оказаться ценнее высокомаржинального SaaS, если без него не подключаются десятки крупных объектов.

## Stop-loss for CAPEX

Каждый проект обязан иметь termination gates.

```text
if cost_overrun > threshold
or demand collapses
or technology fails
or permit impossible
or financing unavailable
→ STOP / RESCOPE / SELL
```

Sunk-cost fallacy не является инвестиционной стратегией.

## Project memory

Для каждого закрытого/отклонённого проекта сохранять:

- why rejected;
- what data were wrong;
- what assumption failed;
- whether condition may change.

Через несколько лет это становится уникальным dataset capital allocation.

## KPI Project Factory

Не только число проектов:

- ideas screened;
- rejection rate;
- time-to-pre-feasibility;
- forecast error CAPEX;
- forecast error demand;
- percentage projects with signed offtake;
- FID rate;
- construction overrun;
- default rate;
- external revenue after commissioning;
- value unlocked in other projects;
- capital saved by early rejection.

## Ultimate output

`Project Factory` превращает EIIOM из доклада в непрерывную машину:

```text
DATA → OPPORTUNITY → PROJECT → EVIDENCE → CASHFLOW → LEARNING → BETTER PROJECT
```
