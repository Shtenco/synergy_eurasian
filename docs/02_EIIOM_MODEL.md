# 02 — EIIOM-2045 Mathematical Model

## Цель

`EIIOM = Eurasian Industrial Intelligence Optimization Model`.

Модель должна находить оптимальное распределение капитала между странами, секторами и фазами так, чтобы максимизировать **discounted verified real-economy value**, а не номинальный TVL или рыночную капитализацию цифровых инструментов.

## Множества

```text
C = {RU, KZ, BY, AM, KG}
T = {2026-30, 2031-40, 2041-45}
```

Базовые 24 сектора:

```text
PowerGen
Grid
MineralRefining
AdvancedMaterials
PowerElectronics
DataCenterInfra
Compute
AICloud
IndustrialAI
Robotics
MachineTools
SemiDesign
Logistics
STEM
AgroGenomics
SeedProduction
PrecisionAg
AgroRobotics
FoodProcessing
WaterIrrigation
RuralAIClusters
UrbanRenovation
RuralHousing
ConstructionTech
```

## Переменная решения

```text
x[c,s,t] >= 0
```

где `x` — CAPEX в млрд долларов.

## Почему не Cobb-Douglas в LP-core

Ранний концепт использовал Cobb-Douglas. Это полезно как макроописание, но нарушает линейность. В воспроизводимом LP ядре используются **линейные capacity-conversion coefficients**, demand caps и технологические dependency constraints. Нелинейные эффекты можно позже добавлять piecewise-linear blocks / MILP / SOS2.

## Целевая функция

Упрощённо:

```text
max Σ[c,s,t] x[c,s,t] * gva_yield[s] * suitability[c,s] * time_weight[t]
```

При этом `gva_yield` — **MODEL ASSUMPTION**, а не обещанная доходность.

## Жёсткие физические зависимости

### Compute ≤ DC shell

```text
ComputeMW[c,t] <= DCMW[c,t]
```

### Power coverage

```text
1.25 * ComputeMW[c,t]
  <= ExistingPowerHeadroom[c] + NewPowerMW[c,t]
```

### Grid coverage

```text
1.25 * ComputeMW[c,t]
  <= ExistingGridHeadroom[c] + NewGridMW[c,t]
```

### Geographic resilience

```text
ComputeShare[c] <= 60%
DCShare[c] <= 60%
```

### AICloud ↔ Compute

```text
AICloudCAPEX <= 1.2 * ComputeCAPEX + baseline_allowance
```

### Industrial AI ↔ physical delivery

```text
IndustrialAI
  <= 1.8 * AICloud + 0.5 * Robotics + baseline_allowance
```

### Robotics ↔ MachineTools / PowerElectronics

```text
MachineTools >= 0.25 * Robotics
Robotics <= 2 * MachineTools + 1.5 * PowerElectronics + allowance
```

### Semiconductor design

```text
SemiDesign <= 0.5 * Compute + allowance
```

Полноценный leading-edge fab не является базовым обязательным узлом: сначала моделируется design/EDA/IP, packaging и прикладные accelerator paths.

## AI Agriculture dependencies

```text
SeedProduction >= 0.7 * AgroGenomics
PrecisionAg <= 2.5 * AICloud + baseline
AgroRobotics <= 1.5 * Robotics + MachineTools + baseline
RuralAIClusters <= 0.7 * local_agro_stack + baseline
FoodProcessing <= PrecisionAg + AgroRobotics + SeedProduction + WaterIrrigation + baseline
```

## Housing dependencies

```text
ConstructionTech >= 0.12 * (UrbanRenovation + RuralHousing)
```

`RuralHousing` не является standalone speculative development: он должен быть связан с реальным локальным productive cluster и социальной инфраструктурой.

## BASE-v2 scenario

Исследовательский envelope:

```text
2026-30: $120bn
2031-40: $290bn
2041-45: $240bn
TOTAL:   $650bn
```

Это **не предложение государственных расходов**. Это совокупный gross CAPEX всех источников за двадцать лет.

Модельный ориентир v2:

```text
Annual GVA-equivalent 2045 ≈ $160bn/y
Productive GVA-equivalent ≈ $155bn/y
Compute IT-load ≈ 1.5GW
Urban renovation = 100m m²
Rural swing housing = 8m m²
Precision agriculture = 60m ha
Agro-robotics = 15m ha
Rural AI-clusters = 160
```

## Ключевая коррекция ранней модели

Ранний top-down сценарий оценивал до 20 GW IT-load к 2045. После разделения:

- DC shell;
- accelerator hardware;
- power;
- grid;
- power electronics;

20 GW при CAPEX $420–650bn перестали быть реалистичным optimum. Это важный пример того, зачем EIIOM нужен именно как constraint model.

## Marginal-capital question

Главный output системы:

```text
Given +$1bn:
  where?
  when?
  what physical capacity?
  what constraint becomes binding?
  what verified annual value?
  what downside?
```

Вместо абстрактного «ROI сектора» решается **связанный portfolio rebalance**.

## Следующая версия: Spatial MILP

`v3` должна заменить агрегированные страны конкретными узлами:

- город / район / квартал;
- подстанция;
- генерация;
- дата-центр;
- завод;
- месторождение / переработка;
- поле / water basin;
- seed station;
- элеватор;
- food-processing plant;
- дорога / rail / port;
- rural cluster;
- конкретный жилфонд.

Появятся binary variables:

```text
BUILD[p] ∈ {0,1}
OPEN_CLUSTER[k] ∈ {0,1}
RENOVATE_BLOCK[b] ∈ {0,1}
```

и network flows по энергии, материалам, товарам, людям и капиталу.
