import pytest

from synergy_eurasian import EurasianContractError, ProductiveProjectProposal


def test_project_requires_explicit_stress_case():
    with pytest.raises(EurasianContractError):
        ProductiveProjectProposal(
            project_id="p1",
            candidate_id="c1",
            region="r1",
            industry="manufacturing",
            capex=100,
            opex_annual=20,
            expected_external_revenue=40,
            jobs=5,
            funding_requested=80,
            stress_case={},
        )


def test_project_projection_is_not_realized_profit():
    p = ProductiveProjectProposal(
        project_id="p1",
        candidate_id="c1",
        region="r1",
        industry="manufacturing",
        capex=100,
        opex_annual=20,
        expected_external_revenue=40,
        jobs=5,
        funding_requested=80,
        stress_case={"revenue_haircut": 0.3},
    )
    assert p.projected_operating_margin == 20
    assert "expected_external_revenue" in p.as_payload()
