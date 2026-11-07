from dataclasses import dataclass
from hashlib import sha256
import json

import pytest

from synergy_sues.v7_adapter import SUESSourceEvent, adapt_v7_event_store
from synergy_sues.v7_projectors import (
    DEFAULT_PROJECTOR_REGISTRY,
    ProjectorRegistry,
    ProjectorSpec,
    replay_event_projections,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    sequence: int
    event_type: str
    effective_at: str
    recorded_at: str
    payload: dict
    source_ref: str
    evidence_ids: tuple = ()
    idempotency_key: str = ""
    previous_hash: str = ""
    event_hash: str = ""


class EventStore:
    def __init__(self, events):
        self.events = tuple(events)

    def verify(self):
        return True


def source_event(event_id, sequence, event_type, payload, previous_hash=""):
    row = DomainEvent(
        event_id, "PROJECT", "project-1", sequence, event_type,
        "2026-11-06T08:00:00+00:00", "2026-11-06T08:01:00+00:00",
        payload, f"source:{event_id}", (f"evidence:{event_id}",),
        f"idem:{event_id}", previous_hash, "",
    )
    unsigned = {
        "event_id": row.event_id, "aggregate_type": row.aggregate_type,
        "aggregate_id": row.aggregate_id, "sequence": row.sequence,
        "event_type": row.event_type, "effective_at": row.effective_at,
        "recorded_at": row.recorded_at, "payload": row.payload,
        "source_ref": row.source_ref, "evidence_ids": row.evidence_ids,
        "idempotency_key": row.idempotency_key, "previous_hash": previous_hash,
    }
    digest = sha256(canonical(unsigned).encode("utf-8")).hexdigest()
    sealed = DomainEvent(**{**row.__dict__, "event_hash": digest})
    return adapt_v7_event_store(EventStore([sealed]))[0]


def graph_events():
    node_a = source_event("e1", 1, "NODE_REGISTERED", {
        "node_id": "project-a", "node_type": "PROJECT", "attributes": {"region": "KZ"}
    })
    node_b = source_event("e2", 1, "NODE_REGISTERED", {
        "node_id": "factory-a", "node_type": "ASSET"
    })
    edge = source_event("e3", 1, "EDGE_REGISTERED", {
        "edge_id": "edge-1", "source_id": "project-a",
        "target_id": "factory-a", "relation": "OWNS",
    })
    return node_a, node_b, edge


def test_default_registry_projects_only_v7_core_graph_event_types():
    a, b, edge = graph_events()
    projected = replay_event_projections([a, b, edge])
    assert [row.projection_type for row in projected] == [
        "GRAPH_NODE", "GRAPH_NODE", "GRAPH_EDGE"
    ]
    assert json.loads(projected[0].payload_json)["node_id"] == "project-a"
    assert projected[2].source_event_hash == edge.source_event_hash


def test_projection_identity_and_replay_are_deterministic():
    events = graph_events()
    first = replay_event_projections(events)
    second = replay_event_projections(events)
    assert first == second
    assert [row.projection_id for row in first] == [row.projection_id for row in second]


def test_exact_duplicate_event_is_idempotently_ignored():
    events = graph_events()
    projected = replay_event_projections([events[0], events[0], events[1], events[2]])
    assert len(projected) == 3


def test_conflicting_event_id_and_duplicate_idempotency_fail_closed():
    event = graph_events()[0]
    changed_hash = type(event)(**{**event.__dict__, "source_event_hash": "f" * 64})
    with pytest.raises(ValueError, match="Conflicting source event ID"):
        replay_event_projections([event, changed_hash])

    other = source_event("other", 1, "NODE_REGISTERED", {"node_id": "other", "node_type": "ASSET"})
    duplicate_key = type(other)(**{
        **other.__dict__, "idempotency_key": event.idempotency_key
    })
    with pytest.raises(ValueError, match="Duplicate source idempotency key"):
        replay_event_projections([event, duplicate_key])


def test_unknown_production_event_is_not_guessed_or_projected():
    event = source_event("prod-1", 1, "PRODUCTION_COMPLETED", {
        "order_id": "batch-1", "quantity": "10"
    })
    with pytest.raises(ValueError, match="No projector registered"):
        replay_event_projections([event])


def test_schema_version_must_be_explicitly_registered():
    event = graph_events()[0]
    with pytest.raises(ValueError, match="schema v2"):
        DEFAULT_PROJECTOR_REGISTRY.project(event, schema_version=2)


def test_payload_contract_rejects_unknown_fields_and_invalid_attributes():
    bad = source_event("bad-1", 1, "NODE_REGISTERED", {
        "node_id": "n1", "node_type": "PROJECT", "owner": "unapproved"
    })
    with pytest.raises(ValueError, match="unsupported fields"):
        replay_event_projections([bad])

    bad_attributes = source_event("bad-2", 1, "NODE_REGISTERED", {
        "node_id": "n2", "node_type": "PROJECT", "attributes": []
    })
    with pytest.raises(ValueError, match="attributes must be an object"):
        replay_event_projections([bad_attributes])


def test_graph_projection_rejects_duplicate_node_ids_and_dangling_edges():
    first = source_event("n1", 1, "NODE_REGISTERED", {"node_id": "same", "node_type": "PROJECT"})
    second = source_event("n2", 1, "NODE_REGISTERED", {"node_id": "same", "node_type": "ASSET"})
    with pytest.raises(ValueError, match="Duplicate projected graph node"):
        replay_event_projections([first, second])

    dangling = source_event("edge", 1, "EDGE_REGISTERED", {
        "edge_id": "e", "source_id": "missing-a", "target_id": "missing-b", "relation": "OWNS"
    })
    with pytest.raises(ValueError, match="Dangling projected graph edge"):
        replay_event_projections([dangling])


def test_registry_rejects_duplicate_registration():
    handler = lambda payload: ("TEST", dict(payload))
    with pytest.raises(ValueError, match="Duplicate projector registration"):
        ProjectorRegistry((
            ProjectorSpec("NODE_REGISTERED", 1, 1, handler),
            ProjectorSpec("NODE_REGISTERED", 1, 2, handler),
        ))



def test_projector_rejects_forged_or_copied_source_event_instances():
    verified = graph_events()[0]
    forged = SUESSourceEvent(**verified.__dict__)
    with pytest.raises(ValueError, match="exact SUESSourceEvent instances"):
        DEFAULT_PROJECTOR_REGISTRY.project(forged)
    with pytest.raises(ValueError, match="exact SUESSourceEvent instances"):
        replay_event_projections([forged])
