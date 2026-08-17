import json
from decimal import Decimal
from pathlib import Path

from sinergy_eurasian.project import (
    CashFlow,
    FxExposure,
    MoneyAmount,
    ProductiveProjectProposal,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/conformance/project_proposal_v2_kz_energy_pilot.json"


def _project() -> ProductiveProjectProposal:
    return ProductiveProjectProposal(
        project_id="kz-energy-pilot-001",
        jurisdiction="KZ",
        sector="Энергетика",
        capex=(MoneyAmount("KZT", "100000000", "capex-plan-1"),),
        requested_funding=(
            MoneyAmount("KZT", "70000000", "funding-request-1"),
        ),
        private_capital=(
            MoneyAmount("KZT", "30000000", "sponsor-capital-1"),
        ),
        opex_annual=(),
        maturity_weeks=156,
        expected_cash_flows=(
            CashFlow(
                "2027",
                "KZT",
                "25000000",
                "base-case operating cash flow",
            ),
        ),
        energy_requirement="10 MW",
        labor_requirement="120 FTE",
        logistics_requirement="rail + road",
        fx_exposures=(
            FxExposure("USD", "10000000", "PAYABLE", "0.7500"),
        ),
        risk_score=Decimal("0.2500"),
        first_loss_capital=(MoneyAmount("KZT", "7000000", "first-loss-1"),),
        dependencies=("grid-connection", "equipment-delivery"),
        milestones=({"id": "m1", "status": "PLANNED", "completion": "0"},),
        evidence_status="MODEL_ESTIMATE",
        evidence_bundle_digest=None,
        source_vintage="2026-08-17",
        metadata={"revision": 2, "title": "Пилот энергетического проекта"},
    )


def test_eurasian_v2_producer_matches_shared_fixture_exactly() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = _project().to_federation_dict_v2()
    assert actual == expected


def test_fixture_is_float_free_recursively() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            assert not isinstance(value, float)

    walk(payload)


def test_fixture_preserves_unique_decimal_spellings() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["risk_score"] == "0.25"
    assert payload["fx_exposures"][0]["hedged_fraction"] == "0.75"
    assert payload["capex"][0]["amount"] == "100000000"
