# 35 — DATASET-v4: point-in-time data fabric for the Eurasian economic twin

## Цель

EIIOM-v4 становится полезным только тогда, когда может воспроизвести состояние экономики **на конкретную дату**, не подглядывая в будущее и не смешивая построенные объекты с анонсированными.

Поэтому основной актив следующей версии — не новый solver, а **point-in-time Eurasian panel**.

## Два времени

Каждая запись должна иметь:

```text
effective_time  — когда факт относится к реальному миру
known_at        — когда этот факт стал доступен системе
```

Для backtest/planning replay:

```text
known_at <= decision_time
```

Иначе возникает экономический lookahead bias.

## Common metadata

```text
record_id
entity_id
metric
value
unit
currency
price_basis
real_or_nominal
geography
effective_from
effective_to
known_at
source_url
publisher
publication_date
retrieved_at
source_class
confidence
observed_committed_planned
revision_id
supersedes
license/access_class
content_hash
```

## Dataset families

### 1. Demography / Households

Aggregated only unless explicit legal basis:

- population;
- households;
- age cohorts;
- labor participation;
- income distribution;
- expenditure distribution;
- debt burden;
- savings/deposits;
- housing burden;
- migration.

No raw personal financial/health data in EIIOM core.

### 2. Labor / Skills

- occupations;
- vacancies;
- wages;
- graduates;
- training seats;
- credential recognition;
- migration flows;
- vacancy duration.

### 3. Enterprises / Industry

- plants/sites;
- product classes;
- rated capacity;
- utilization;
- energy intensity;
- inputs/outputs;
- employment;
- investment;
- export/import dependency;
- maintenance/shutdown state where public/authorized.

### 4. Trade / Demand

- EAEU mutual trade;
- external trade;
- customs product classes;
- price/volume;
- origin/destination;
- persistent imports;
- export market growth;
- public procurement;
- B2B demand signals from Business OS with permission.

### 5. Energy

- generators;
- capacity;
- generation;
- fuel;
- outages;
- wholesale prices where available;
- substations;
- transmission limits where publishable;
- connection queues;
- planned projects.

Security-sensitive grid data must be access-controlled/aggregated.

### 6. Compute / Digital

- data-center locations;
- shell capacity;
- IT load;
- PUE;
- power contract;
- hardware class;
- hardware age;
- workload utilization;
- fiber/IXP connectivity;
- cloud service demand.

### 7. Materials / Mining / Processing

- reserves/resources where public;
- production;
- refining;
- product grade;
- processing capacity;
- energy/water intensity;
- export/import;
- planned expansions.

### 8. Logistics

Use real corridor/project registries:

- rail segments;
- roads;
- terminals;
- ports/dry ports;
- border crossings;
- warehouses;
- cold chain;
- project status;
- capacity;
- travel/transit time;
- tariffs/cost;
- reliability.

### 9. Agriculture

- field polygons where legally/publicly available;
- crop;
- yield;
- soil;
- weather;
- irrigation;
- machinery;
- input costs;
- storage;
- processing;
- seed varieties;
- trial results;
- disease/stress observations.

### 10. Water

- basin;
- renewable flow;
- storage;
- withdrawal;
- irrigation demand;
- industrial demand;
- household demand;
- environmental constraints;
- drought scenarios.

### 11. Housing / Cities

- building polygons;
- construction year;
- structure type;
- condition;
- floor area;
- occupancy aggregate;
- utility state;
- renovation status;
- land-use/zoning;
- transport access;
- school/health capacity.

### 12. Finance

Aggregated/project-level:

- risk-free/reference rates;
- sovereign/corporate spreads;
- lending rates;
- FX;
- project debt terms;
- bond/CFA terms;
- insurance;
- development finance;
- capital market depth.

Canonical balance-sheet truth stays in Financial OS.

### 13. Science / Technology

- TechnologyCandidate;
- TRL;
- experiment evidence;
- patents;
- freedom-to-operate;
- prototype cost;
- pilot performance;
- replication status.

### 14. Regulatory / Legal

Versioned rules:

- cross-border trade;
- customs;
- investments;
- securities/CFA;
- payments;
- data;
- energy market;
- construction;
- environmental;
- seed/agro;
- labor mobility.

Legal state is time-dependent and must be point-in-time.

## Observed vs Committed vs Planned

Mandatory enum:

```text
OBSERVED
COMMITTED
UNDER_CONSTRUCTION
PLANNED
ANNOUNCED
SCENARIO
```

Production capacity calculation may include only eligible statuses according to decision date.

## Revision handling

Statistics are revised. Never overwrite silently.

```text
record_v1
→ record_v2 supersedes v1
```

Replay for old decision uses what was known then; current dashboard uses newest valid revision.

## Currency normalization

Store native currency and reporting conversion separately:

```text
native_value
native_currency
fx_rate
fx_source
fx_as_of
reporting_value
reporting_currency
```

For CAPEX comparisons also store nominal vs real price basis.

## Spatial IDs

Preferred hierarchy:

```text
country
admin1
admin2
municipality
site
asset
```

Keep geometry separately and reference `geometry_id`.

## Entity resolution

One factory can appear under multiple company/project names.

Need canonical:

```text
entity_id
legal_entity_ids
site_ids
aliases
source_records
confidence
```

Do not merge uncertain entities automatically.

## Demand without survivorship bias

For project backtests, include:

- failed firms/projects;
- closed plants;
- canceled infrastructure;
- delisted/obsolete products where relevant;
- declined demand categories;
- project overruns and defaults.

Training only on successful operating assets will systematically exaggerate project quality.

## Project failure dataset

A first-class table:

```text
project_id
stage_failed
reason
capex_spent
recovery_value
schedule_delay
demand_error
technical_error
regulatory_error
financing_error
management_error
external_shock
```

This dataset may become more valuable than success stories for risk calibration.

## Evidence linkage

Every important project KPI can point to `EvidencePackage`:

```text
metric_record.evidence_ids[]
```

Raw evidence can reside in Data Fabric; EIIOM stores content-addressed references and authorized derived metrics.

## Data quality score

Conceptual:

```text
DQ = f(
  source_authority,
  freshness,
  completeness,
  consistency,
  directness,
  revision_stability,
  independent_confirmation
)
```

Low-DQ input increases uncertainty rather than being silently treated as precise.

## Train / calibration / evaluation split

Economic optimizer calibration should use temporal splits.

Example:

```text
CALIBRATION: <= 2022
VALIDATION:  2023–2024
HOLDOUT:     2025
FORWARD:     2026+
```

Actual split depends on dataset availability; never optimize coefficients directly on the same project outcomes used to claim validation.

## Data sovereignty

Architecture supports:

```text
central public data
+ federated private data
+ secure derived aggregates
+ model-to-data execution
```

Not all industrial datasets need to be physically centralized.

## Minimal v4 dataset release

Before claiming spatial optimization:

```text
≥3 regions
≥50 physical/economic nodes
≥100 transport/grid/resource edges
≥20 real project candidates
≥5 years of historical demand/price where relevant
point-in-time metadata
failure/canceled examples
source manifest
```

## Golden rule

> **A better solver cannot rescue a bad point-in-time dataset. DATASET-v4 is the main bottleneck of the next generation.**
