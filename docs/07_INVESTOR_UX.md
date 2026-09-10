# 07 — Investor UX / Community System

## Задача

Сделать из разового инвестора долгосрочного участника реальной производственной экосистемы, не превращая систему в MLM, обещание гарантированной доходности или зависимость от постоянного притока новых денег.

## Что полезно перенять из массовых crowd-investment систем

Полезные паттерны:

- сильная большая миссия;
- низкий психологический порог первого шага;
- понятные регулярные планы накопления;
- личный кабинет;
- roadmap;
- еженедельные/ежемесячные обновления;
- демонстрация физического прогресса;
- офлайн/онлайн встречи;
- экспертные сообщества;
- статусы участия;
- наставничество;
- многоязычность;
- возможность приносить не только деньги, но компетенции, клиентов, поставщиков, землю, оборудование, идеи.

Что **не переносится**:

- вознаграждение как процент от денег приведённого инвестора;
- обещания гарантированных дивидендов;
- «успей войти»;
- искусственный дефицит долей;
- непрозрачная внутренняя оценка;
- выплаты предыдущим участникам из взносов новых;
- давление при пропуске платежа;
- кредитное плечо домохозяйства ради покупки продукта.

## Лестница участия

```text
LEVEL 0 — Observer
  бесплатный AI-CFO / «Моя Дельта»

LEVEL 1 — Saver
  резерв + финансовая дисциплина

LEVEL 2 — Investor
  небольшой регулируемый project-CFA/RWA после suitability gate

LEVEL 3 — Portfolio Co-owner
  диверсифицированный портфель нескольких проектов

LEVEL 4 — Creator
  предложения проектов, клиентов, технологий, поставщиков

LEVEL 5 — Expert
  участие в domain councils по квалификации

LEVEL 6 — Ambassador
  образование/сообщество, без инвестиционного MLM

LEVEL 7 — Partner
  собственный бизнес/SPV внутри экосистемы после underwriting
```

## Commitment plan вместо «рассрочки на инвестицию»

Пользователь задаёт **цель накопления**, а не долг перед платформой:

```text
Goal: 120 000 ₽ productive portfolio
Horizon: 24 months
Suggested monthly saving: 5 000 ₽
```

Если доход падает:

```text
IncomeShock → contribution reduced or paused
Penalty = 0
```

Семья важнее инвестиционного плана.

## Personal dashboard

Каждый пользователь должен видеть:

### Family layer

- income;
- necessary expenses;
- Delta;
- reserve runway;
- debt load;
- long-term portfolio;
- SYNERGY allocation;
- next goals.

### Project layer

Для каждого инструмента:

```text
ProjectID
LegalIssuer
InstrumentType
InvestedAmount
CurrentEligibleValue
Seniority
RiskClass
Maturity
LiquidityRules
ProjectCompletion
PhysicalKPIs
LastEvidenceDate
CashflowStatus
AuditStatus
```

### Physical-progress feed

Не «ваш токен вырос», а:

- foundation complete;
- equipment delivered;
- 40 MW connected;
- first harvest completed;
- line reached 72% utilization;
- 15,000 m² renovated;
- export contract signed;
- external revenue received.

## Digital passport of participant

Показывает:

- years in system;
- capital contributed;
- number of projects;
- realized distributions;
- risk-adjusted portfolio;
- expertise contributed;
- verified economic bounties;
- governance reputation.

Физический сертификат может быть сувениром/идентификатором участия, но не создаёт дополнительных прав сверх юридического инструмента.

## Community flywheel

```text
Free AI-CFO
  ↓
Useful result for family
  ↓
Trust
  ↓
First small investment
  ↓
Visible physical progress
  ↓
Regular saving habit
  ↓
Portfolio diversification
  ↓
Expert/community participation
  ↓
Economic contribution beyond capital
  ↓
More real projects
```

## Referral / bounty policy

Разрешённое направление мотивации:

```text
Reward ∝ VerifiedEconomicValue
```

Например:

- новый B2B-клиент;
- qualified supplier;
- engineer/expert;
- внедрённая технология;
- экспортный контракт;
- снижение подтверждённых издержек;
- полезный open-source contribution;
- финансово-образовательный пользователь, который построил резерв.

Запрещённый дизайн:

```text
Reward ∝ AmountInvestedByRecruitedPerson
```

## Governance reputation

Голосование не должно быть чистым `1 token = 1 vote` для всех решений.

Концептуально:

```text
VotingPower = f(
  legally eligible capital rights,
  verified expertise,
  track record,
  affected-local-stake,
  conflict-of-interest limits
)
```

Примеры:

- агрономы получают expert weight в seed/agro review;
- инженеры — в industrial projects;
- жители района — в social design реновации;
- финансовый комитет — в risk/seniority;
- капитал влияет только там, где это предусмотрено юридическими правами инструмента.

## Коммуникационный принцип

Главное сообщение:

> **Миллионы маленьких Дельт — один большой производительный капитал.**

Но коммуникация всегда отделяет:

- миссию;
- сценарные цели;
- юридические права;
- ожидаемые метрики;
- фактические результаты.

Никогда не смешивать aspirational poster и investment disclosure.
