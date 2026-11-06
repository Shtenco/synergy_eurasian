# SYNERGY SUES — V7 Event and Realization Bridge V1

Status: executable structural adapter; research branch only. No accounting posting is performed.

## 1. Integration boundary

V7 and SUES have different responsibilities:
- V7 is the event-sourced economic graph and the realization evidence chain.
- SUES owns typed economic contracts, physical-flow and benefit attribution registries, subledger bridges and double-entry reference journal.
- Financial OS remains the canonical accounting authority; Pay System remains payment execution authority.

The V7 work currently exists in a separate research pull request. This adapter therefore has no import-time dependency on `synergy_v7`. It consumes the documented V7 event-store and realization-record shapes through structural interfaces. When the V7 branch is merged or installed, callers pass its EventStore and `evaluate_realization_chain` function directly.

## 2. Event-store adapter

`adapt_v7_event_store(event_store)` accepts a complete V7 event store exposing:
- `events`: append-ordered immutable event records;
- `verify()`: the source store's own chain-integrity check.

The SUES adapter independently checks:
- complete per-aggregate sequence starting at 1;
- event ID uniqueness;
- idempotency-key uniqueness;
- exact previous-hash continuity per aggregate;
- timezone-aware effective and recorded timestamps;
- JSON-object payloads without NaN/Infinity;
- SHA-256 event hash against the canonical V7 serialization;
- evidence-ID shape and uniqueness within each event.

The output is an immutable `SUESSourceEvent` tuple. The original event ID, hash, aggregate, sequence, event type, timestamps, source, evidence IDs, idempotency key and canonical payload are retained.

This is a verified source-envelope bridge, not a projection into inventory, AR/AP, cash, physical output or the GL. The current V7 core source implements `NODE_REGISTERED` and `EDGE_REGISTERED` graph projections. Other event names may appear in fixtures, but are not treated as stable production contracts without an implemented source handler and versioned payload schema.

A partial event slice is intentionally rejected: without the first event for each aggregate, the adapter cannot independently prove the hash-chain origin.

## 3. Versioned event projectors\n\n`src/synergy_sues/v7_projectors.py` adds a fail-closed allowlist keyed by `(event_type, schema_version)`. The initial registry contains only the two event types implemented by the inspected V7 core at PR #10 head `9c0aed72857493bac0a99ba6247ed726c554870e`:\n\n| Event | Schema version | Projection | Required payload |\n|---|---:|---|---|\n| `NODE_REGISTERED` | 1 | `GRAPH_NODE` | `node_id`, `node_type`; optional object `attributes` |\n| `EDGE_REGISTERED` | 1 | `GRAPH_EDGE` | `edge_id`, `source_id`, `target_id`, `relation`; optional object `attributes` |\n\nPayloads reject unknown fields, missing identifiers, non-object attributes and non-finite/non-JSON values. The event envelope in V7 does not currently carry a schema-version field; callers must supply the schema version explicitly to the projector API. Schema version 1 is therefore a declared compatibility contract for this projector, not a claim that V7 itself embeds that field. Projector implementation version is tracked separately.\n\n`replay_event_projections(...)` is deterministic and idempotent for exact repeated source events. It rejects conflicting event-ID/hash pairs, duplicate idempotency keys, duplicate graph node/edge IDs and dangling graph edges. Projection IDs are SHA-256 digests over source identity/hash, event/schema/projector versions and canonical projected payload. The function returns immutable read-model records only. It does not write to any ledger or authorize financial state changes.\n\n**Fail-closed rule:** `PRODUCTION_COMPLETED`, inventory, delivery, invoice and cash event names are not registered merely because similar names occur in tests or domain models. Production, inventory and cash projectors require source-owned event emitters, frozen payload schemas, explicit evidence requirements and replay fixtures first.\n\n## 4. Realization-chain adapter

`adapt_v7_realization_chain(...)` requires the V7 `evaluate_realization_chain` callable and the source collections:
- OutputObservation;
- DeliveryAcceptance;
- InvoiceDeliveryAllocation;
- TradeDocument;
- SettlementEvent;
- CollectionAttribution;
- CostObservation.

The V7 evaluator runs first. If it rejects any missing, inconsistent, over-allocated or over-settled link, no SUES bridge is returned.

On success, the adapter preserves each source row as an immutable `SUESRealizationLink`, including:
- source record type and ID;
- effective date when the V7 source actually supplies one;
- source and evidence references;
- explicit parent/related record IDs;
- enterprise/project/benefit-stream/period dimensions only where directly available or resolvable through an explicit delivery → output link;
- quantity and unit, or amount and currency, without cross-currency aggregation;
- evidence status where the V7 source defines one;
- canonical JSON of the original source row.

The validated V7 report is retained as canonical JSON in `SUESRealizationBridge.validated_report_json`. The adapter preserves the complete supplied source set, including future-dated rows; the V7 evaluator owns all `as_of` inclusion semantics. This keeps the evidence bridge replayable and prevents silent source-row loss.

## 5. Accounting and causal safety

The adapter deliberately does not:
- create or post JournalEntry records;
- create AR/AP documents or cash settlements;
- recognize revenue from invoice allocation;
- infer collection from settlement without explicit CollectionAttribution;
- treat output minus baseline as a causal treatment effect;
- translate currencies or combine unlike physical units;
- turn source classes into a higher evidence grade.

V7's explicit realization links remain the evidence source. A later, separately reviewed posting projector may convert an accepted event into a SUES subledger event only when its source event type, schema version, entity ownership, effective date, currency, evidence requirements and idempotency mapping are specified.

## 6. Acceptance tests

`tests/test_synergy_sues_v7_adapter.py` and `tests/test_synergy_sues_v7_projectors.py` cover:
- valid multi-event aggregate hash chains and preserved lineage;
- tampered payload/hash rejection;
- sequence-gap and duplicate-idempotency rejection;
- realization output → delivery → invoice allocation → settlement → collection attribution links;
- cost evidence and evidence-class preservation;
- fail-closed behavior when the V7 realization evaluator rejects a chain;\n- versioned graph-event projection, deterministic replay, exact-duplicate idempotency, unknown-type rejection, payload validation, graph referential integrity and registry collision checks.

## 7. Known limitations and next steps

1. Add versioned event-type projectors for V7 production completion, inventory movement, delivery acceptance and cash collection after their event payload schemas are frozen.
2. Add durable event-store checkpoint anchoring and signature verification; SHA-256 alone is not identity or authorization.
3. Add replay cursor and transactional outbox/inbox for retry-safe cross-subsystem delivery.
4. Add entity/account mapping and controlled journal projectors only under Financial OS ownership.
5. Add a versioned adapter compatibility matrix for V7 schema revisions.
6. Validate against the full V7 branch test suite once both research branches are available in one CI checkout.

This V1 is an interchange and evidence-preservation layer, not a production ERP integration or an authorization to move money.
