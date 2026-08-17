from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .input_output import ModelInvariantError


EVIDENCE_CLASSES = frozenset(
    {
        "MARKETPLACE_ORDER",
        "WAREHOUSE_STOCK",
        "CUSTOMS_DECLARATION",
        "INVOICE",
        "BANK_SETTLEMENT",
        "BLOCKCHAIN_FINALITY",
        "FISCAL_RECEIPT",
        "ENERGY_METER",
        "PRODUCTION_TELEMETRY",
        "AUDIT_REPORT",
        "OTHER",
    }
)
FINALITY_LEVELS = frozenset({"OBSERVED", "SETTLED", "AUDITED"})


def _hex64(value: str, field_name: str) -> str:
    normalized = value.lower().strip()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ModelInvariantError(f"{field_name} must be a 64-character hex digest")
    return normalized


def _digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProjectEvidenceItem:
    evidence_id: str
    evidence_class: str
    source_system: str
    reference: str
    observed_at: datetime
    finality_level: str
    evidence_digest: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        evidence_id = self.evidence_id.strip()
        evidence_class = self.evidence_class.upper().strip()
        source_system = self.source_system.strip()
        reference = self.reference.strip()
        finality_level = self.finality_level.upper().strip()
        if not evidence_id or not source_system or not reference:
            raise ModelInvariantError(
                "evidence_id, source_system and reference are required"
            )
        if evidence_class not in EVIDENCE_CLASSES:
            raise ModelInvariantError(f"unsupported evidence_class: {evidence_class}")
        if finality_level not in FINALITY_LEVELS:
            raise ModelInvariantError(f"unsupported finality_level: {finality_level}")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ModelInvariantError("observed_at must be timezone-aware")

        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "evidence_class", evidence_class)
        object.__setattr__(self, "source_system", source_system)
        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "finality_level", finality_level)
        object.__setattr__(
            self,
            "evidence_digest",
            _hex64(self.evidence_digest, "evidence_digest"),
        )

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_class": self.evidence_class,
            "source_system": self.source_system,
            "reference": self.reference,
            "observed_at": self.observed_at.isoformat(),
            "finality_level": self.finality_level,
            "evidence_digest": self.evidence_digest,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ProjectEvidenceBundle:
    project_id: str
    as_of: datetime
    items: tuple[ProjectEvidenceItem, ...]

    def __post_init__(self) -> None:
        project_id = self.project_id.strip()
        if not project_id:
            raise ModelInvariantError("project_id is required")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ModelInvariantError("bundle as_of must be timezone-aware")
        ids = [item.evidence_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ModelInvariantError("evidence_id values must be unique within a bundle")
        if any(item.observed_at > self.as_of for item in self.items):
            raise ModelInvariantError("evidence item cannot be observed after bundle as_of")
        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "items", tuple(sorted(self.items, key=lambda item: item.evidence_id)))

    def has_class(self, evidence_class: str) -> bool:
        target = evidence_class.upper().strip()
        return any(item.evidence_class == target for item in self.items)

    def minimum_finality_count(self, finality_level: str) -> int:
        target = finality_level.upper().strip()
        if target not in FINALITY_LEVELS:
            raise ModelInvariantError(f"unsupported finality_level: {target}")
        rank = {"OBSERVED": 1, "SETTLED": 2, "AUDITED": 3}
        threshold = rank[target]
        return sum(rank[item.finality_level] >= threshold for item in self.items)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "schema": "project.evidence/v1",
            "project_id": self.project_id,
            "as_of": self.as_of.isoformat(),
            "items": [item.canonical_dict() for item in self.items],
        }

    @property
    def digest(self) -> str:
        return _digest(self.canonical_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self.canonical_dict()
        payload["digest"] = self.digest
        return payload
