from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

from .input_output import ModelInvariantError


ZERO = Decimal("0")
ONE = Decimal("1")
MAX_SAFE_JSON_INTEGER = 9_007_199_254_740_991
EVIDENCE_STATUSES = frozenset(
    {"SCENARIO", "MODEL_ESTIMATE", "OBSERVED_OPERATIONAL", "EXTERNALLY_SETTLED", "AUDITED"}
)
OBSERVED_EVIDENCE_STATUSES = frozenset(
    {"OBSERVED_OPERATIONAL", "EXTERNALLY_SETTLED", "AUDITED"}
)
FX_DIRECTIONS = frozenset({"PAYABLE", "RECEIVABLE"})


def _d(value: Decimal | int | str, field_name: str = "value") -> Decimal:
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ModelInvariantError(f"{field_name} must be a finite decimal") from exc
    if not number.is_finite():
        raise ModelInvariantError(f"{field_name} must be finite")
    return number


def _asset(value: str) -> str:
    normalized = value.upper().strip()
    if not normalized:
        raise ModelInvariantError("asset is required")
    return normalized


def _decimal_text(value: Decimal) -> str:
    """Historical v1 textual representation; preserve quantization/trailing zeros."""

    return format(value, "f")


def _canonical_decimal_text(value: Decimal | int | str, field_name: str = "value") -> str:
    number = _d(value, field_name)
    if number == ZERO:
        return "0"
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _hex64(value: str, field_name: str) -> str:
    normalized = value.lower().strip()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise ModelInvariantError(f"{field_name} must be a 64-character hex digest")
    return normalized


