"""Typed physical-flow aggregation with strict resource/unit/period separation."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .contracts import Quantity


class FlowBoundary(str, Enum):
    INTERNAL = "INTERNAL"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    FINAL_USE = "FINAL_USE"


class FlowEvidenceStatus(str, Enum):
    PLANNED = "PLANNED"
    COMMITTED = "COMMITTED"
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    SCENARIO = "SCENARIO"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class PhysicalFlow:
    flow_id: str
    source_id: str
    target_id: str
    resource_id: str
    quantity: Quantity
    period_id: str
    boundary: FlowBoundary = FlowBoundary.INTERNAL
    evidence_id: str = ""
    evidence_status: FlowEvidenceStatus = FlowEvidenceStatus.PLANNED

    def __post_init__(self) -> None:
        if not all((self.flow_id, self.source_id, self.target_id, self.resource_id, self.period_id)):
            raise ValueError("Physical flow identity, endpoints, resource and period are required")
        if not isinstance(self.boundary, FlowBoundary):
            object.__setattr__(self, "boundary", FlowBoundary(self.boundary))
        if not isinstance(self.evidence_status, FlowEvidenceStatus):
            object.__setattr__(self, "evidence_status", FlowEvidenceStatus(self.evidence_status))
        if self.evidence_status in {
            FlowEvidenceStatus.COMMITTED, FlowEvidenceStatus.OBSERVED, FlowEvidenceStatus.VERIFIED,
        } and not self.evidence_id:
            raise ValueError("Committed, observed and verified physical flows require evidence_id")
        if self.quantity.amount < 0:
            raise ValueError("Physical flow quantity must be non-negative")


def summarize_physical_flows(flows: Iterable[PhysicalFlow]) -> dict:
    """Summarize flows without adding unlike units, resources or periods."""
    rows = list(flows)
    ids = [row.flow_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate physical flow_id")

    totals: dict[tuple[str, str, str, str, str], Decimal] = {}
    counts: dict[tuple[str, str, str, str, str], int] = {}
    for row in rows:
        key = (row.resource_id, row.quantity.unit, row.period_id, row.boundary.value, row.evidence_status.value)
        totals[key] = totals.get(key, Decimal("0")) + row.quantity.amount
        counts[key] = counts.get(key, 0) + 1

    records = [
        {
            "resource_id": key[0],
            "unit": key[1],
            "period_id": key[2],
            "boundary": key[3],
            "evidence_status": key[4],
            "quantity": str(value),
            "flow_count": counts[key],
        }
        for key, value in sorted(totals.items())
    ]
    return {
        "flows": records,
        "internal_transfers_are_not_new_output": True,
        "aggregation_dimensions": ["resource_id", "unit", "period_id", "boundary", "evidence_status"],
        "scenario_and_unverified_flows_are_separated": True,
    }
