import pytest

from synergy_eurasian import (
    EurasianContractError,
    ProductiveGrowthAttestation,
    ProductiveProjectProposal,
)


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


def test_productive_attestation_requires_real_physical_growth_for_value_credit():
    with pytest.raises(EurasianContractError):
        ProductiveGrowthAttestation(
            close_id="prod-close-1",
            close_sequence=1,
            project_ids=("p1",),
            goods_output_growth_units=0,
            capacity_growth_units=10,
            verified_goods_value_growth=100,
            verified_capacity_value_growth=50,
            fraud_or_quality_haircut_value=0,
            physical_consistency_gap=0,
            valuation_method_ref="valuation:v1",
            evidence_refs=("evidence:p1",),
        )


def test_productive_attestation_fails_closed_on_physical_gap():
    with pytest.raises(EurasianContractError):
        ProductiveGrowthAttestation(
            close_id="prod-close-1",
            close_sequence=1,
            project_ids=("p1",),
            goods_output_growth_units=10,
            capacity_growth_units=10,
            verified_goods_value_growth=100,
            verified_capacity_value_growth=50,
            fraud_or_quality_haircut_value=0,
            physical_consistency_gap=0.001,
            valuation_method_ref="valuation:v1",
            evidence_refs=("evidence:p1",),
        )


def test_productive_credit_nets_fraud_quality_haircut():
    attestation = ProductiveGrowthAttestation(
        close_id="prod-close-1",
        close_sequence=1,
        project_ids=("p1", "p2"),
        goods_output_growth_units=100,
        capacity_growth_units=20,
        verified_goods_value_growth=120,
        verified_capacity_value_growth=80,
        fraud_or_quality_haircut_value=30,
        physical_consistency_gap=0,
        valuation_method_ref="valuation:v1",
        evidence_refs=("inventory-proof", "commissioning-proof"),
    )
    assert attestation.gross_productive_value_growth == 200
    assert attestation.credited_productive_growth == 170
    payload = attestation.as_payload()
    assert payload["credited_productive_growth"] == 170
    assert payload["project_ids"] == ["p1", "p2"]
