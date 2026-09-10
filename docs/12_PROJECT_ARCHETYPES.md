# 12 — Project Archetypes

Каждый archetype — шаблон для `ProjectProposal`, а не автоматически одобренная инвестиция.

## P01 — Grid / Transformer Bottleneck Removal

**Проблема:** новый compute/завод физически не может подключиться.

Inputs:

- requested MW;
- substation capacity;
- transformer lead time;
- cable/switchgear;
- connection queue;
- land/right-of-way.

Outputs:

- connected MW;
- outage reduction;
- projects unlocked;
- verified meter data.

Gate: downstream signed/credible demand.

## P02 — AI-ready Data Center + Compute

Разделяется на пять активов:

1. land/building;
2. grid/substation;
3. power train/cooling;
4. accelerator hardware;
5. cloud/workload layer.

Нельзя финансировать «500 MW data center» как один магический объект.

Gate:

```text
anchor workload
+ power >= 1.3x IT load
+ hardware path
+ network
+ cooling/water plan
```

## P03 — Industrial AI / Digital Twin

На существующем предприятии:

```text
baseline → AI pilot → A/B/counterfactual measurement → verified savings → scale
```

KPI:

- energy/unit;
- yield;
- downtime;
- scrap;
- maintenance cost;
- throughput;
- working capital.

Project may be financed as gain-share/ESCO-like contract rather than equipment sale.

## P04 — Power Electronics Plant

Products:

- transformers;
- UPS;
- converters;
- switchgear;
- industrial controllers;
- power modules where economic.

Gate: visible 24-month order book / offtake.

## P05 — Advanced Materials / Refining

Start from downstream requirement, not from extraction capacity.

```text
offtake → specification → refining/material line → qualification → production
```

Gate: contracted/credible offtake before FID.

## P06 — Robotics + Machine Tools

Priority: vertical industrial automation for existing factories, warehouses, mining and agriculture.

Avoid vanity deployment based only on robot count.

KPI:

- output/hour;
- labor-hours/unit;
- quality;
- uptime;
- payback;
- localization.

## P07 — Eurasian Seed Intelligence Node

Assets:

- germplasm/data access;
- genotyping;
- phenotyping;
- trial network;
- G×E modelling;
- seed multiplication partner.

Gate: field-validation protocol and official registration path.

## P08 — Precision Agriculture Upgrade

Upgrade package:

- satellite/drone monitoring;
- sensors;
- field maps;
- variable-rate application;
- autopilot;
- AI planning;
- yield/soil/water telemetry.

Measure pre/post economics by field cohort.

## P09 — Agro-Robotics Service Fleet

Instead of forcing each small farm to buy expensive machines, cluster SPV owns a shared fleet:

- autonomous tractors;
- spraying drones;
- harvest/inspection robots;
- maintenance depot.

Revenue: per-hectare/per-operation service.

## P10 — Food Processing / Cold Chain

Built only against known crop/livestock supply and demand.

KPI:

- raw throughput;
- value-added/unit;
- spoilage reduction;
- energy/unit;
- export revenue.

## P11 — Rural AI Cluster

Combined social + productive node:

- housing;
- basic services;
- broadband;
- agro stack;
- processing;
- logistics;
- remote-work capacity.

Gate: independent social/infrastructure readiness audit before residents move in.

## P12 — Urban Renovation Block

Inputs:

- building cohort/state;
- title/tenant registry;
- voluntary relocation agreements;
- temporary capacity;
- replacement rights;
- construction plan;
- land-value capture;
- utility upgrades.

Output: verified renovated/replaced m² and resident outcome.

## P13 — STEM / Engineering Pipeline

Not generic education spending. Must link cohorts to specific future bottlenecks:

```text
transformer engineers
industrial automation
power systems
AI/ML
agronomy/genomics
robotics
construction management
project finance
```

KPI: critical roles filled and retention.

## P14 — Semiconductor Design / EDA / IP

Focus on design, verification, domain-specific accelerators, firmware and IP where competitive.

Leading-edge fab is a separate future decision and requires its own economics.

## P15 — Logistics Corridor Digitization

- scheduling;
- customs/document automation;
- warehouse optimization;
- rail/road capacity planning;
- cold chain;
- port/terminal flows.

KPI: door-to-door time/cost and reliability.

## Project selection rule

Every archetype competes for capital in the same EIIOM queue. No sector has a permanent right to funding.

```text
Fund project only if:
  real bottleneck relieved
  + evidence measurable
  + downside acceptable
  + legal structure valid
  + physical dependencies secured
  + marginal system value beats alternatives
```