def _assert_canonical_json_profile(value: Any, path: str = "$") -> None:
    """Reject cross-language-ambiguous JSON primitives in federation v2 objects."""

    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_JSON_INTEGER:
            raise ModelInvariantError(f"{path} integer exceeds cross-language safe range")
        return
    if isinstance(value, float):
        raise ModelInvariantError(
            f"{path} contains float; federation v2 requires decimal strings"
        )
    if isinstance(value, Decimal):
        raise ModelInvariantError(
            f"{path} contains Decimal object; federation v2 requires decimal strings"
        )
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_canonical_json_profile(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ModelInvariantError(f"{path} contains non-string JSON object key")
            _assert_canonical_json_profile(item, f"{path}.{key}")
        return
    raise ModelInvariantError(
        f"{path} contains non-JSON value of type {type(value).__name__}"
    )


@dataclass(frozen=True)
class MoneyAmount:
    asset: str
    amount: Decimal
    source_ref: str | None = None

    def __post_init__(self) -> None:
        amount = _d(self.amount, "money amount")
        if amount < ZERO:
            raise ModelInvariantError("money amount must be non-negative")
        object.__setattr__(self, "asset", _asset(self.asset))
        object.__setattr__(self, "amount", amount)

    def to_dict(self) -> dict[str, Any]:
        """Historical v1-compatible representation."""

        return {
            "asset": self.asset,
            "amount": _decimal_text(self.amount),
            "source_ref": self.source_ref,
        }

    def to_federation_dict_v2(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "amount": _canonical_decimal_text(self.amount, "money amount"),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class CashFlow:
    period: str
    asset: str
    amount: Decimal
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.period.strip():
            raise ModelInvariantError("cash-flow period is required")
        object.__setattr__(self, "period", self.period.strip())
        object.__setattr__(self, "asset", _asset(self.asset))
        object.__setattr__(self, "amount", _d(self.amount, "cash-flow amount"))

    def to_dict(self) -> dict[str, Any]:
        """Historical v1-compatible representation."""

        return {
            "period": self.period,
            "asset": self.asset,
            "amount": _decimal_text(self.amount),
            "note": self.note,
        }

    def to_federation_dict_v2(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "asset": self.asset,
            "amount": _canonical_decimal_text(self.amount, "cash-flow amount"),
            "note": self.note,
        }


@dataclass(frozen=True)
class FxExposure:
    asset: str
    amount: Decimal
    direction: str
    hedged_fraction: Decimal = ZERO

    def __post_init__(self) -> None:
        amount = _d(self.amount, "FX exposure amount")
        direction = self.direction.upper().strip()
        hedged_fraction = _d(self.hedged_fraction, "hedged_fraction")
        if amount < ZERO:
            raise ModelInvariantError("FX exposure amount must be non-negative")
        if direction not in FX_DIRECTIONS:
            raise ModelInvariantError(f"invalid FX direction: {direction}")
        if not ZERO <= hedged_fraction <= ONE:
            raise ModelInvariantError("hedged_fraction must be between 0 and 1")
        object.__setattr__(self, "asset", _asset(self.asset))
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "hedged_fraction", hedged_fraction)

    def to_dict(self) -> dict[str, Any]:
        """Historical v1-compatible representation with numeric hedge fraction."""

        return {
            "asset": self.asset,
            "amount": _decimal_text(self.amount),
            "direction": self.direction,
            "hedged_fraction": float(self.hedged_fraction),
        }

    def to_federation_dict_v2(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "amount": _canonical_decimal_text(self.amount, "FX exposure amount"),
            "direction": self.direction,
            "hedged_fraction": _canonical_decimal_text(
                self.hedged_fraction,
                "hedged_fraction",
            ),
        }


def totals_by_asset(amounts: Iterable[MoneyAmount]) -> dict[str, Decimal]:
    """Aggregate only within the same asset; no implicit FX conversion is allowed."""

    totals: dict[str, Decimal] = {}
    for item in amounts:
        totals[item.asset] = totals.get(item.asset, ZERO) + item.amount
    return dict(sorted(totals.items()))


@dataclass(frozen=True)
class ProductiveProjectProposal:
    project_id: str
    jurisdiction: str
    sector: str
    capex: tuple[MoneyAmount, ...]
    requested_funding: tuple[MoneyAmount, ...]
    private_capital: tuple[MoneyAmount, ...]
    maturity_weeks: int
    expected_cash_flows: tuple[CashFlow, ...]
    evidence_status: str
    opex_annual: tuple[MoneyAmount, ...] = ()
    energy_requirement: str | None = None
    labor_requirement: str | None = None
    logistics_requirement: str | None = None
    fx_exposures: tuple[FxExposure, ...] = ()
    risk_score: Decimal | None = None
    first_loss_capital: tuple[MoneyAmount, ...] = ()
    dependencies: tuple[str, ...] = ()
    milestones: tuple[dict[str, Any], ...] = ()
    evidence_bundle_digest: str | None = None
    source_vintage: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.project_id.strip():
            raise ModelInvariantError("project_id is required")
        if not self.jurisdiction.strip():
            raise ModelInvariantError("jurisdiction is required")
        if not self.sector.strip():
            raise ModelInvariantError("sector is required")
        if not self.capex:
            raise ModelInvariantError("capex must not be empty")
        if not self.requested_funding:
            raise ModelInvariantError("requested_funding must not be empty")
        if (
            not isinstance(self.maturity_weeks, int)
            or isinstance(self.maturity_weeks, bool)
            or self.maturity_weeks < 1
            or self.maturity_weeks > MAX_SAFE_JSON_INTEGER
        ):
            raise ModelInvariantError(
                "maturity_weeks must be a positive cross-language safe integer"
            )

        evidence_status = self.evidence_status.upper().strip()
        if evidence_status not in EVIDENCE_STATUSES:
            raise ModelInvariantError(f"invalid evidence_status: {evidence_status}")
        evidence_digest = self.evidence_bundle_digest
        if evidence_digest is not None:
            evidence_digest = _hex64(evidence_digest, "evidence_bundle_digest")

        object.__setattr__(self, "project_id", self.project_id.strip())
        object.__setattr__(self, "jurisdiction", self.jurisdiction.upper().strip())
        object.__setattr__(self, "sector", self.sector.strip())
        object.__setattr__(self, "evidence_status", evidence_status)
        object.__setattr__(self, "evidence_bundle_digest", evidence_digest)

        if self.risk_score is not None:
            score = _d(self.risk_score, "risk_score")
            if not ZERO <= score <= ONE:
                raise ModelInvariantError("risk_score must be between 0 and 1")
            object.__setattr__(self, "risk_score", score)

    def capex_by_asset(self) -> dict[str, Decimal]:
        return totals_by_asset(self.capex)

    def requested_funding_by_asset(self) -> dict[str, Decimal]:
        return totals_by_asset(self.requested_funding)

    def private_capital_by_asset(self) -> dict[str, Decimal]:
        return totals_by_asset(self.private_capital)

    def to_federation_dict(self) -> dict[str, Any]:
        """Historical project.proposal/v1 export preserved side-by-side."""

        return {
            "schema": "project.proposal/v1",
            "project_id": self.project_id,
            "jurisdiction": self.jurisdiction,
            "sector": self.sector,
            "capex": [item.to_dict() for item in self.capex],
            "requested_funding": [item.to_dict() for item in self.requested_funding],
            "private_capital": [item.to_dict() for item in self.private_capital],
            "opex_annual": [item.to_dict() for item in self.opex_annual],
            "maturity_weeks": self.maturity_weeks,
            "expected_cash_flows": [flow.to_dict() for flow in self.expected_cash_flows],
            "energy_requirement": self.energy_requirement,
            "labor_requirement": self.labor_requirement,
            "logistics_requirement": self.logistics_requirement,
            "fx_exposures": [item.to_dict() for item in self.fx_exposures],
            "risk_score": None if self.risk_score is None else float(self.risk_score),
            "first_loss_capital": [item.to_dict() for item in self.first_loss_capital],
            "dependencies": list(self.dependencies),
            "milestones": list(self.milestones),
            "evidence_status": self.evidence_status,
            "source_vintage": self.source_vintage,
            "metadata": self.metadata,
        }

    def to_federation_dict_v2(self) -> dict[str, Any]:
        """Canonical project.proposal/v2 export with float-free economic numbers."""

        if (
            self.evidence_status in OBSERVED_EVIDENCE_STATUSES
            and self.evidence_bundle_digest is None
        ):
            raise ModelInvariantError(
                f"{self.evidence_status} v2 project claim requires evidence_bundle_digest"
            )
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ModelInvariantError("project.proposal/v2 dependencies must be unique")

        payload = {
            "schema": "project.proposal/v2",
            "project_id": self.project_id,
            "jurisdiction": self.jurisdiction,
            "sector": self.sector,
            "capex": [item.to_federation_dict_v2() for item in self.capex],
            "requested_funding": [
                item.to_federation_dict_v2() for item in self.requested_funding
            ],
            "private_capital": [
                item.to_federation_dict_v2() for item in self.private_capital
            ],
            "opex_annual": [item.to_federation_dict_v2() for item in self.opex_annual],
            "maturity_weeks": self.maturity_weeks,
            "expected_cash_flows": [
                flow.to_federation_dict_v2() for flow in self.expected_cash_flows
            ],
            "energy_requirement": self.energy_requirement,
            "labor_requirement": self.labor_requirement,
            "logistics_requirement": self.logistics_requirement,
            "fx_exposures": [
                item.to_federation_dict_v2() for item in self.fx_exposures
            ],
            "risk_score": (
                None
                if self.risk_score is None
                else _canonical_decimal_text(self.risk_score, "risk_score")
            ),
            "first_loss_capital": [
                item.to_federation_dict_v2() for item in self.first_loss_capital
            ],
            "dependencies": list(self.dependencies),
            "milestones": list(self.milestones),
            "evidence_status": self.evidence_status,
            "evidence_bundle_digest": self.evidence_bundle_digest,
            "source_vintage": self.source_vintage,
            "metadata": self.metadata,
        }
        _assert_canonical_json_profile(payload)
        return payload
