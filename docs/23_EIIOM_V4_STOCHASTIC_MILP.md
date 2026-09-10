# 23 — EIIOM-v4: Stochastic Spatial MILP / Economic Compiler

## Зачем v4

LP-v2 отвечает: **какие отрасли получают капитал**.

Spatial-v3 отвечает: **где строить конкретные объекты**.

v4 должен отвечать на более сильный вопрос:

> **Как собрать из семейного капитала, банковского/project finance, энергии, материалов, труда, науки, цифровой инфраструктуры и транспортных коридоров устойчивую сеть проектов при нескольких будущих сценариях одновременно?**

Это уже не просто инвестиционный оптимизатор. Это **economic compiler**.

## Множества

```text
C  countries
R  regions
N  physical nodes
P  candidate projects
S  sectors
K  commodities/services
E  transport/grid/data edges
T  time periods
Ω  uncertainty scenarios
H  household cohorts
F  financing instruments
L  labor/skill classes
W  water basins
D  demand markets
```

## State vector

Для времени `t` и сценария `ω`:

```text
X[t,ω] = {
  installed_capacity,
  utilization,
  power_generation,
  grid_headroom,
  compute,
  inventories,
  labor,
  skills,
  housing,
  farmland,
  water,
  logistics_capacity,
  demand,
  debt,
  liquidity,
  project_status,
  household_reserves,
  external_market_access
}
```

## Главные переменные решения

### Project build

```text
BUILD[p,t] ∈ {0,1}
```

### Capacity expansion

```text
CAPADD[p,t] >= 0
```

### Commodity/resource flow

```text
FLOW[k,e,t,ω] >= 0
```

### Production

```text
PROD[p,k,t,ω] >= 0
```

### Inventory

```text
INV[k,n,t,ω] >= 0
```

### Compute allocation

```text
COMPUTE_ALLOC[workload,n,t,ω] >= 0
```

### Financing

```text
EQUITY[p,f,t] >= 0
DEBT[p,f,t] >= 0
CFA_RWA[p,f,t] >= 0
CATALYTIC[p,t] >= 0
```

### Household voluntary capital

```text
HH_INVEST[h,p,t] >= 0
```

subject to household reserve/suitability limits.

### P2P credit

```text
P2P_LOAN[borrower,tranche,t] >= 0
```

with maturity/funding constraints.

### Housing renovation

```text
RENOVATE[b,t] ∈ {0,1}
TEMP_ASSIGN[h,k,t] >= 0
```

where temporary assignment is only possible for consenting households.

### Science-stage investment

```text
RND_STAGE[technology,g,t] ∈ {0,1}
```

Capital to next TRL gate, not automatic full-scale build.

## Multi-objective function

Вместо одного GVA multiplier:

```text
MAX Expected[
    EconomicSurplus
  + ExternalCashflowValue
  + ProductivityValue
  + ResilienceValue
  + HumanCapitalValue
  + OptionValueOfScience
  - CAPEX
  - LifecycleOPEX
  - FinancingCost
  - ExpectedCreditLoss
  - TailRiskCost
  - SocialDisruptionCost
  - EnvironmentalDamageCost
]
```

Дополнительно CVaR:

```text
MAX ExpectedValue - λ * CVaR_α(Loss)
```

Это предотвращает выбор портфеля, который великолепен в среднем, но катастрофичен в плохом сценарии.

## Сценарии Ω

Минимум:

```text
BASE
LOW_GROWTH
HIGH_WACC
FX_STRESS
ENERGY_TIGHT
COMPUTE_SUPPLY_RESTRICTED
CLIMATE_DRY
LOGISTICS_DISRUPTION
EXPORT_BOOM
TECH_ACCELERATION
```

Можно комбинировать через scenario tree.

## Non-anticipativity

Решения до раскрытия сценария не могут «знать будущее»:

```text
Decision[t,ω1] = Decision[t,ω2]
for scenarios indistinguishable at t
```

Это критично: иначе stochastic model будет иметь скрытый lookahead.

## Input-output balance

Для каждого товара `k`, узла `n`, времени `t`, сценария `ω`:

```text
Production
+ Imports
+ IncomingFlows
+ InventoryRelease
=
IntermediateUse
+ HouseholdDemand
+ Exports
+ OutgoingFlows
+ InventoryBuild
+ Losses
```

## Leontief / recipe constraints

Например 1 единица output требует набор inputs:

```text
InputUse[i,p] >= a[i,p] * Production[p]
```

Это позволяет видеть скрытый bottleneck: завод может быть построен, но не иметь трансформаторов, меди, воды или квалифицированных работников.

## Capacity constraint

```text
Production[p,t,ω] <= AvailableCapacity[p,t] * Availability[p,t,ω]
```

## Demand constraint

```text
Sales[k,d,t,ω] <= AddressableDemand[k,d,t,ω]
```

Это защищает модель от бесконечного строительства высокомаржинального сектора без покупателей.

## Energy system

```text
Generation[n,t,ω]
+ ImportsPower[n,t,ω]
- ExportsPower[n,t,ω]
- Losses
>= IndustrialLoad + ComputeLoad + ResidentialLoad + ReserveMargin
```

