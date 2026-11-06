# SYNERGY V7 — Event-Sourced Productive Economy Graph

**Status:** research reference kernel; initial implementation, not production accounting or a validated digital twin.  
**Date:** 2026-11-06

## 1. Why V7 exists

V1–V6 established separate but connected research capabilities: reproduction accounting, dynamic investment cohorts, stochastic stress, sector capital allocation, technology diffusion, complementarity and research-capability feedback. The V6.4–V6.5.6 resilience line separately studies production coordination, liquidity, supplier substitution and recovery.

The missing common substrate is a canonical, auditable economic state. V7 introduces that substrate. It does not replace prior optimizers; it gives them shared identities, time semantics, resource constraints, physical-flow accounting and benefit provenance.

## 2. Non-negotiable design rules

1. **Events are append-only.** Corrections are new compensating events, never silent mutation.
2. **Bitemporal facts.** Every event distinguishes when a fact is effective from when the system learned it.
3. **Stable identities.** Enterprise, asset, resource, technology, project, evidence and benefit stream IDs remain stable across model families.
4. **Evidence-qualified capacity.** Only OBSERVED and COMMITTED resource capacity is firm. Planned, announced, under-construction and scenario capacity cannot silently satisfy a hard constraint.
5. **Physical flows are not financial flows.** Internal transfers are reported separately and are never treated as new external output.
6. **Consolidated benefit attribution.** One enterprise × benefit stream × period can be claimed once. Net reproducible benefit deducts incremental OPEX and replacement obligation.
7. **Scenario is not fact.** Scenario, underwritten, verified and observed evidence classes remain explicit.
8. **Optimization is not authorization.** The engine produces evidence and candidate decisions; human, legal, safety and financial gates remain independent.

## 3. Initial implementation

| Module | Responsibility |
|---|---|
| `src/synergy_v7/core.py` | Immutable domain events, per-aggregate sequence, idempotency, SHA-256 hash chain, graph projection, dependency-cycle checks, physical flows, evidence-qualified resource capacity |
| `src/synergy_v7/ledger.py` | Benefit-stream uniqueness, net reproducible benefit, NPV, empirical upper-tail CVaR and Pareto frontier |
| `interfaces/synergy_v7_event.schema.json` | Interchange contract for event envelopes |
| `tests/test_synergy_v7_kernel.py` | Deterministic invariants and adversarial cases |

The implementation uses only the Python standard library. It is intentionally a small reference kernel, not a distributed event database. Hash chaining detects accidental or unauthorized modification relative to a trusted checkpoint; it does not by itself provide signatures, trusted timestamps, access control, consensus, or legal non-repudiation.

## 4. Canonical event envelope

Each event carries:
- `event_id`, `aggregate_type`, `aggregate_id`, `sequence`;
- `event_type` and JSON `payload`;
- `effective_at` and `recorded_at`, both timezone-aware;
- `source_ref`, `evidence_ids`, optional `idempotency_key`;
- `previous_hash` and computed `event_hash`.

Graph projections are rebuilt from `NODE_REGISTERED` and `EDGE_REGISTERED` events. The event log is the source of truth; graph objects are derived views.

## 5. Resource feasibility

A resource commitment is valid only against a matching resource ID, period and unit. The kernel rejects missing capacity states, unit mismatch, overcommitment and capacity whose evidence status is not OBSERVED or COMMITTED. Proposed commitments are excluded by default and can be included explicitly for scenario analysis.

The first release uses period buckets. V7.1 should add sub-period scheduling, conversion yields, network losses, geographic transfer limits, storage state-of-charge, maintenance outages and resource substitution.

## 6. Physical and financial consolidation

Physical exports, imports and final use are tracked separately from internal movement. An internal flow can be operationally important but does not create consolidated output merely by crossing an organizational boundary.

For a benefit claim:

`net_reproducible_benefit = gross_incremental_benefit - incremental_opex - replacement_obligation`

This is a conservative minimum, not a complete accounting standard. Later releases must also model taxes, working capital, financing costs, externalities, quality, service continuity and counterfactual attribution. Cash NPV is calculated separately from physical-output, labor-time, resilience and innovation-capacity indicators.

## 7. Risk and portfolio comparison

The kernel includes empirical upper-tail CVaR as the mean of the worst loss observations and a Pareto-frontier filter. This is a descriptive risk statistic, not a formal CVaR-constrained optimizer. A future solver must define loss distributions, confidence level, scenario weights, decision variables and feasibility constraints explicitly.

No single weighted score should erase trade-offs between NPV, essential output, unit cost, continuity, resilience, labor time and innovation capacity. The Pareto set is retained for governance review.

## 8. V7.2 implementation status

V7.2 adds operating working-capital metrics (NWC, DSO, DIO, DPO and CCC) plus a prioritized cash waterfall: OPEX → replacement → debt service → reserve top-up → growth CAPEX → distributions. Financing proceeds and internal transfers are kept separate from consolidated external operating cash generation. This is a period-level control calculator, not double-entry accounting. See [V7.2 design](48_SYNERGY_V7_2_WORKING_CAPITAL_AND_CASH_WATERFALL.md).

## 9. V7 roadmap

### V7.1 — temporal resource network
- time-expanded graph; multi-period reservations and commissioning;
- material/energy conversion coefficients and loss accounting;
- supplier/customer capacities and transport constraints;
- inventories, working capital and receivables/payables ageing.

### V7.2 — enterprise operating model
- production recipes, bills of materials, yields, scrap and quality;
- asset lifecycle, maintenance, depreciation and replacement schedules;
- external customer demand, contracts and settlement evidence;
- cash waterfall: OPEX → replacement → debt service → reserves → growth.

### V7.3 — technology adoption and causal evaluation
- technology compatibility, prerequisites, deployment cohorts and diffusion;
- baseline/counterfactual design, control groups and measurement uncertainty;
- evidence provenance, confidence grades and audit replay;
- benefit attribution across enterprise, project, technology and network without duplication.

### V7.4 — resilience and formal risk
- correlated supplier, energy, logistics, cyber and climate shocks;
- liquidity waterfall, recovery time and critical-service minimums;
- formal CVaR constraints and chance constraints;
- robust and stochastic optimization with out-of-sample validation.

### V7.5 — learning network
- verified reusable technology packages and implementation playbooks;
- R&D throughput, experiment costs, replication success and diffusion lag;
- capability reproduction tracked separately from cash NPV;
- feedback into V4–V6 optimizers through versioned interfaces.

## 9. Acceptance gates before production use

- append-only storage with durable backups and independently anchored hash checkpoints;
- signed evidence and role-based authorization;
- deterministic replay and schema migration tests;
- concurrency, idempotency and disaster-recovery tests;
- independent accounting, safety, legal and cybersecurity review;
- calibration against real enterprise records and out-of-sample periods;
- no automated token issuance, lending, payment or securities decision from optimizer output.

## 10. How to run

```bash
python -m pytest -q tests/test_synergy_v7_kernel.py
```

The kernel is a research foundation. It must not be represented as an operational ERP, regulated ledger, audited financial statement or proof of actual economic impact.
