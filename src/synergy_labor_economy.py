"""Evidence-qualified, non-monetary labor contribution scoring for SYNERGY.

This module deliberately has no wallet, mint, payment, accounting, network, or
persistence side effects. Financial authorization belongs to Financial OS.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


POLICY_VERSION = "SLE-SCORE-1.0"
MIN_COMPLEXITY = Decimal("0.5")
MAX_COMPLEXITY = Decimal("2.0")
MIN_OUTCOME = Decimal("0.5")
MAX_OUTCOME = Decimal("2.0")
ZERO = Decimal("0")
ONE = Decimal("1")


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite decimal number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a finite decimal number") from None
    if not number.is_finite():
        raise ValueError(f"{field} must be finite")
    return number


def _format_decimal(value: Decimal) -> str:
    """Serialize Decimal without input-dependent trailing zero noise."""
    if value == ZERO:
        return "0"
    return format(value.normalize(), "f")


def _required_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("each contribution must be an object")

    contribution_id = _required_text(record, "contribution_id")
    contributor_id = _required_text(record, "contributor_id")
    _required_text(record, "project_id")
    _required_text(record, "effort_unit")
    benefit_stream_id = _required_text(record, "benefit_stream_id")

    if record.get("status") != "ACCEPTED":
        raise ValueError(f"{contribution_id}: only ACCEPTED contributions can be scored")
    if record.get("contributor_kind") not in {"HUMAN", "AI_AGENT", "JOINT"}:
        raise ValueError(f"{contribution_id}: unsupported contributor_kind")
    if record.get("category") not in {
        "PRODUCTION", "INTELLECTUAL", "TECHNICAL", "ENTREPRENEURIAL",
        "COORDINATION", "CARE_SOCIAL", "INFRASTRUCTURE", "EDUCATION",
        "MAINTENANCE", "AI_AGENT", "HUMAN_AI_JOINT",
    }:
        raise ValueError(f"{contribution_id}: unsupported contribution category")

    effort = _decimal(record.get("effort_units"), "effort_units")
    if record.get("hours_observed") is not None:
        observed_hours = _decimal(record.get("hours_observed"), "hours_observed")
        if observed_hours < ZERO:
            raise ValueError(f"{contribution_id}: hours_observed cannot be negative")
    complexity = _decimal(record.get("complexity_factor"), "complexity_factor")
    quality = _decimal(record.get("quality_factor"), "quality_factor")
    outcome = _decimal(record.get("outcome_factor"), "outcome_factor")
    reliability = _decimal(record.get("reliability_factor"), "reliability_factor")
    attribution = _decimal(record.get("attribution_share"), "attribution_share")

    if effort <= ZERO:
        raise ValueError(f"{contribution_id}: effort_units must be positive")
    if not MIN_COMPLEXITY <= complexity <= MAX_COMPLEXITY:
        raise ValueError(f"{contribution_id}: complexity_factor outside V1 policy bounds")
    if not ZERO <= quality <= ONE:
        raise ValueError(f"{contribution_id}: quality_factor must be in [0, 1]")
    if not MIN_OUTCOME <= outcome <= MAX_OUTCOME:
        raise ValueError(f"{contribution_id}: outcome_factor outside V1 policy bounds")
    if not ZERO <= reliability <= ONE:
        raise ValueError(f"{contribution_id}: reliability_factor must be in [0, 1]")
    if not ZERO <= attribution <= ONE:
        raise ValueError(f"{contribution_id}: attribution_share must be in [0, 1]")

    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{contribution_id}: at least one evidence item is required")
    independent_evidence = False
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError(f"{contribution_id}: evidence items must be objects")
        _required_text(item, "evidence_id")
        _required_text(item, "source")
        digest = _required_text(item, "sha256")
        if len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
            raise ValueError(f"{contribution_id}: evidence sha256 must be 64 hex characters")
        independent_evidence = independent_evidence or item.get("independent") is True
    if not independent_evidence:
        raise ValueError(f"{contribution_id}: independent evidence is required")

    verification = record.get("verification")
    if not isinstance(verification, dict):
        raise ValueError(f"{contribution_id}: verification object is required")
    _required_text(verification, "verifier_id")
    _required_text(verification, "signature_reference")
    if verification.get("independent_from_contributor") is not True:
        raise ValueError(f"{contribution_id}: verifier must be independent")
    if verification.get("conflict_disclosed") is not True:
        raise ValueError(f"{contribution_id}: verifier conflict disclosure is required")

    return {
        "contribution_id": contribution_id,
        "contributor_id": contributor_id,
        "benefit_stream_id": benefit_stream_id,
        "effort_units": effort,
        "complexity_factor": complexity,
        "quality_factor": quality,
        "outcome_factor": outcome,
        "reliability_factor": reliability,
        "attribution_share": attribution,
    }


def score_contributions(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Validate a complete batch and return deterministic non-monetary scores.

    Attribution is conserved per benefit_stream_id. The function rejects the
    entire batch if a benefit is credited more than once in aggregate.
    """
    validated = [_validate_record(record) for record in records]
    if not validated:
        raise ValueError("at least one contribution is required")

    ids = [item["contribution_id"] for item in validated]
    if len(ids) != len(set(ids)):
        raise ValueError("contribution_id values must be unique within a batch")

    attribution_by_benefit: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for item in validated:
        attribution_by_benefit[item["benefit_stream_id"]] += item["attribution_share"]

    overallocated = {
        benefit_id: str(total)
        for benefit_id, total in attribution_by_benefit.items()
        if total > ONE
    }
    if overallocated:
        raise ValueError(f"benefit stream attribution exceeds 1.0: {overallocated}")

    scored = []
    total_score = ZERO
    for item in sorted(validated, key=lambda row: row["contribution_id"]):
        score = (
            item["effort_units"]
            * item["complexity_factor"]
            * item["quality_factor"]
            * item["outcome_factor"]
            * item["reliability_factor"]
            * item["attribution_share"]
        )
        total_score += score
        scored.append({
            "contribution_id": item["contribution_id"],
            "contributor_id": item["contributor_id"],
            "benefit_stream_id": item["benefit_stream_id"],
            "labor_score": _format_decimal(score),
        })

    return {
        "policy_version": POLICY_VERSION,
        "status": "NON_MONETARY_SCORE_ONLY",
        "total_labor_score": _format_decimal(total_score),
        "contributions": scored,
        "attribution_totals": {
            key: _format_decimal(value) for key, value in sorted(attribution_by_benefit.items())
        },
        "financial_authorization_required": True,
        "money_issued": False,
    }
