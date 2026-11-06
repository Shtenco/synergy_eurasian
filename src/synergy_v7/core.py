"""Event-sourced economic graph primitives for SYNERGY V7 (stdlib only)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from hashlib import sha256
import json, math
from typing import Any, Iterable


def _timestamp(value: str) -> datetime:
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (TypeError,ValueError) as exc:
        raise ValueError(f"Invalid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise ValueError("Timestamps must include a timezone offset")
    return dt


def _canonical(value: Any) -> str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    sequence: int
    event_type: str
    effective_at: str
    recorded_at: str
    payload: dict[str,Any]
    source_ref: str
    evidence_ids: tuple[str,...]=()
    idempotency_key: str=""
    previous_hash: str=""
    event_hash: str=""
    def unsigned(self):
        d=asdict(self); d.pop("event_hash"); return d


class EventStore:
    """Append-only in-memory event log with per-aggregate sequence and SHA-256 chain."""
    def __init__(self):
        self._events=[]; self._ids=set(); self._idempotency=set()
        self._sequences={}; self._aggregate_hash={}
    @property
    def events(self): return tuple(self._events)
    def append(self,event: DomainEvent) -> DomainEvent:
        if not all((event.event_id,event.aggregate_type,event.aggregate_id,event.event_type,event.source_ref)):
            raise ValueError("Event identity, type and source_ref are required")
        if event.event_id in self._ids: raise ValueError(f"Duplicate event_id: {event.event_id}")
        if event.idempotency_key and event.idempotency_key in self._idempotency:
            raise ValueError(f"Duplicate idempotency_key: {event.idempotency_key}")
        if event.sequence<1: raise ValueError("sequence must be >= 1")
        _timestamp(event.effective_at); _timestamp(event.recorded_at); _canonical(event.payload)
        key=(event.aggregate_type,event.aggregate_id)
        expected=self._sequences.get(key,0)+1
        if event.sequence!=expected: raise ValueError(f"Expected aggregate sequence {expected}, got {event.sequence}")
        previous=self._aggregate_hash.get(key,"")
        if event.previous_hash and event.previous_hash!=previous: raise ValueError("previous_hash does not match aggregate head")
        unsigned=event.unsigned(); unsigned["previous_hash"]=previous
        digest=sha256(_canonical(unsigned).encode()).hexdigest()
        sealed=DomainEvent(**{**asdict(event),"previous_hash":previous,"event_hash":digest})
        self._events.append(sealed); self._ids.add(event.event_id)
        if event.idempotency_key: self._idempotency.add(event.idempotency_key)
        self._sequences[key]=event.sequence; self._aggregate_hash[key]=digest
        return sealed
    def verify(self) -> bool:
        heads={}
        for e in self._events:
            key=(e.aggregate_type,e.aggregate_id); seq,prev=heads.get(key,(0,""))
            if e.sequence!=seq+1 or e.previous_hash!=prev: return False
            if sha256(_canonical(e.unsigned()).encode()).hexdigest()!=e.event_hash: return False
            heads[key]=(e.sequence,e.event_hash)
        return True


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    attributes: dict[str,Any]=field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    attributes: dict[str,Any]=field(default_factory=dict)


class EconomicGraph:
    """Typed graph with referential integrity and acyclic DEPENDS_ON edges."""
    def __init__(self,nodes: Iterable[GraphNode],edges: Iterable[GraphEdge]):
        ns,es=list(nodes),list(edges)
        if len({n.node_id for n in ns})!=len(ns): raise ValueError("Duplicate graph node_id")
        if len({e.edge_id for e in es})!=len(es): raise ValueError("Duplicate graph edge_id")
        self.nodes={n.node_id:n for n in ns}; self.edges=tuple(es); self.validate()
    @classmethod
    def build(cls,nodes,edges): return cls(nodes,edges)
    def validate(self):
        adj={}
        for e in self.edges:
            if e.source_id not in self.nodes or e.target_id not in self.nodes: raise ValueError(f"Dangling edge: {e.edge_id}")
            if e.relation=="DEPENDS_ON": adj.setdefault(e.source_id,[]).append(e.target_id)
        visiting=set(); visited=set()
        def visit(n):
            if n in visiting: raise ValueError("Project dependency graph contains a cycle")
            if n in visited: return
            visiting.add(n)
            for nxt in adj.get(n,[]): visit(nxt)
            visiting.remove(n); visited.add(n)
        for n in adj: visit(n)


@dataclass(frozen=True)
class PhysicalFlow:
    flow_id: str
    source_node: str
    target_node: str
    resource_id: str
    quantity: float
    unit: str
    period: str
    boundary: str="INTERNAL"
    def __post_init__(self):
        if not all((self.flow_id,self.resource_id,self.unit,self.period)): raise ValueError("Physical flow identifiers, unit and period are required")
        if not math.isfinite(self.quantity) or self.quantity<0: raise ValueError("Physical flow quantity must be finite and non-negative")
        if self.boundary not in {"INTERNAL","IMPORT","EXPORT","FINAL_USE"}: raise ValueError("Unsupported physical-flow boundary")


def physical_flow_summary(flows: Iterable[PhysicalFlow]) -> dict[str,Any]:
    rows=list(flows); ids=[f.flow_id for f in rows]
    if len(ids)!=len(set(ids)): raise ValueError("Duplicate physical flow_id")
    exports={}; imports={}; final={}; internal=0.0
    for f in rows:
        k=(f.resource_id,f.unit)
        if f.boundary=="EXPORT": exports[k]=exports.get(k,0.0)+f.quantity
        elif f.boundary=="IMPORT": imports[k]=imports.get(k,0.0)+f.quantity
        elif f.boundary=="FINAL_USE": final[k]=final.get(k,0.0)+f.quantity
        else: internal+=f.quantity
    fmt=lambda d:{f"{k[0]}::{k[1]}":v for k,v in sorted(d.items())}
    return {"external_exports":fmt(exports),"imports":fmt(imports),"final_use":fmt(final),
            "internal_transfer_volume":internal,"internal_transfer_is_new_output":False}


@dataclass(frozen=True)
class ResourceCapacity:
    resource_id: str
    period: str
    available_quantity: float
    unit: str
    status: str
    evidence_id: str
    def __post_init__(self):
        if not all((self.resource_id,self.period,self.unit,self.evidence_id)): raise ValueError("Resource capacity identity and evidence are required")
        if not math.isfinite(self.available_quantity) or self.available_quantity<0: raise ValueError("available_quantity must be finite and non-negative")
        if self.status not in {"OBSERVED","COMMITTED","UNDER_CONSTRUCTION","PLANNED","ANNOUNCED","SCENARIO"}: raise ValueError("Invalid resource status")


@dataclass(frozen=True)
class ResourceCommitment:
    commitment_id: str
    resource_id: str
    project_id: str
    period: str
    quantity: float
    unit: str
    status: str="COMMITTED"
    def __post_init__(self):
        if not all((self.commitment_id,self.resource_id,self.project_id,self.period,self.unit)): raise ValueError("Resource commitment identity is required")
        if not math.isfinite(self.quantity) or self.quantity<0: raise ValueError("Commitment quantity must be finite and non-negative")
        if self.status not in {"COMMITTED","PROPOSED"}: raise ValueError("Invalid commitment status")


def validate_resource_capacity(capacities: Iterable[ResourceCapacity],commitments: Iterable[ResourceCommitment],include_proposed: bool=False):
    """Only OBSERVED/COMMITTED capacity is firm; proposed reservations are opt-in."""
    caps=list(capacities); rows=list(commitments); keys=[(c.resource_id,c.period) for c in caps]
    if len(keys)!=len(set(keys)): raise ValueError("Duplicate resource capacity state for resource-period")
    cmap={(c.resource_id,c.period):c for c in caps}; used={}
    for item in rows:
        if item.status=="PROPOSED" and not include_proposed: continue
        key=(item.resource_id,item.period)
        if key not in cmap: raise ValueError(f"Missing capacity state for {key}")
        cap=cmap[key]
        if item.unit!=cap.unit: raise ValueError(f"Unit mismatch for {key}: {item.unit} != {cap.unit}")
        if cap.status not in {"OBSERVED","COMMITTED"}: raise ValueError(f"Capacity is not firm for {key}: {cap.status}")
        used[key]=used.get(key,0.0)+item.quantity
    violations=[]
    for key,q in used.items():
        cap=cmap[key]
        if q>cap.available_quantity+1e-9:
            violations.append({"resource_id":key[0],"period":key[1],"committed":q,"available":cap.available_quantity,"unit":cap.unit,"excess":q-cap.available_quantity})
    return {"feasible":not violations,"violations":violations,"firm_capacity_only":True,"proposed_commitments_included":include_proposed}


def graph_from_events(events: Iterable[DomainEvent]) -> EconomicGraph:
    """Deterministically rebuild graph projections from NODE_REGISTERED/EDGE_REGISTERED events."""
    nodes={}; edges={}
    for e in events:
        p=e.payload
        if e.event_type=="NODE_REGISTERED":
            n=GraphNode(str(p["node_id"]),str(p["node_type"]),dict(p.get("attributes",{})))
            if n.node_id in nodes: raise ValueError(f"Node already registered: {n.node_id}")
            nodes[n.node_id]=n
        elif e.event_type=="EDGE_REGISTERED":
            edge=GraphEdge(str(p["edge_id"]),str(p["source_id"]),str(p["target_id"]),str(p["relation"]),dict(p.get("attributes",{})))
            if edge.edge_id in edges: raise ValueError(f"Edge already registered: {edge.edge_id}")
            edges[edge.edge_id]=edge
    return EconomicGraph.build(nodes.values(),edges.values())
