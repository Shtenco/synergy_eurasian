# 25 — Human Capital: человек как главный производительный актив

## Почему это отдельный слой

EIIOM-v2 мог переоценивать физический CAPEX: электростанции, заводы, роботы, ЦОДы. v4 вводит жёсткое правило:

> **Мощность без людей, навыков, здоровья, жилья и мобильности может существовать бухгалтерски, но не производительно.**

## Human Capital State

Для региона:

```text
HC[r,t] = {
  population,
  labor_force,
  skill_distribution,
  education_pipeline,
  health_capacity,
  housing_affordability,
  mobility,
  wage_distribution,
  migration,
  entrepreneurship,
  digital_access
}
```

## Skill graph

Не «нужно 100 тысяч инженеров», а конкретные skill nodes:

```text
Power Systems
Transformer Design
Power Electronics
Industrial Automation
Machine Tools
Robotics
Welding / CNC / Maintenance
AI/ML
Data Engineering
Cybersecurity
Agronomy
Genomics / Breeding
Irrigation
Construction Management
Project Finance
Audit / Compliance
Logistics
```

Для каждого:

```text
current_supply
annual_graduates
retirement_rate
migration_rate
training_time
cost_per_graduate
wage
project_demand
```

## Workforce bottleneck price

EIIOM-v4 должен рассчитывать shadow price специалиста:

```text
ShadowValue(skill_l, region_r)
 = marginal system value unlocked by +1 qualified worker
```

Это позволяет сравнить:

- построить ещё оборудование;
- обучить специалистов;
- повысить зарплаты;
- создать жильё;
- разрешить mobility;
- автоматизировать задачу.

## Education as capacity investment

Образование моделируется как delayed-capacity project:

```text
TrainingCAPEX[t]
  ↓ lag
QualifiedWorkers[t+lag]
  ↓
ProjectCapacityUnlocked
```

Completion, retention and placement rates are explicit.

## Corporate academies

Для дефицитных специальностей быстрее классических университетских циклов могут работать:

- apprenticeships;
- 6–18 month retraining;
- vendor academies;
- dual education;
- plant/university programs;
- digital twins/simulators;
- remote labs.

Качество подтверждается job performance, а не числом сертификатов.

## Housing as labor infrastructure

Жильё в v4 связано с workforce graph.

```text
Factory opens
  → labor demand
  → housing demand
  → school/health/transport demand
```

Если эти зависимости не закрыты, project FID должен видеть реальный labor-acquisition cost.

## Family economic stability

AI-CFO и Delta-layer — не только retail investing funnel. Финансово устойчивые семьи:

- имеют меньшую вероятность debt distress;
- могут менять работу и переучиваться;
- создают больше долгосрочных savings;
- легче участвуют в entrepreneurship;
- формируют более стабильный потребительский спрос.

Поэтому household financial resilience — экономическая инфраструктура.

## Health / productivity

Модель не должна присваивать человеку «стоимость жизни». Используется только planning relation между доступностью медицинской помощи, absenteeism, disability-adjusted work capacity, time-to-treatment и производительностью на агрегированном уровне.

Sensitive personal health data не используется EIIOM без специальной правовой основы и privacy architecture.

## Mobility

ЕАЭС уже имеет значимый общий рынок труда. В модели lawful mobility — отдельный ресурсный edge:

```text
WorkerFlow[l, r1 → r2, t]
```

с затратами:

- relocation;
- housing;
- family services;
- credential recognition;
- travel;
- adaptation.

Оптимизатор не должен считать людей безличным переносимым ресурсом: добровольность и социальные ограничения обязательны.

## Rural AI clusters and human capital

Новый rural cluster требует одновременно:

```text
productive jobs
+ quality housing
+ broadband
+ healthcare
+ school
+ transport
+ cultural/recreation minimum
```

Иначе новая инфраструктура не удержит кадры.

## Entrepreneurship pipeline

```text
Skill / Idea
  ↓
AI-CFO / Business OS
  ↓
Micro/P2P finance
  ↓
First customer
  ↓
Supplier history
  ↓
SME scale
  ↓
EIIOM cluster supplier
  ↓
institutional project finance
```

Это превращает household layer в supplier-generation machine.

## Inequality / concentration guardrail

Проект не должен максимизировать GVA ценой абсолютной концентрации gains.

Report at least:

```text
median household income effect
wage distribution
regional job creation
housing cost burden
SME share of procurement
ownership concentration
retail investor loss distribution
```

Эти метрики не обязаны входить в objective с одинаковым весом, но обязаны быть видимы.

## Social ROI

Для инфраструктуры:

```text
SocialValue =
  ProductivityGain
+ TimeSaved
+ Health/EducationAccessBenefit
+ HousingQualityBenefit
+ ResilienceBenefit
- LifecycleCost
- DisplacementCost
```

Это planning metric, не cashflow SPV.

## KPI 2045

Вместо только «миллион инженеров»:

- vacancy time for critical roles;
- training completion/placement;
- engineer/technician retention;
- real wage growth from productivity;
- household reserve runway;
- SME formation/survival;
- rural cluster occupancy;
- commute/travel time;
- housing cost burden;
- cross-country qualification portability.

## Human-first invariant

```text
SystemOptimization cannot consume:
  subsistence income,
  emergency reserve,
  involuntary relocation,
  hidden labor coercion
for a higher economic objective.
```

Экономика существует для повышения возможностей человека, а не человек для улучшения строки objective function.
