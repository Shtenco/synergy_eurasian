# 04 — Financing Architecture / SYNA / Productive Escrow

## Основной принцип

Финансовый слой СИНЕРГИИ должен **трансформировать** капитал, но не объявлять собственную эмиссию созданной стоимостью.

```text
RealAsset → VerifiedCashFlow / EligibleNAV → financing capacity
```

Не допускается:

```text
Mint → token price → collateral → more mint → synthetic NAV
```

## $650 млрд: что это означает

BASE-v2 использует **$650 млрд gross CAPEX за 2026–2045**, а не единовременный государственный чек.

Исследовательский funding mix:

| Источник | Доля | Объём за 20 лет |
|---|---:|---:|
| private/corporate equity + reinvested earnings | 24% | $156bn |
| project/development debt | 25% | $162.5bn |
| infrastructure/agro/housing bonds | 15% | $97.5bn |
| land-value capture / mortgage / presales | 10% | $65bn |
| regulated tokenized RWA / project CFA capital | 8% | $52bn |
| state/SWF/development catalytic capital | 8% | $52bn |
| offtake/vendor/export-credit finance | 5% | $32.5bn |
| bounded productive-liquidity bridge | 5% | $32.5bn cumulative |

Это **MODEL ASSUMPTION**, не оферта.

## Цель первого этапа

Не искать $650bn. Сначала собрать/создать **$10–20bn качественного anchor NAV** из реальных активов и внешнего капитала. Затем использовать нормальное project finance, debt, CFA/RWA, reinvestment и ограниченную временную ликвидность для увеличения productive asset base.

## Контур 1 — Real Assets

Принимаются только юридически и бухгалтерски определённые активы:

- project SPV equity;
- infrastructure assets;
- power assets;
- factories/equipment;
- income-producing housing/renovation SPV;
- agriculture/processing assets;
- cash/deposits;
- eligible bonds/CFA/RWA;
- externally audited investment-fund NAV.

## Контур 2 — SYNA-CAP

Концептуально SYNA-CAP — **floating NAV-backed capital instrument**, а не stablecoin.

Если юридически допустимо:

```text
NAV_per_unit = EligibleNAV / UnitsOutstanding
```

Новый инвестор должен входить по текущему NAV/valuation, чтобы сам по себе новый выпуск не размывал старых владельцев.

### Eligible NAV

```text
EligibleNAV =
    Cash
  + Haircut(LiquidAssets)
  + Haircut(ProjectCFA)
  + Haircut(RealAssets)
  + Haircut(MIDAS_NAV)
  - ExternalDebt
  - StableLiabilities
  - OtherSeniorClaims
```

`MarketCap(SYNA)` не входит в `EligibleNAV` как актив системы.

## Контур 3 — Settlement Layer

Расчётный инструмент отделён от SYNA-CAP и должен иметь более консервативный collateral.

Идея:

```text
SettlementCoverage >= 130–150%   # scenario policy range
```

Основное обеспечение:

- cash;
- deposits;
- short-duration liquid instruments;
- high-quality eligible CFA/RWA;
- transparent reserves.

Volatile project equity и trading NAV получают существенные haircuts или исключаются.

## Контур 4 — MIDAS Reserve Booster

MIDAS рассматривается как **внешний источник реализованного PnL**, а не как денежный эмитент.

Правило:

```text
Realized external PnL → reserve / project equity / buyback / MIDAS growth
```

Unrealized PnL не должен автоматически поддерживать денежные обязательства.

Для системной устойчивости задаётся cap:

```text
MIDAS eligible share of systemic NAV <= policy limit
```

Например 5–10% как исследовательская граница, уточняемая risk engine.

## Контур 5 — Productive Escrow

### E1 — Escrow Authorization

Финансирующий контур создаёт **нециркулирующее право/лимит финансирования**. Оно не считается денежной массой и не создаёт purchasing power для общего рынка.

### E2 — Verified Release

Расчётная ликвидность может быть выпущена только после внешнего доказательства физического milestone.

Концептуальный guardrail:

```text
Release_t = PRICE_GATE_t * min(
    UnusedEscrow_t,
    alpha * VerifiedIncrementalProductiveFlow_t,
    DrainCapacity_t
)
```

`alpha = 0.25 года` использовалось в BASE-v2 как консервативная сценарная граница, а не экономический закон.

### PRICE_GATE

`PRICE_GATE = 0`, если нарушаются установленные национальным денежным регулятором пределы:

- core inflation;
- food inflation;
- FX stress;
- sector capacity stress;
- failed audit;
- insufficient sterilization capacity.

### Automatic drain

Временная ликвидность должна иметь встроенный путь погашения:

```text
project revenue / repayment / tax / dividend / agreed sweep
  → settlement account
  → QE liability reduction
  → burn / sterilization
```

## Критически важная граница репозитория

`synergy_eurasian` **не реализует mint/burn**. Он только создаёт:

- `ProjectProposal`;
- физические milestones;
- expected productive flow;
- evidence requirements;
- recommendation limits.

Денежное решение принимается внешним Financial OS + human/regulatory authorization.

## Bridges / external blockchains

Bridge/arbitrage может:

- объединять ликвидность;
- уменьшать price fragmentation;
- приносить реальный net arbitrage PnL;
- расширять investor access.

Но:

```text
BridgeTVL != NewWealth
InternalPoolRevaluation != ExternalIncome
MintedToken != Asset
```

Учитывается только фактически реализованный net external PnL после fees/gas/MEV/credit loss и только один раз.

## Solvency invariants

```text
EligibleRealAssets > ExternalLiabilities + StableLiabilities + QEOutstanding
FreeCollateral = EligibleAssets - EncumberedAssets
FreeCollateral >= 0
ConservationError ≈ 0
```

Один актив не может одновременно обеспечивать несколько независимых обязательств без явного seniority/intercreditor accounting.

## Legal principle

Каждая страна сохраняет собственное регулирование денег, ЦФА/ценных бумаг, фондов, банков и цифровых активов. Общий EAEU-layer может стандартизировать данные, risk metrics и evidence, но не подменяет национальные лицензии и регуляторов.
