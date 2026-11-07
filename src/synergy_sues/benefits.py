"""Cross-project benefit attribution registry to prevent duplicate economic claims."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .contracts import EvidenceStatus, Money, _decimal


@dataclass(frozen=True)
class BenefitEvent:
    benefit_event_id: str
    measurement_id: str
    enterprise_id: str
    period_id: str
    metric_code: str
    amount: Money
    counterfactual_id: str
    evidence_ids: tuple[str, ...]
    evidence_status: EvidenceStatus
    measurement_scope_id: str = ""

    def __post_init__(self) -> None:
        if not all((self.benefit_event_id, self.measurement_id, self.enterprise_id,
                    self.period_id, self.metric_code, self.counterfactual_id)):
            raise ValueError("Benefit event identity, measurement and counterfactual are required")
        if not isinstance(self.evidence_status, EvidenceStatus):
            object.__setattr__(self, "evidence_status", EvidenceStatus(self.evidence_status))
        if isinstance(self.evidence_ids, (str, bytes)) or not isinstance(self.evidence_ids, (tuple, list)):
            raise ValueError("Benefit evidence_ids must be a tuple or list of strings")
        if not isinstance(self.evidence_ids, tuple):
            object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        if not isinstance(self.measurement_scope_id, str):
            raise ValueError("measurement_scope_id must be a string")
        if self.measurement_scope_id and not self.measurement_scope_id.strip():
            raise ValueError("measurement_scope_id cannot be whitespace")
        if not self.evidence_ids:
            raise ValueError("Benefit event requires at least one evidence ID")
        if any(not isinstance(item, str) or not item for item in self.evidence_ids):
            raise ValueError("Benefit evidence IDs must be non-empty strings")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Benefit evidence IDs must be unique")
        if self.amount.amount < 0:
            raise ValueError("Benefit amount must be non-negative")


@dataclass(frozen=True)
class BenefitAttribution:
    claim_id: str
    benefit_event_id: str
    project_id: str
    attribution_weight: Decimal

    def __post_init__(self) -> None:
        if not all((self.claim_id, self.benefit_event_id, self.project_id)):
            raise ValueError("Benefit attribution identity is required")
        weight = _decimal(self.attribution_weight, "attribution_weight")
        if not Decimal("0") < weight <= Decimal("1"):
            raise ValueError("attribution_weight must be in (0, 1]")
        object.__setattr__(self, "attribution_weight", weight)


class BenefitAttributionRegistry:
    """One measured benefit event may be shared, but total attribution cannot exceed 100%."""

    def __init__(self) -> None:
        self._events: dict[str, BenefitEvent] = {}
        self._measurement_ids: set[str] = set()
        self._measurement_keys: set[tuple[str, str, str, str, str]] = set()
        self._claims: dict[str, BenefitAttribution] = {}

    def add_event(self, event: BenefitEvent) -> None:
        if event.benefit_event_id in self._events:
            raise ValueError(f"Duplicate benefit_event_id: {event.benefit_event_id}")
        if event.measurement_id in self._measurement_ids:
            raise ValueError(f"Measurement already registered: {event.measurement_id}")
        measurement_key = (
            event.enterprise_id, event.period_id, event.metric_code,
            event.counterfactual_id, event.measurement_scope_id,
        )
        if measurement_key in self._measurement_keys:
            raise ValueError(
                "Enterprise/period/metric/counterfactual measurement scope already registered"
            )
        self._events[event.benefit_event_id] = event
        self._measurement_ids.add(event.measurement_id)
        self._measurement_keys.add(measurement_key)

    def add_claim(self, claim: BenefitAttribution) -> None:
        if claim.claim_id in self._claims:
            raise ValueError(f"Duplicate benefit claim: {claim.claim_id}")
        if claim.benefit_event_id not in self._events:
            raise ValueError(f"Unknown benefit event: {claim.benefit_event_id}")
        used = sum(
            (row.attribution_weight for row in self._claims.values()
             if row.benefit_event_id == claim.benefit_event_id),
            Decimal("0"),
        )
        if used + claim.attribution_weight > Decimal("1"):
            raise ValueError("Total benefit attribution would exceed 1.0")
        self._claims[claim.claim_id] = claim

    def summary(self) -> dict:
        by_project: dict[tuple[str, str], Decimal] = {}
        by_status: dict[str, dict[str, Decimal]] = {}
        event_rows = []
        for event_id, event in self._events.items():
            claims = [x for x in self._claims.values() if x.benefit_event_id == event_id]
            allocated = sum((x.attribution_weight for x in claims), Decimal("0"))
            status = event.evidence_status.value
            status_bucket = by_status.setdefault(status, {})
            status_bucket[event.amount.currency] = status_bucket.get(event.amount.currency, Decimal("0")) + event.amount.amount
            for claim in claims:
                key = (claim.project_id, event.amount.currency)
                by_project[key] = by_project.get(key, Decimal("0")) + event.amount.amount * claim.attribution_weight
            event_rows.append({
                "benefit_event_id": event_id,
                "measurement_id": event.measurement_id,
                "gross_amount": str(event.amount.amount),
                "currency": event.amount.currency,
                "attributed_weight": str(allocated),
                "unallocated_weight": str(Decimal("1") - allocated),
                "evidence_status": status,
                "scenario_is_not_observed_cash": event.evidence_status == EvidenceStatus.SCENARIO,
            })
        return {
            "events": event_rows,
            "attributed_amount_by_project_currency": [
                {"project_id": project, "currency": currency, "amount": str(amount)}
                for (project, currency), amount in sorted(by_project.items())
            ],
            "gross_amount_by_evidence_status_currency": {
                status: {currency: str(amount) for currency, amount in values.items()}
                for status, values in by_status.items()
            },
            "total_attribution_capped_at_one_per_measurement": True,
        }
