"""Fail-closed, deterministic V7 event projectors for SUES.

Only event types implemented by the inspected V7 core are registered here:
NODE_REGISTERED and EDGE_REGISTERED. This module creates read-model records only;
it never mutates journals, subledgers, payment systems, or legal state.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Callable, Iterable, Mapping

from .v7_adapter import SUESSourceEvent, _canonical


@dataclass(frozen=True)
class SUESProjection:
    projection_id: str
    projection_type: str
    source_event_id: str
    source_event_hash: str
    event_type: str
    schema_version: int
    projector_version: int
    payload_json: str


@dataclass(frozen=True)
class ProjectorSpec:
    event_type: str
    schema_version: int
    projector_version: int
    handler: Callable[[Mapping[str, Any]], tuple[str, dict[str, Any]]]


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _node_registered(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    allowed = {"node_id", "node_type", "attributes"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"NODE_REGISTERED has unsupported fields: {sorted(unknown)}")
    node_id = _required_text(payload, "node_id")
    node_type = _required_text(payload, "node_type")
    attributes = payload.get("attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("NODE_REGISTERED attributes must be an object")
    # Canonicalization rejects NaN, Infinity and non-JSON payload values.
    _canonical(attributes)
    return "GRAPH_NODE", {
        "node_id": node_id,
        "node_type": node_type,
        "attributes": attributes,
    }


def _edge_registered(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    allowed = {"edge_id", "source_id", "target_id", "relation", "attributes"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"EDGE_REGISTERED has unsupported fields: {sorted(unknown)}")
    edge_id = _required_text(payload, "edge_id")
    source_id = _required_text(payload, "source_id")
    target_id = _required_text(payload, "target_id")
    relation = _required_text(payload, "relation")
    attributes = payload.get("attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("EDGE_REGISTERED attributes must be an object")
    _canonical(attributes)
    return "GRAPH_EDGE", {
        "edge_id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "relation": relation,
        "attributes": attributes,
    }


class ProjectorRegistry:
    """Immutable-by-convention allowlist keyed by (event_type, schema_version)."""

    def __init__(self, specs: Iterable[ProjectorSpec]):
        rows = tuple(specs)
        keys = [(row.event_type, row.schema_version) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate projector registration")
        for row in rows:
            if not row.event_type or row.schema_version < 1 or row.projector_version < 1:
                raise ValueError("Invalid projector registration metadata")
            if not callable(row.handler):
                raise ValueError("Projector handler must be callable")
        self._specs = {(row.event_type, row.schema_version): row for row in rows}

    def project(
        self, event: SUESSourceEvent, schema_version: int = 1
    ) -> SUESProjection:
        if not isinstance(event, SUESSourceEvent):
            raise ValueError("Projectors accept only verified SUESSourceEvent records")
        spec = self._specs.get((event.event_type, schema_version))
        if spec is None:
            raise ValueError(
                f"No projector registered for {event.event_type!r} schema v{schema_version}"
            )
        try:
            payload = json.loads(event.payload_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Source event payload_json is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Source event payload must decode to an object")
        projection_type, projected = spec.handler(payload)
        canonical_payload = _canonical(projected)
        identity = {
            "source_event_id": event.source_event_id,
            "source_event_hash": event.source_event_hash,
            "event_type": event.event_type,
            "schema_version": schema_version,
            "projector_version": spec.projector_version,
            "projection_type": projection_type,
            "payload_json": canonical_payload,
        }
        projection_id = sha256(_canonical(identity).encode("utf-8")).hexdigest()
        return SUESProjection(
            projection_id=projection_id,
            projection_type=projection_type,
            source_event_id=event.source_event_id,
            source_event_hash=event.source_event_hash,
            event_type=event.event_type,
            schema_version=schema_version,
            projector_version=spec.projector_version,
            payload_json=canonical_payload,
        )


DEFAULT_PROJECTOR_REGISTRY = ProjectorRegistry((
    ProjectorSpec("NODE_REGISTERED", 1, 1, _node_registered),
    ProjectorSpec("EDGE_REGISTERED", 1, 1, _edge_registered),
))


def replay_event_projections(
    events: Iterable[SUESSourceEvent],
    registry: ProjectorRegistry = DEFAULT_PROJECTOR_REGISTRY,
    schema_version: int = 1,
) -> tuple[SUESProjection, ...]:
    """Replay a complete ordered event stream deterministically and idempotently.

    An exact duplicate source event is ignored. Reuse of an event ID with a
    different hash, or reuse of an idempotency key by another event, fails closed.
    The final graph projection is checked for duplicate IDs and dangling edges.
    """
    output: list[SUESProjection] = []
    by_event_id: dict[str, str] = {}
    by_idempotency: dict[str, str] = {}
    nodes: set[str] = set()
    edges: set[str] = set()
    edge_refs: list[tuple[str, str]] = []

    for event in events:
        if not isinstance(event, SUESSourceEvent):
            raise ValueError("Replay accepts only verified SUESSourceEvent records")
        prior_hash = by_event_id.get(event.source_event_id)
        if prior_hash is not None:
            if prior_hash != event.source_event_hash:
                raise ValueError(f"Conflicting source event ID: {event.source_event_id}")
            continue
        if event.idempotency_key:
            prior_event = by_idempotency.get(event.idempotency_key)
            if prior_event is not None and prior_event != event.source_event_id:
                raise ValueError(f"Duplicate source idempotency key: {event.idempotency_key}")

        projection = registry.project(event, schema_version)
        body = json.loads(projection.payload_json)
        if projection.projection_type == "GRAPH_NODE":
            node_id = body["node_id"]
            if node_id in nodes:
                raise ValueError(f"Duplicate projected graph node: {node_id}")
            nodes.add(node_id)
        elif projection.projection_type == "GRAPH_EDGE":
            edge_id = body["edge_id"]
            if edge_id in edges:
                raise ValueError(f"Duplicate projected graph edge: {edge_id}")
            edges.add(edge_id)
            edge_refs.append((body["source_id"], body["target_id"]))

        output.append(projection)
        by_event_id[event.source_event_id] = event.source_event_hash
        if event.idempotency_key:
            by_idempotency[event.idempotency_key] = event.source_event_id

    for source_id, target_id in edge_refs:
        if source_id not in nodes or target_id not in nodes:
            raise ValueError(
                f"Dangling projected graph edge: {source_id!r} -> {target_id!r}"
            )
    return tuple(output)
