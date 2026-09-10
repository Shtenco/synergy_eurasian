# 05 — Urban Renovation ↔ Rural AI Clusters

## Идея

Реновация старого городского жилфонда и развитие села рассматриваются не как две независимые программы, а как единый цикл использования капитала.

```text
Urban block
  → voluntary temporary relocation
  → vacant-building renovation / reconstruction
  → guaranteed return / replacement housing
  → rural housing remains a permanent productive asset
  → rural AI cluster grows
```

## Почему это может быть эффективнее обычной реновации

Если часть домов/кварталов можно освобождать на время реконструкции, снижаются:

- сложность фазирования работ вокруг жильцов;
- сроки;
- строительные риски;
- стоимость временных локальных решений;
- социальный конфликт вокруг постоянных переселений.

Одновременно новый rural swing housing после завершения конкретного цикла не списывается: он остаётся жильём для работников, семей, студентов, remote workers, предпринимателей, специалистов, туризма/социального фонда.

## Социальные инварианты

Это обязательные ограничения, а не опции модели.

```text
H-01 Voluntary only
H-02 Legally guaranteed right of return / compensation
H-03 Housing is not conditional on agricultural employment
H-04 School/health/broadband/transport before occupancy
H-05 No quality/area downgrade without consent
H-06 Accessible housing for vulnerable residents
H-07 Transparent compensation and dispute procedure
H-08 Rural asset remains maintained after renovation cycle
```

## BASE-v2 scenario targets

```text
Urban renovation by 2045: 100 million m²
Rural swing housing:        8 million m²
```

При модельных:

- 55 м² temporary rural housing на домохозяйство;
- 2.7 человека на домохозяйство;

8 млн м² дают около 145 тыс. домохозяйств / около 390 тыс. человек одновременной swing-capacity.

Это **сценарные параметры**, а не оценка всего советского жилфонда.

## Что входит в rural cluster до заселения

Minimum viable settlement:

- качественное жильё;
- вода/канализация;
- электричество и резерв;
- broadband/fiber;
- транспорт до регионального центра;
- школа/детский сад по масштабу;
- primary healthcare / telemedicine;
- retail/basic services;
- coworking;
- аварийные службы;
- maintenance operator.

Productive layer:

- precision agriculture;
- autonomous machinery service;
- drones;
- seed/trial access;
- cold chain;
- processing;
- logistics;
- edge compute;
- energy/water optimization.

## Финансирование

Жилищный слой не должен финансироваться преимущественно денежной эмиссией.

Иллюстративный funding stack:

```text
35% land-value capture / extra saleable development rights
25% long-duration housing/municipal/project bonds
20% public infrastructure co-finance
15% private/institutional equity
 5% tightly bounded bridge/escrow financing
```

Реальные пропорции определяются по каждому городу/проекту.

## Не считать рост цены земли выпуском

```text
LandPriceGain != NewCommodityOutput
```

Рост оценочной стоимости недвижимости может улучшать баланс владельца, но сам по себе не является новой товарной массой, под которую можно автоматически выпускать расчётную ликвидность.

## Spatial MILP objective

Для каждого квартала `b` и rural cluster `k` v3 должна минимизировать:

```text
RenovationCost
+ TemporaryRelocationCost
+ TravelTimeCost
+ SocialDisruptionPenalty
+ InfrastructureCost
- ResidualRuralAssetValue
- LandValueCapture
- ProductivityGain
```

при ограничениях:

- добровольность;
- ёмкость временного жилья;
- школа/медицина;
- transport time;
- construction capacity;
- return deadline;
- legal rights;
- budget.

## KPI

- renovated m²;
- cost/m²;
- average project duration;
- resident satisfaction;
- share returning to city;
- share voluntarily remaining in rural cluster;
- rural housing occupancy after cycle;
- jobs/businesses created;
- cluster tax base;
- transport accessibility;
- school/health service quality.