Плюс transmission edge limits.

## Compute stack

```text
ITLoad <= DCShellCapacity
ITLoad * PUE <= GridDelivery
AcceleratorWorkload <= InstalledAcceleratorEquivalent
AIServiceOutput <= Compute + Data + Skills + Demand
```

`Compute` никогда не преобразуется в GVA без workload/demand channel.

## Labor and skills

Для каждого skill `l`:

```text
Σ_p LaborDemand[p,l] <= Workforce[l] + Trained[l] + LawfulMobility[l]
```

Training investment имеет lag:

```text
Trained[l,t+lag] += TrainingSeats[l,t] * CompletionRate
```

## Water

Для каждого basin:

```text
AgricultureUse
+ IndustrialUse
+ HouseholdUse
<= SustainableWithdrawal
```

Climate scenarios меняют sustainable withdrawal и crop yields.

## Agriculture

```text
Yield[crop,field,t,ω]
 = baseline_yield
 * genetics_factor
 * precision_factor
 * irrigation_factor
 * climate_factor
```

В MILP это реализуется piecewise-linear blocks или precomputed scenario coefficients, а не нелинейным black box внутри solver.

## Seed breeding

AI не создаёт урожай напрямую.

```text
R&D investment
→ candidate lines
→ trials
→ probability of registered improved variety
→ later yield/stability benefit
```

Эффект имеет lag и uncertainty.

## Housing / voluntary relocation

```text
TEMP_ASSIGN[h,k,t] <= Consent[h,k,t] * HouseholdSize[h]
```

и:

```text
SchoolCapacity[k,t] >= AssignedChildren[k,t]
HealthcareCapacity[k,t] >= AssignedPopulation[k,t] * standard
TransportCapacity[k,t] >= required
```

Right-of-return is legal hard constraint, not objective penalty.

## Household finance constraint

Для cohort `h`:

```text
EmergencyReserve[h,t] >= MinimumReserve[h,t]
```

before elevated risk allocation.

```text
HH_INVEST[h,p,t]
<= RiskBudget[h,t]
<= FreeDelta[h,t] * PolicyShare[h]
```

No optimizer may consume household subsistence funds to improve system NPV.

## P2P maturity constraint

```text
LoanMaturity <= WeightedFundingMaturity - Buffer
```

and expected-loss reserve.

## Financing and project balance sheet

```text
UsesOfFunds[p]
=
Equity
+ Debt
+ CFA/RWA
+ VendorFinance
+ OfftakePrepayment
+ CatalyticCapital
```

Productive-liquidity bridge is **not generated by this model**; EIIOM only outputs eligible verified milestones for external Financial OS review.

## Solvency interface

Before a project is funded:

```text
FinancialOSAvailableCapacity >= RequestedAuthorization
```

EIIOM cannot override it.

## Logistics

Flow cost:

```text
Cost[e,k] =
  freight
+ border/customs
+ insurance
+ inventory_time
+ FX/settlement friction
+ expected disruption
```

Multiple corridors create resilience option value.

## External market access

```text
FLOW[e,t,ω] = 0
if LegalAccess[e,t,ω] == false
```

No sanctions/compliance bypass by optimization.

## Science TRL gates

A low-TRL technology cannot become full-scale build variable without passing earlier evidence gates.

```text
BUILD_COMMERCIAL[p,t]
<= QUALIFIED_TECH[p,t]
```

## Capital recycling

Cash generated in one period increases later capital capacity only after Financial OS recognition:

```text
AvailableCapital[t+1]
<= ExternalCommittedCapital
 + RecognizedRetainedCashflow[t]
 + ApprovedDebtCapacity[t]
```

No internal token mark enters this equation.

## Shadow prices

Один из самых ценных outputs v4 — dual/shadow values:

```text
ShadowPrice(power_MW)
ShadowPrice(grid_MW)
ShadowPrice(engineer)
ShadowPrice(water_m3)
ShadowPrice(corridor_capacity)
ShadowPrice(1bn_capital)
```

Они отвечают: **какой bottleneck сегодня стоит системе дороже всего?**

## Marginal $1bn engine

Алгоритм:

1. solve BASE;
2. add $1bn available capital;
3. resolve;
4. compare full portfolio;
5. report not only where +$1bn landed, but which projects were displaced/rebalanced;
6. compute change in expected value and CVaR;
7. report new binding constraints.

## No fake v4 result

До загрузки реальных spatial baselines v4 **не должен публиковать “оптимальные города/заводы” как solver result**.

Правильный статус:

```text
MODEL_SPEC_READY
DATA_CALIBRATION_PENDING
```

Только после GIS/resource/demand data можно честно переходить к `SOLVER_OUTPUT`.

## Definition of investment-grade model

- source manifest for every material baseline;
- reproducible data pipeline;
- spatial node graph;
- actual project candidates;
- currency/WACC policies;
- demand curves;
- physical recipes;
- stochastic scenarios;
- CVaR;
- non-anticipativity;
- invariant tests;
- independent review;
- ability to replay every published result.
