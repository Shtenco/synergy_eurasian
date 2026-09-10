# 19 — P2P Mutual Credit / касса взаимопомощи / productive capital

## Роль в евразийской системе

Между household savings и крупным project finance нужен мезоуровень: малый бизнес, фермеры, кооперативы, локальные сервисы, оборудование и временная ликвидность.

SYNERGY использует для этого **maturity-matched mutual/P2P credit**, а не обещание «размножить деньги».

## Базовый цикл

```text
Household Delta
  ↓
Independent Savings Tranches
  ↓
Reserve / Maturity Ladder
  ↓
Eligible P2P / SME / Equipment Credit
  ↓
Real Asset / Working Capital
  ↓
External Customer Revenue
  ↓
Principal + Interest Repayment
  ↓
Financial OS
  ↓
Capital Reuse
```

## Главная бухгалтерская граница

Выданный кредит создаёт одновременно:

```text
Lender Asset  +LoanReceivable
Borrower Cash +LoanLiability
```

Он не создаёт консолидированный NAV из ничего.

Положительный NAV возникает только если:

```text
RealizedInterest + Fees + RecoveredCollateral
  > CreditLoss + FundingCost + OPEX + FraudLoss
```

и при этом principal не посчитан доходом.

## Tranche model

Каждый новый вклад семьи — отдельный funding tranche:

```text
Tranche {
  tranche_id
  owner
  currency
  amount
  callable_date
  maturity_date
  liquidity_class
  risk_limit
}
```

Нельзя считать ежемесячное пополнение новым «участником» или многократно использовать один и тот же principal одновременно.

## Maturity matching

Для каждого кредита:

```text
WeightedFundingMaturity >= LoanMaturity + LiquidityBuffer
```

Callable reserve money не используется для долгого 5-летнего кредита без отдельного maturity transformation / liquidity reserve.

## Product families

### A. Emergency Mutual Credit

Назначение: короткий социальный bridge для участника с временным cashflow shock.

Принципы:

- небольшой лимит;
- короткий срок;
- прозрачная affordability-проверка;
- без инвестирования этих средств в risk assets;
- hardship restructuring;
- не финансируется из минимального emergency reserve других семей без explicit policy.

### B. Productive Microcredit

Для:

- оборудования;
- инструмента;
- небольшого производства;
- фермерской техники;
- холодовой цепи;
- energy-efficiency retrofit;
- verified inventory turnover.

Кредит должен иметь идентифицируемый source of repayment.

### C. Revenue-Based Finance

Вместо фиксированного долга для нестабильного малого бизнеса:

```text
Repayment_t = min(cap, share * VerifiedRevenue_t)
```

Снижает вероятность дефолта при сезонности, но требует прозрачного settlement.

### D. Equipment / Asset Lease Pool

Фонд покупает производительный актив и сдаёт его в lease/service model.

Примеры:

- shared agro machinery;
- robots;
- cold storage;
- workshop tools;
- solar/storage where economic;
- delivery equipment.

Здесь collateral физически наблюдаем.

### E. Cooperative Project Credit

Несколько малых предприятий формируют supply chain вокруг одного крупного anchor buyer.

```text
AnchorOfftake
  ↓
SupplierReceivables / PurchaseOrders
  ↓
P2P/SME financing
  ↓
Production
  ↓
Delivery
  ↓
Anchor settlement
```

## Positive-NAV mutual aid fund

Касса взаимопомощи становится устойчивой, если разделить три баланса:

```text
SOCIAL RESERVE
  grants / emergency support

CREDIT BOOK
  loans + expected loss + reserves

INVESTMENT BOOK
  long-term productive assets
```

Нельзя покрывать постоянные investment losses новой социальной кассой.

## Expected credit loss

Для loan `i`:

```text
ECL_i = PD_i * LGD_i * EAD_i
```

Portfolio capital:

```text
NetCreditNAV =
    Cash
  + PerformingLoanPV
  + CollateralHaircutValue
  - FundingLiabilities
  - ExpectedCreditLoss
  - OperatingAccruals
```

## AI underwriting

NEXUS/AI может помогать оценивать:

- cashflow stability;
- invoice/payment history;
- seasonality;
- sector stress;
- collateral condition;
- supply-chain dependencies;
- fraud anomalies;
- affordability.

Но AI не имеет права автоматически дискриминировать по чувствительным характеристикам или обходить legal consumer-credit rules.

## P2P → Eurasian Project Pipeline

Самая интересная функция слоя — растить малые компании до supplier-grade.

```text
Household capital
  ↓
P2P equipment finance
  ↓
SME supplier
  ↓
verified delivery history
  ↓
larger working-capital line
  ↓
EIIOM industrial cluster supplier
  ↓
project bond / institutional finance eligibility
```

То есть народный капитал не обязан напрямую финансировать гигантский завод. Он может создавать **десятки тысяч поставщиков**, которые затем входят в большие евразийские цепочки.

## Currency discipline

RUB, KZT, BYN, AMD, KGS, USD и иные валюты нельзя складывать номинально.

```text
PortfolioValue(reporting_currency)
 = Σ FX_policy(asset_currency → reporting_currency) * haircut * asset_value
```

FX reference rate не доказывает исполнимый курс обмена.

## Anti-Ponzi invariant

```text
InterestPaidToExistingParticipants
  <= RealizedInterest/Fees/OperatingIncome
     + explicitly disclosed reserve support
```

Новый principal может финансировать новый кредит, но не должен маскироваться под «доходность» старого портфеля.

## Integration contracts

P2P layer sends to Financial OS:

```text
LoanOriginationIntent
FundingTrancheReservation
RepaymentReceipt
DefaultEvent
CollateralEvent
WriteOffAuthorization
```

EIIOM receives only aggregated/permissioned signals:

```text
SMECreditDemand
SupplierCapacity
RegionalDefaultRate
EquipmentDemand
WorkingCapitalBottleneck
```

Так private household data не становится открытым industrial dataset.
