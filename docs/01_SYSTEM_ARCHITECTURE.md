# 01 — System Architecture

## Назначение `synergy_eurasian`

Этот репозиторий — **Real Economy OS**. Его ответственность:

1. описывать физические производственные цепочки;
2. хранить проверяемые baseline/assumption данные;
3. оптимизировать CAPEX;
4. формировать `ProjectProposal`;
5. принимать/проверять `EvidencePackage`;
6. считать физический output, GVA-equivalent и ограничения;
7. передавать предложения во внешний Financial OS.

Он **не**:

- минтит деньги/токены;
- выдаёт инвестиционные лицензии;
- считает собственный токен активом, обеспечивающим самого себя;
- принимает модельный GDP/GVA за денежную выручку;
- сам одобряет финансирование созданных им проектов.

## Пять колец СИНЕРГИИ

### Ring 1 — Applications

- AI-CFO / «Моя Дельта»;
- citizen/investor dashboard;
- project cockpit;
- factory/farm/renovation dashboard;
- project marketplace;
- public evidence explorer.

### Ring 2 — AI OS

`AUTOPILOT + NEXUS`

Функции:

- forecast;
- optimization;
- anomaly detection;
- project ranking;
- digital twins;
- industrial control recommendations;
- crop/seed ranking;
- capital allocation.

AI всегда bounded: критические финансовые, социальные и юридические решения требуют policy gates и человеческой авторизации.

### Ring 3 — Economic OS

`Financial OS + MetaPay`

Отдельный контур:

- underwriting;
- risk books;
- CFA/RWA issuance adapters;
- settlement;
- canonical accounting;
- collateral registry;
- liabilities;
- cash management.

### Ring 4 — Infrastructure OS

`Meta-OS + SynergyNet`

- compute;
- data centers;
- storage;
- edge nodes;
- industrial telemetry;
- secure communications;
- inter-cluster networking.

### Ring 5 — Trust Layer

`Synergy System + AI Blockchain / PQ chain`

- identity;
- evidence hashes;
- audit trails;
- approvals;
- asset registry proofs;
- post-quantum-ready signatures where technically and legally appropriate;
- governance history.

## Research perimeter

`MIDAS`, bridge/arbitrage, token experiments, QE simulators, TURBO, Info Graph и иные исследовательские модули могут поставлять сигналы или капитал во внешний Financial OS, но **не имеют прямого write-access к Real Economy truth**.

## Canonical data flow

```text
Observed baseline
   ↓
Input-Output Graph
   ↓
EIIOM optimizer
   ↓
ProjectProposal
   ↓
Independent technical/economic review
   ↓
Financial OS underwriting
   ↓
Human/regulatory authorization
   ↓
Settlement / MetaPay
   ↓
Construction / deployment
   ↓
EvidencePackage
   ↓
Commissioning verification
   ↓
Real output / external cashflow
   ↓
Canonical accounting / NAV
```

## Trust rule

Модель может рекомендовать проект, но не может сама доказать, что он построен. Доказательством являются внешние данные: акты ввода, telemetry, счета, фото/видео с provenance, независимый аудит, банковский cashflow, экспортные документы, meter readings и иные допустимые evidence sources.

## Core invariants

```text
INV-01: ModeledValue != Cash
INV-02: TokenMarketCap != EligibleNAV
INV-03: Asset cannot collateralize two liabilities simultaneously
INV-04: Project release requires external evidence
INV-05: AI cannot bypass human/regulatory authorization
INV-06: Revenue must originate from a real counterparty or legally recognized asset cashflow
INV-07: Bridge arbitrage is PnL/liquidity, not synthetic creation of NAV
INV-08: Social relocation must be voluntary
INV-09: No project may hide its liabilities outside canonical accounting
INV-10: Every optimization run is reproducible from versioned assumptions
```

## North Star

```text
REAL ECONOMY
+ VERIFIABLE DATA
+ CANONICAL ACCOUNTING
+ BOUNDED AI
+ HUMAN GOVERNANCE
+ SETTLEMENT
+ CRYPTOGRAPHIC EVIDENCE
= SYNERGY
```
