# 32 — Climate, Energy & Water Security

## Почему это один контур

В Евразии энергия, вода, сельское хозяйство, промышленность и города физически связаны. Поэтому нельзя оптимизировать их отдельными таблицами.

```text
CLIMATE
  ↓
water availability
  ↓
agriculture / hydro / cities / industry
  ↓
power demand & food output
  ↓
trade / prices / migration / CAPEX
```

## Climate is scenario, not slogan

Для EIIOM климатический слой — набор физических stress scenarios, а не ESG-score.

Минимум:

```text
NORMAL
HOT_DRY
MULTIYEAR_DROUGHT
FLOOD_EXTREME
COLD_WINTER
HEATWAVE_POWER_PEAK
CROP_DISEASE_SHOCK
```

## Water balance

Для basin `w`, периода `t`, сценария `ω`:

```text
RenewableWater[w,t,ω]
+ StorageRelease[w,t,ω]
+ Reuse[w,t,ω]
=
AgricultureUse
+ IndustryUse
+ HouseholdUse
+ EnvironmentalFlow
+ StorageBuild
+ Losses
```

Нельзя использовать nominal river flow как полностью доступную промышленную воду.

## Agricultural water productivity

Главный KPI:

```text
WaterProductivity = marketable_tonnes / m3_water
```

и экономический:

```text
EconomicWaterProductivity = verified_value_added / m3_water
```

Это позволяет сравнивать irrigation upgrades, crop choice и processing.

## Energy-water nexus

Water systems требуют энергии:

- pumping;
- treatment;
- desalination only where relevant/economic;
- cooling;
- wastewater reuse.

Energy systems могут требовать воду:

- thermal generation cooling;
- hydro depends on flows;
- some industrial fuel chains.

EIIOM должен учитывать оба направления.

## Grid resilience

Для critical region:

```text
FirmCapacity
+ ImportCapacity
+ StorageFirmContribution
+ DemandResponse
>= PeakDemand * ReserveMargin
```

AI/data centers не должны съедать reliability reserve промышленности/населения.

## Flexible compute

Часть non-latency-critical AI workloads может быть dispatchable:

```text
low-price / surplus hours → training / batch compute↑
peak grid stress           → flexible compute↓
```

Это потенциально превращает compute в demand-response resource, но только если workload/customer contracts допускают прерывание.

## Waste heat

DC/industrial waste heat имеет ценность только при существующем heat sink.

```text
RecoverableHeatValue
= usable_heat_delivered
- network CAPEX
- pumping
- seasonal mismatch
```

Не считать теоретические MW тепла доходом без покупателя.

## Storage

Battery/storage project оценивается по stack of services:

- peak shaving;
- ancillary services;
- renewable shifting;
- outage resilience;
- grid deferral.

Avoid double-counting the same capacity as simultaneously fully available to all services.

## Food security

Food security KPI is broader than production tonnes:

```text
FoodSecurity = f(
  domestic production,
  seed resilience,
  input resilience,
  storage,
  processing,
  logistics,
  import diversity,
  affordability,
  climate stress
)
```

## Seed resilience

For critical crop:

```text
SeedResilience =
  local_registered_varieties
+ diversified external suppliers
+ multiplication capacity
+ germplasm diversity
+ climate-adapted pipeline
```

Autarky is not required; resilience is the objective.

## Emergency reserve networks

Critical goods:

- selected food categories;
- transformer/spares;
- critical industrial components;
- medicines/medical supplies under separate regulated planning;
- fuels where needed.

Reserve size should be based on lead time and disruption probability, not political symbolism.

## Environmental cost

Project comparison includes:

```text
land impact
water impact
pollution controls
waste
remediation liability
carbon/energy cost where economically material
biodiversity/legal constraints
```

Ignoring environmental liabilities inflates apparent NPV and can create future fiscal cost.

## Climate-adjusted project finance

For long-lived assets:

```text
DSCR_stress(climate_ω)
LTV_stress(climate_ω)
insurance_cost_ω
maintenance_cost_ω
```

must remain within policy or project needs redesign.

## Rural-cluster resilience

Every rural AI cluster requires:

- water security;
- backup power;
- heat/cooling;
- resilient broadband;
- emergency transport;
- food/storage;
- local maintenance capability.

## KPI

- water withdrawal/unit output;
- irrigation efficiency;
- drought yield volatility;
- grid outage minutes;
- reserve margin;
- energy intensity;
- flexible load MW;
- storage utilization;
- waste-heat actually sold/used;
- climate-stressed DSCR;
- critical seed/input coverage.

## Hard rule

```text
No growth target can override a physical water or reliability constraint.
```
