# 08 — Governance, Risk, Compliance

## Зачем этот слой

СИНЕРГИЯ объединяет real assets, AI, project finance, retail participation, cross-border infrastructure и потенциальные цифровые права. Поэтому главный риск — не только технический. Ошибка governance способна разрушить даже хороший производственный проект.

## Базовая модель принятия решения

Ни AI, ни токен-холдеры, ни один основатель не должны иметь единоличного права провести полный цикл проекта.

```text
Model recommendation
  ↓
Technical review
  ↓
Economic underwriting
  ↓
Legal/regulatory review
  ↓
Conflict-of-interest review
  ↓
Human authorization
  ↓
Settlement
  ↓
Independent evidence
  ↓
Accounting
```

## Разделение ролей

Минимум:

- **Model Operator** — строит сценарий;
- **Project Sponsor** — предлагает проект;
- **Technical Verifier** — подтверждает инженерную часть;
- **Financial Underwriter** — считает debt/equity/cashflow;
- **Legal/Compliance** — определяет допустимость инструмента;
- **Treasury/Settlement** — исполняет разрешённые платежи;
- **Evidence Auditor** — подтверждает milestones;
- **Accounting/NAV Agent** — признаёт актив/обязательство;
- **Risk Committee** — может остановить следующий release;
- **Community/Local Council** — участвует в затрагивающих жителей решениях.

## Жёсткие risk gates

### Project gate

```text
No FID without:
  identified asset
  legal SPV/owner
  CAPEX estimate
  construction schedule
  signed/credible demand
  downside scenario
  evidence plan
  exit/termination rule
```

### Data-center gate

```text
AnchorDemand >= 60% planned IT capacity   # scenario threshold
ContractedPower >= 1.3 * planned IT load
HardwarePath == secured
3YUtilizationCase >= threshold
```

### Materials/refining gate

```text
OfftakeBeforeFID >= 50% planned output   # scenario threshold
```

### Industrial AI gate

```text
Scale only after measured pilot
Payback target <= 3–4 years
Counterfactual baseline required
```

### Housing gate

```text
VoluntaryConsent == true
ReturnRight == legally enforceable
BasicServicesReady == true
RelocationCapacity >= affected households
```

### Productive escrow gate

```text
ExternalEvidence == passed
PriceStabilityGate == open
DrainCapacity >= required
NoDoubleCollateral == true
```

## Основные риски

| Риск | Почему опасен | Базовый ответ |
|---|---|---|
| accelerator supply / tech access | stranded DC shell | staged procurement, multi-vendor, efficiency-first |
| grid delay | compute не подключается | grid-before-compute gate |
| transformer/power electronics shortage | bottleneck всей сети | long-term offtake + local production |
| lack of industrial demand | AI не создаёт GVA | anchor customers + gain-sharing |
| engineering shortage | проекты не масштабируются | STEM/mobility/retraining |
| FX/WACC | CAPEX резко дорожает | currency-matched finance / local revenue |
| data/IP fragmentation | общий AI-stack распадается | common schemas + federated approaches |
| upstream overbuild | замороженный капитал | offtake-before-FID |
| household backlash | социальная деградация | voluntary-only + legal rights |
| token reflexivity | synthetic NAV | exclude own market cap from collateral |
| bridge/security failure | loss of reserves | exposure caps, isolated reserves, independent verification |
| trading losses | contagion from MIDAS | haircut/cap, no stable-liability dependence |
| model error | false capital allocation | reproducible assumptions + scenario ensemble |

## Accounting invariants

```text
A1: Every recognized asset has legal owner and evidence.
A2: Every liability has seniority and maturity.
A3: Encumbered asset is excluded from free collateral.
A4: Unrealized internal token appreciation is not external income.
A5: Internal AMM TVL expansion is not automatically HardNAV growth.
A6: Only realized external net PnL is recognized as new external cash.
A7: Modelled GVA is not booked revenue.
A8: Conservation error must remain approximately zero in simulations.
```

## Investor-protection invariants

- no guaranteed return unless instrument legally and financially contains such senior obligation and disclosure;
- no use of emergency household savings by default;
- no leverage encouragement to retail users;
- risk classification and suitability/qualification gates;
- clear liquidity/maturity information;
- independent valuation where required;
- project-specific issuer/SPV where practicable;
- related-party transactions disclosed;
- full fee waterfall disclosed;
- marketing copy cannot override legal disclosure.

## Anti-pyramid test

Любая retail/crowd model проходит тест:

```text
Can existing investors be paid if new investor inflow = 0?
```

Если ответ «нет», модель требует redesign.

Дополнительный тест:

```text
CashAvailableForDistribution
  <= RealizedOperatingCashflow
   + RealizedAssetSalePnL
   + legally permitted financing explicitly disclosed as such
```

Привлечение нового капитала может финансировать новые активы, но не маскироваться под операционную доходность старых инвесторов.

## AI governance

AI может:

- ранжировать проекты;
- давать forecasts;
- выявлять аномалии;
- предлагать allocation;
- автоматически останавливать процесс при hard invariant breach.

AI не может:

- обходить compliance;
- создавать юридические права;
- подделывать evidence;
- сам подтверждать построенный им же проект;
- самостоятельно менять accounting policy;
- снимать hard risk limits без человеческого решения.

## Auditability

Каждый run EIIOM должен хранить:

```text
model_version
config_hash
input_data_hashes
solver_version
objective_value
constraint_slacks
selected_projects
rejected_projects
run_timestamp
reviewer_signatures
```

Так экономическая политика становится проверяемой и воспроизводимой.
