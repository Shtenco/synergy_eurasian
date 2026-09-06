from __future__ import annotations

from dataclasses import asdict, dataclass


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
