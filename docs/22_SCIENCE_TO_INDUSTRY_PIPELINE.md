# 22 — Science → Industry → Export Pipeline

## Главная задача

СИНЕРГИЯ должна уметь не только выбирать между уже известными заводами, но и превращать собственные научные гипотезы в промышленную технологию — **не перепрыгивая через доказательства**.

## Полный pipeline

```text
Research Question
  ↓
Literature / Patent / Dataset Search
  ↓
Evidence Graph
  ↓
Hypothesis
  ↓
Simulation / Analytical Model
  ↓
Adversarial Falsification
  ↓
Independent Reproduction Attempt
  ↓
Laboratory Experiment
  ↓
Prototype
  ↓
Pilot
  ↓
TRL Gate
  ↓
IP / Freedom-to-Operate
  ↓
Economic Pre-Feasibility
  ↓
ProjectProposal
  ↓
Underwriting
  ↓
Demonstration Plant
  ↓
Commercial Scale
  ↓
External Revenue / Export
```

## Domain roles

### `nexus_science_agent`

- source search;
- evidence graph;
- claim quality;
- contradiction search;
- experiment proposals;
- reproduction packages;
- uncertainty.

### `agi_nexus`

- bounded reasoning;
- model synthesis;
- planning;
- hypothesis-space search.

### `ai_coder`

- reproducible code;
- simulation/analysis tooling;
- tests;
- provenance.

### `synergy_eurasian`

- physical resource requirements;
- market/demand;
- CAPEX/OPEX;
- supply-chain constraints;
- project ranking.

### `synergy_financial_os`

- funding capacity;
- accounting;
- liabilities;
- evidence-based recognition.

## Technology Readiness Gates

```text
TRL-0/1  idea / scientific principle
TRL-2    formulated concept
TRL-3    analytical / experimental proof-of-concept
TRL-4    lab validation
TRL-5    relevant-environment validation
TRL-6    prototype demonstration
TRL-7    operational pilot
TRL-8    qualified system
TRL-9    repeated commercial operation
```

EIIOM must apply a **TRL-adjusted value haircut**.

Example structure:

```text
RiskAdjustedTechValue
 = UnriskedProjectValue
 * P(science works)
 * P(engineering scale)
 * P(certification)
 * P(market adoption)
```

Probabilities must be explicit scenarios, not hidden optimism.

## Research portfolio logic

Большая ошибка — финансировать только один moonshot. Правильнее иметь барбелл:

```text
70% near/mid-TRL productivity projects
20% strategic platform R&D
10% high-risk/high-option moonshots
```

Это illustrative policy, not mandatory allocation.

## Priority scientific families for Eurasian productive economy

### Materials

- advanced alloys;
- power electronics materials;
- catalysts;
- battery/storage materials;
- thermal-management materials;
- corrosion/wear;
- recycling/refining.

### Energy

- grid optimization;
- nuclear lifecycle/industrial heat where lawful;
- storage;
- heat pumps;
- industrial waste-heat recovery;
- hydrogen only where end-use economics closes;
- experimental LENR/cold-nuclear work remains research until independently reproduced.

### Agriculture/Biology

- genomic prediction;
- stress-resistant crops;
- soil microbiome where evidence supports;
- controlled environment agriculture;
- crop disease detection;
- water efficiency;
- feed/livestock productivity.

### Compute / Electronics

- power conversion;
- domain-specific accelerators;
- packaging;
- edge AI;
- efficient inference;
- XPU/dataflow research;
- compilers/runtime.

### Manufacturing

- robotics;
- machine vision;
- additive manufacturing;
- digital twins;
- predictive maintenance;
- process control;
- quality automation.

## Science marketplace

Research institutions/teams can publish standardized `TechnologyCandidate`:

```text
technology_id
problem
claimed_effect
baseline
experimental_status
replications
TRL
required_capex_to_next_gate
critical_materials
energy_requirements
IP_status
FTO_status
expected_market
failure_modes
evidence_hashes
```

EIIOM ranks **funding to the next evidence gate**, not immediately full-scale factory CAPEX.

## Option-value financing

For early technology:

```text
Stage1 grant/equity → prove X
Stage2 capital       → prove Y
Stage3 pilot         → prove commercial KPI
Stage4 scale         → only after commercial evidence
```

This prevents a weak scientific assumption from consuming an industrial-scale budget.

## Negative results are assets

The Data Fabric stores failed experiments with provenance.

```text
FailedHypothesis
  → prevents duplicate spending
  → improves model priors
  → redirects capital
```

A well-proven negative result can have positive economic value.

## Commercialization route

```text
TechnologyCandidate
  ↓
Pilot customer
  ↓
Measured gain
  ↓
IP / licensing / manufacturing choice
  ↓
Supplier qualification
  ↓
EIIOM localization decision
  ↓
Commercial product
```

Not every invention needs a new factory. Options:

- license to existing plant;
- JV;
- retrofit existing line;
- contract manufacturing;
- own SPV only if economics justify.

## Export-first evidence

Technology has stronger system value if it can earn external revenue.

```text
SystemValueBonus ∝ verified external demand / exportability
```

But exportability does not override domestic safety, strategic or legal constraints.

## Research integrity

```text
Simulation != Experiment
Patent != Working Product
Prototype != Commercial Product
Backtest != Cash
Internal Citation != Independent Replication
```

This constitution is especially important for high-uncertainty scientific projects.
