# 20 — Multi-Scale Capital Flywheel: семья → бизнес → регион → Евразия

## Главная идея

В ранней версии СИНЕРГИИ «Дельта» была персональной формулой. В v4 она становится **универсальной экономической операцией** на каждом уровне.

## L0 — Household Delta

```text
Δ_household = Income - NecessaryExpenses - DebtService
```

После minimum reserve:

```text
Δ_household → savings + diversified capital + productive project exposure
```

Цель: рост чистого капитала семьи, а не максимизация комиссий платформы.

## L1 — Business Delta

```text
Δ_business = ExternalRevenue - CashOPEX - Taxes - DebtService - MaintenanceCAPEX
```

Далее:

```text
Δ_business → reserve + working capital + productivity CAPEX + dividends
```

## L2 — Project Delta

```text
Δ_project = RealizedOperatingCashflow
            - senior debt service
            - lifecycle reserve
            - required maintenance
```

Только после этого возникает distributable/reinvestable capacity.

## L3 — Regional Economic Delta

Это не бухгалтерская прибыль региона, а planning metric:

```text
Δ_region =
  NewExternalSales
+ ImportSubstitutionValueAdjustedForInputs
+ ProductivitySavings
+ NetInvestmentIncome
- ImportedInputs
- FinancingCost
- InfrastructureLifecycleCost
- ExpectedLosses
```

Нельзя считать transfer payments или внутренний оборот между местными компаниями дважды.

## L4 — EAEU / System Delta

```text
VerifiedSystemDelta =
    ExternalExportCashflow
  + RealizedMetaPayPnL
  + RealizedMIDASPnL
  + RealizedOtherExternalInvestmentIncome
  + ExternalCapitalGainsRealized
  - ExternalImportPayments
  - ExternalFinancingCost
  - ExternalLosses
  - LifecycleConsumptionOfCapital
```

`VerifiedSystemDelta` и `GDP/GVA` — разные метрики.

## Два двигателя роста капитала

### Financial Loop

```text
capital
  → MetaPay / MIDAS / external investment sleeves
  → externally realized PnL
  → Financial OS
  → reserves / reinvestment
```

### Productive Loop

```text
capital
  → EIIOM project
  → physical capacity
  → goods/services
  → external/internal paying customers
  → operating cashflow
  → Financial OS
  → reinvestment
```

**Главный долгосрочный двигатель — Productive Loop.** Financial Loop ускоряет накопление и ликвидность, но не должен становиться единственным источником жизнеспособности системы.

## Третий двигатель — Human Capital Loop

```text
education / health / housing / mobility
  → higher productivity
  → higher household/business Delta
  → more savings + tax base + entrepreneurship
  → more education / productive capital
```

Это устраняет ошибку, при которой социальные расходы рассматриваются только как «издержка».

## Четвёртый двигатель — Science/IP Loop

```text
research
  → reproducible evidence
  → IP / engineering know-how
  → industrial deployment
  → productivity/export
  → royalty / margin / tax / reinvestment
  → next research
```

## Пятый двигатель — Demand-to-Localization Loop

```text
Business OS / MetaPay trade data / import data
  → persistent demand gap
  → EIIOM localization candidate
  → local supplier network
  → production
  → lower delivered cost / higher resilience
  → larger market share
```

Смысл: торговля становится сенсором для индустриализации.

## Capital stack by stage

### Seed stage

```text
founder/strategic capital
+ grants/R&D
+ catalytic public/development capital
+ limited retail instruments where legally allowed
```

### Construction stage

```text
equity
+ project debt
+ equipment/vendor finance
+ offtake prepayments
+ infrastructure support
+ CFA/RWA/bonds if lawful
```

### Operating stage

```text
operating cashflow
+ refinancing
+ retained earnings
+ institutional capital
```

### Scale stage

```text
reinvestment
+ larger debt markets
+ listed/private capital
+ export-credit finance
+ cross-border co-investment
```

## Leverage firewall

Цель — не максимальный debt/assets. Использовать dynamic debt capacity:

```text
DebtCapacity = min(
  DSCR_limit,
  LTV_limit,
  stress_cashflow_limit,
  currency_mismatch_limit,
  maturity_limit,
  legal_limit
)
```

### DSCR

```text
DSCR = CashAvailableForDebtService / DebtService
```

Project cannot use BASE-case only; stress DSCR is mandatory.

## Reinforcement without reflexivity

Допустимый positive feedback:

```text
RealAsset↑
→ ExternalCashflow↑
→ AuditedNAV↑
→ FinancingCapacity↑
→ MoreRealAssets↑
```

Недопустимый reflexive loop:

```text
OwnTokenPrice↑
→ collateral mark↑
→ more mint↑
→ own token buyback↑
→ OwnTokenPrice↑
```

## Capital allocation objective

Не максимизировать одно число NPV. Использовать portfolio objective:

```text
Score =
    w1 * RiskAdjustedEconomicValue
  + w2 * ExternalCashflowPotential
  + w3 * ProductivityGain
  + w4 * StrategicBottleneckRelief
  + w5 * ResilienceValue
  + w6 * HumanCapitalEffect
  - w7 * TailRisk
  - w8 * ImportCriticality
  - w9 * FiscalBurden
  - w10 * Environmental/SocialDamage
```

Weights are policy/scenario inputs and must be explicit.

## Universal rule

На любом уровне:

```text
Income / external value
- real costs
- liabilities
= economic Delta

Delta
→ reserve
→ productive capital
→ larger future income
```

Это и есть единая формула СИНЕРГИИ от семьи до континента.
