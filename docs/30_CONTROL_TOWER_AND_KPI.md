# 30 — EIIOM Control Tower: что система должна видеть каждый день

## Почему нужен единый контрольный слой

Система масштаба Евразии легко превращается в презентацию из сотен KPI. Control Tower должен показывать причинную цепочку:

```text
CAPITAL
→ PROJECT
→ PHYSICAL CAPACITY
→ UTILIZATION
→ OUTPUT
→ SALES
→ SETTLEMENT
→ CASH / NAV
→ REINVESTMENT CAPACITY
```

## Level 0 — Household

```text
median_income
necessary_expenses
median_delta
reserve_runway_months
high_cost_debt_share
long_term_savings
project_investment_share
financial_distress_rate
```

Главный вопрос: становится ли обычная семья устойчивее?

## Level 1 — SME / Business

```text
external_revenue
operating_margin
working_capital_days
energy_per_unit
labor_productivity
capacity_utilization
supplier_delivery_rate
credit_default_rate
new_export_customers
```

## Level 2 — Project

### Construction

- approved CAPEX;
- committed CAPEX;
- spent CAPEX;
- earned physical progress;
- schedule variance;
- cost variance;
- open technical blockers;
- permit blockers;
- financing headroom.

### Operating

- rated capacity;
- utilization;
- output;
- yield/scrap/loss;
- energy;
- water;
- labor;
- maintenance;
- revenue;
- operating cashflow;
- DSCR;
- external share of revenue.

## Level 3 — Cluster / Region

```text
power_headroom_mw
grid_headroom_mw
water_headroom
critical_skill_gap
housing_capacity
transport_capacity
industrial_utilization
SME_supplier_count
external_trade_balance_by_chain
localization_ratio
```

## Level 4 — EAEU system

### Real economy

```text
verified_productive_capacity
cross_border_intermediate_trade
external_export_cashflow
import_dependency_critical
industrial_productivity
agricultural_productivity
construction/renovation throughput
```

### Financial

```text
HardNAV
LiquidNAV
EconomicNAV
external_liabilities
liquidity_buffer
recognized_external_PnL
retained_cashflow
capital_authorized
capital_committed
```

Financial truth comes from Financial OS, not calculated independently here.

### Logistics

```text
corridor_capacity
average_transit_time
border_time
transport_cost_per_tonne_km
container_delay
route_redundancy
corridor_disruption_state
```

### Compute

```text
IT_MW
PUE
accelerator_utilization
contracted_workload
inference_cost
training_cost
power_cost
hardware_age
```

### Human capital

```text
critical_vacancies
median_fill_time
training_pipeline
retention
real_wage_productivity_gap
regional_mobility
```

## North Star metrics

Не один KPI, а пять:

### N1 — Verified Productive Delta

```text
VPD = VerifiedExternalAndOperatingValue
      - ExternalCosts
      - LifecycleCapitalConsumption
      - RealizedLosses
```

### N2 — Capital Productivity

```text
CP = VerifiedIncrementalAnnualValue / InvestedCapital
```

Нельзя сравнивать sectors без maturity/lifetime/risk adjustment.

### N3 — Bottleneck Relief Index

```text
BRI = downstream value unlocked / project CAPEX
```

### N4 — Household Resilience

```text
HRI = function(reserve runway, debt stress, stable Delta, savings rate)
```

### N5 — External Value Share

```text
EVS = external/export/reconciled value / total recognized productive value
```

Не максимизировать EVS до 100%: внутренние услуги и инфраструктура тоже имеют ценность. KPI нужен, чтобы видеть источник внешней покупательной способности.

## Risk dashboard

### Red flags

- HardNAV falls while token/market metrics rise;
- debt grows faster than operating cashflow;
- new investment inflow funds distributions;
- compute utilization low while DC CAPEX continues;
- power/grid queue rises;
- project cost-overrun cluster;
- one supplier/technology/corridor concentration;
- household project-investment share rises while reserve runway falls;
- project evidence is stale;
- related-party procurement grows;
- reported GVA grows without cash/physical confirmation.

## Evidence freshness

Каждый KPI должен иметь:

```text
value
unit
as_of
source_authority
confidence
last_evidence_hash
freshness_limit
```

Stale data visually degrades confidence and cannot silently remain «green».

## Traffic-light semantics

```text
GREEN  = within policy + fresh evidence
AMBER  = warning / uncertainty / near limit
RED    = invariant breach / stop condition
GREY   = insufficient evidence
```

Grey is not green.

## Forecast vs actual

Для каждой метрики:

```text
BASE forecast
STRESS forecast
ACTUAL
variance
explanation
```

Это постепенно создаёт dataset forecast errors.

## Model accountability

Control Tower also reports EIIOM quality:

```text
CAPEX forecast error
schedule forecast error
demand forecast error
energy forecast error
project-ranking hit rate
false positive projects
false negatives discovered later
```

AI/optimizer must be measured like any other productive system.

## Public vs restricted dashboard

### Public

- project purpose;
- legal issuer;
- high-level CAPEX;
- physical progress;
- major risks;
- evidence status;
- aggregated economic outcomes.

### Restricted institutional

- contracts;
- counterparty data;
- detailed cashflow;
- sensitive infrastructure;
- cybersecurity;
- personal data;
- trade secrets.

Transparency does not mean publishing security-sensitive infrastructure data.

## Decision queue

Control Tower should end with a ranked queue:

```text
STOP NOW
FIX BOTTLENECK
RELEASE NEXT MILESTONE FOR REVIEW
SCALE
HOLD
REUNDERWRITE
```

EIIOM is useful when it changes decisions, not merely produces charts.
