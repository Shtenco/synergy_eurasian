# 13 — Research Perimeter / External SYNERGY Engines

`synergy_eurasian` моделирует **реальную экономику**. Несколько связанных исследовательских систем могут взаимодействовать с ним, но не входят в его accounting truth и не могут автоматически создавать признанный NAV.

## MIDAS

Роль:

- внешний trading/research engine;
- потенциальный источник **realized external net PnL**;
- reserve booster;
- research signal source для macro/risk layer.

Не допускается:

- признавать unrealized PnL как stable collateral без haircut;
- финансировать системные обязательства только ожиданием будущей alpha;
- считать backtest PnL реальным активом.

## MetaPay

Роль:

- settlement / routing / external-value capture research;
- prefunded multi-venue flow optimization;
- арбитраж, если он существует после fees, gas, slippage, settlement и counterparty risk.

Признаётся только:

```text
RealizedExternalPnLAfterAllCosts
```

Не признаётся:

```text
InternalPoolRevaluation
NominalTVLGrowth
CircularSelfTrading
UnrealizedRouteQuote
```

## Productive Liquidity / AI Central Bank research

Исследовательский monetary layer может моделировать:

- escrow limits;
- matching capital;
- rating gates;
- fraud penalties;
- production/import-capex/logistics/SME/export contours;
- price-stability gates;
- automatic sterilization.

Но в `synergy_eurasian` он представлен только интерфейсом `ProjectProposal → EvidencePackage`.

### Почему

Real Economy OS не должен иметь право:

1. предложить проект;
2. сам оценить его как успешный;
3. сам создать под него деньги;
4. сам признать эти деньги активом.

Это нарушило бы separation of duties.

## SYNA / token experiments

SYNA может исследоваться как:

- tokenized capital claim;
- NAV-linked unit;
- RWA/CFA wrapper;
- governance/access layer.

Но:

```text
SYNA market price != system NAV
SYNA market cap != collateral asset
Minted SYNA != external income
```

## AMM / bridge / QE experiments

Исследовательские AMM-графы, bridge arbitrage, internal/external liquidity, QE/QT corridors и mint/sell/addLP циклы полезны только для проверки одного вопроса:

> появляется ли **внешняя** стоимость после всех расходов и обязательств?

Главные метрики:

```text
DeltaHardNAV_after_all_costs
DeltaExternalCash
DeltaExternalLiabilities
Coverage
SolvencyNAV
ConservationError
```

Token-side TVL и GrossTVL публикуются только рядом с HardNAV, чтобы визуальный рост токенной стороны не выдавался за экономическую прибыль.

## Три допустимых внешних двигателя капитала

Концептуально система может иметь:

1. **Real-economy operating cashflow/export** — основной двигатель;
2. **MIDAS realized external alpha** — ограниченный reserve booster;
3. **MetaPay/market arbitrage realized external PnL** — opportunistic engine.

Внутренний Productive Escrow/QE — не четвёртый источник богатства. Это **временной механизм финансирования**, который должен быть погашен/стерилизован из созданного реального cashflow.

## Current engineering warning

Связанные monetary/blockchain эксперименты должны считаться `RESEARCH / NOT PRODUCTION` до прохождения:

- deterministic accounting tests;
- conservation tests;
- adversarial economic tests;
- security audit;
- chain/fork tests;
- legal review;
- CI green.

Красный CI или отсутствие runtime/security guards автоматически запрещают использование соответствующего модуля как production dependency.

## Interface rule

```text
ExternalEngine
   ↓
Realized and independently verifiable result
   ↓
Financial OS
   ↓
Canonical accounting
   ↓
Only then may Real Economy OS observe available capital
```

Никакой исследовательский двигатель не пишет NAV напрямую.
