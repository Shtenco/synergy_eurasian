# 21 — Eurasian Digital Infrastructure: Compute, Data, Network, Trust

## Идея

Индустриальный AI невозможен без физического цифрового слоя. Но цифровая инфраструктура имеет несколько независимых функций и не должна схлопываться в «один блокчейн».

```text
POWER / GRID
   ↓
PHYSICAL COMPUTE
   ↓
HOST / META-OS
   ↓
DATA FABRIC
   ↓
SYNERGYNET
   ↓
AI / APPLICATION SERVICES
   ↓
TRUST COMMITMENTS / METACHAIN
```

## D0 — Power before compute

Для любого AI node:

```text
IT_Load_MW
× PUE
× AvailabilityMargin
<= ContractedPowerMW
```

И отдельно:

```text
ContractedPowerMW <= GridDeliverableMW
```

Наличие электростанции в стране не означает наличие свободной мощности в конкретной подстанции.

## D1 — Compute portfolio

Не строить только giant GPU campuses. Оптимальный портфель разделяется:

### Tier A — Central AI/HPC

- training;
- large simulation;
- national/industrial foundation models;
- scientific compute.

### Tier B — Regional inference / industrial cloud

- factories;
- logistics;
- healthcare/education workloads where lawful;
- digital twins;
- enterprise inference.

### Tier C — Edge industrial compute

- farms;
- mines;
- substations;
- factories;
- robots;
- rural clusters;
- low-latency control.

### Tier D — Research hardware

TURBO/XPU and other experimental architectures remain in R&D until matched benchmarks and hardware/emulation evidence exist.

## D2 — Data Fabric

Source repositories:

- `ai_compress`;
- `qr_compress`;
- storage layers of domain systems.

Every economic/scientific object has two identities:

```text
canonical_content_hash = identity of semantic source bytes/object
archive_hash           = identity of compressed container
```

Codec changes must not change economic identity.

### Data classes

```text
PUBLIC
PARTNER
CONFIDENTIAL_BUSINESS
PERSONAL
FINANCIAL_RESTRICTED
STATE/CRITICAL_INFRASTRUCTURE_RESTRICTED
```

EIIOM must work with aggregates/federated features when raw data cannot legally leave the source domain.

## D3 — SynergyNet

SynergyNet is a P2P content/evidence transport overlay.

Possible value:

- local-first transfer;
- content-addressed cache;
- deduplication;
- resilient multipath routing;
- store-and-forward;
- compression-aware transport;
- remote industrial/rural connectivity support.

But:

```text
P2P node != validator
P2P node != bank
P2P node != treasury signer
P2P node != accounting authority
```

### Required benchmark

Before claims of superiority:

```text
SynergyNet vs QUIC/HTTP3 vs selected P2P baseline
same files
same hardware
same WAN impairment
same security level
same CPU/memory measurement
```

Metrics:

- latency;
- goodput;
- first-byte latency;
- bytes-on-wire;
- cache hit;
- dedup savings;
- CPU;
- memory;
- failure recovery.

## D4 — Meta-OS

`synergy_meta_os` runs services on a node, but does not merge authority.

Node profiles:

```text
EDGE_CLIENT
P2P_RELAY
CONTENT_CACHE
NEXUS_COMPUTE
BLOCKCHAIN_PEER
BLOCKCHAIN_VALIDATOR
METAPAY_GATEWAY
FINANCIAL_SERVICE
BUSINESS_AUTOPILOT
FULL_SYNERGY_NODE
```

High-risk roles require explicit signed manifest + attestation + policy.

## D5 — Post-Quantum Trust

`synergy_metachain` bootstrap research already defines fail-closed policies and target ML-DSA/SLH-DSA/light-client boundaries.

For Eurasian deployment, trust should be layered:

```text
Domain Authority Artifact
  ↓
Canonical Encoding
  ↓
Hash
  ↓
Domain-separated Signature
  ↓
Checkpoint
  ↓
Optional cross-chain proof
```

Blockchain proves exact commitment, not meaning.

### Production prerequisites

- standards-conformant PQ primitives;
- deterministic cross-client vectors;
- concrete external-chain light clients;
- event inclusion proofs;
- replay protection;
- persistent external-host validator evidence;
- independent security audit;
- key lifecycle/HSM/MPC procedures.

Until then: research/testnet only.

## D6 — Digital sovereignty without isolation

Цель не «отрезать Евразию от мирового Интернета». Цель — иметь возможность продолжать critical operations при потере отдельных внешних сервисов.

Resilience model:

```text
local identity
+ local data copies
+ local compute
+ local model serving
+ local settlement fallback where lawful
+ multiple external gateways
```

Это resilience, а не autarky.

## D7 — Industrial Digital Twin Bus

Каждый real-economy node публикует machine-readable state:

```text
AssetID
Capacity
Utilization
PowerDraw
InputInventory
OutputInventory
MaintenanceState
OrderBook
Quality
Downtime
EvidenceTimestamp
```

EIIOM использует эти данные только после data-quality and authority checks.

## D8 — Compute economics

Проект compute оценивается не по MW, а по:

```text
UsefulComputeValue =
  ContractedWorkloadRevenue
+ IndustrialProductivitySavings
+ ScientificOptionValue
- Power
- HardwareDepreciation
- Cooling
- Network
- Staff
- Financing
- ObsolescenceRisk
```

### Accelerator obsolescence

AI hardware имеет короткий economic life относительно электростанции/здания. Поэтому shell, power, cooling and accelerators должны быть отдельными asset classes и depreciation schedules.

## D9 — XPU strategy

`motherboard_xpu_xml` рассматривается как long-option:

1. formal compiler/dataflow model;
2. software emulator;
3. FPGA/prototype;
4. matched kernel benchmarks;
5. utilization/energy studies;
6. only then ASIC/chiplet economics.

Никакой CAPEX на массовый silicon не входит в BASE, пока предыдущие gates не доказаны.

## D10 — Eurasian AI utility

Долгосрочная цель — не одна giant model, а common AI utility:

```text
shared standards
+ federated data contracts
+ model registry
+ compute marketplace
+ industrial digital twins
+ verified AI services
```

Каждая страна/организация может хранить sensitive raw data локально, но использовать interoperable models and evidence formats.

## Economic invariant

```text
DigitalInfrastructureValue
  = value of useful services delivered
  - lifecycle cost
  - risk
```

Количество nodes, tokens, hashes, GPUs или PB данных само по себе не является экономическим результатом.
