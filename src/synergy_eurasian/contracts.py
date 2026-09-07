from __future__ import annotations

from dataclasses import asdict, dataclass, field


class EurasianContractError(ValueError):
    pass


@dataclass(frozen=True)
class ProductiveProjectProposal:
    project_id: str
    candidate_id: str
    region: str
    industry: str
    capex: float
    opex_annual: float
    expected_external_revenue: float
    jobs: int
    funding_requested: float
    stress_case: dict

    def __post_init__(self) -> None:
        for name, value in (
            ("capex", self.capex),
            ("opex_annual", self.opex_annual),
            ("expected_external_revenue", self.expected_external_revenue),
            ("funding_requested", self.funding_requested),
        ):
            if value < 0:
                raise EurasianContractError(f"{name} must be non-negative")
        if self.jobs < 0:
            raise EurasianContractError("jobs must be non-negative")
        if not self.region or not self.industry:
            raise EurasianContractError("region and industry are required")
        if not isinstance(self.stress_case, dict) or not self.stress_case:
            raise EurasianContractError("stress_case must be an explicit non-empty scenario")

    @property
    def projected_operating_margin(self) -> float:
        return self.expected_external_revenue - self.opex_annual

    def as_payload(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ProductiveGrowthAttestation:
    """Canonical Synergy Eurasian proof for the productive side of AICB V5.

    This contract reports *realized* productive growth, never a project plan.
    Physical observations and monetary valuation remain explicit and auditable.
    The value credit may be consumed by the emission escrow only together with
    an independent Financial OS growth credit.
    """

    close_id: str
    close_sequence: int
    project_ids: tuple[str, ...]
    goods_output_growth_units: float
    capacity_growth_units: float
    verified_goods_value_growth: float
    verified_capacity_value_growth: float
    fraud_or_quality_haircut_value: float
    physical_consistency_gap: float
    valuation_method_ref: str
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.close_id:
            raise EurasianContractError("close_id is required")
        if self.close_sequence <= 0:
            raise EurasianContractError("close_sequence must be positive")
        if not self.project_ids:
            raise EurasianContractError("at least one completed project is required")
        if len(set(self.project_ids)) != len(self.project_ids):
            raise EurasianContractError("project_ids must be unique")
        for name, value in (
            ("goods_output_growth_units", self.goods_output_growth_units),
            ("capacity_growth_units", self.capacity_growth_units),
            ("verified_goods_value_growth", self.verified_goods_value_growth),
            ("verified_capacity_value_growth", self.verified_capacity_value_growth),
            ("fraud_or_quality_haircut_value", self.fraud_or_quality_haircut_value),
            ("physical_consistency_gap", self.physical_consistency_gap),
        ):
            if value < 0:
                raise EurasianContractError(f"{name} must be non-negative")
        if not self.valuation_method_ref:
            raise EurasianContractError("valuation_method_ref is required")
        if not self.evidence_refs or any(not ref for ref in self.evidence_refs):
            raise EurasianContractError("non-empty evidence_refs are required")
        if self.physical_consistency_gap > 1e-12:
            raise EurasianContractError(
                "productive growth cannot be attested while physical consistency gap is non-zero"
            )
        if self.verified_goods_value_growth > 0 and self.goods_output_growth_units <= 0:
            raise EurasianContractError(
                "goods value growth requires positive observed goods growth"
            )
        if self.verified_capacity_value_growth > 0 and self.capacity_growth_units <= 0:
            raise EurasianContractError(
                "capacity value growth requires positive observed capacity growth"
            )

    @property
    def gross_productive_value_growth(self) -> float:
        return self.verified_goods_value_growth + self.verified_capacity_value_growth

    @property
    def credited_productive_growth(self) -> float:
        return max(
            self.gross_productive_value_growth - self.fraud_or_quality_haircut_value,
            0.0,
        )

    def as_payload(self) -> dict:
        payload = asdict(self)
        payload["project_ids"] = list(self.project_ids)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["gross_productive_value_growth"] = self.gross_productive_value_growth
        payload["credited_productive_growth"] = self.credited_productive_growth
        return payload
