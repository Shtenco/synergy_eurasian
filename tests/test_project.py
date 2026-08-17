from decimal import Decimal

import pytest

from sinergy_eurasian import (
    CashFlow,
    FxExposure,
    ModelInvariantError,
    MoneyAmount,
    ProductiveProjectProposal,
    totals_by_asset,
)


def _proposal() -> ProductiveProjectProposal:
    return ProductiveProjectProposal(
        project_id="kz-datacenter-01",
        jurisdiction="kz",
        sector="data-centers",
        capex=(
            MoneyAmount("KZT", "100000000"),
            MoneyAmount("CNY", "500000"),
        ),
        requested_funding=(MoneyAmount("KZT", "70000000"),),
        private_capital=(MoneyAmount("KZT", "30000000"),),
        maturity_weeks=156,
        expected_cash_flows=(
            CashFlow("2028-Q1", "KZT", "12000000"),
            CashFlow("2028-Q1", "USD", "50000"),
        ),
        evidence_status="model_estimate",
        fx_exposures=(
            FxExposure("CNY", "500000", "payable", Decimal("0.60")),
        ),
        risk_score=Decimal("0.25"),
    )


def test_money_totals_are_grouped_by_asset_only() -> None:
    totals = totals_by_asset(
        [
            MoneyAmount("KZT", "100"),
            MoneyAmount("kzt", "50"),
            MoneyAmount("USD", "2"),
        ]
    )
    assert totals == {"KZT": Decimal("150"), "USD": Decimal("2")}


def test_multicurrency_project_never_creates_nominal_cross_currency_total() -> None:
    proposal = _proposal()
    assert proposal.capex_by_asset() == {
        "CNY": Decimal("500000"),
        "KZT": Decimal("100000000"),
    }
    assert proposal.requested_funding_by_asset() == {"KZT": Decimal("70000000")}


def test_project_export_matches_federation_shape() -> None:
    payload = _proposal().to_federation_dict()
    assert payload["schema"] == "project.proposal/v1"
    assert payload["jurisdiction"] == "KZ"
    assert payload["capex"][0]["asset"] == "KZT"
    assert payload["capex"][1]["asset"] == "CNY"
    assert payload["expected_cash_flows"][1]["asset"] == "USD"
    assert payload["fx_exposures"][0]["hedged_fraction"] == 0.6
    assert payload["evidence_status"] == "MODEL_ESTIMATE"


def test_negative_money_amount_is_rejected() -> None:
    with pytest.raises(ModelInvariantError):
        MoneyAmount("KZT", "-1")


def test_cash_flow_can_be_negative_to_represent_outflow() -> None:
    flow = CashFlow("2027-Q1", "USD", "-10")
    assert flow.amount == Decimal("-10")


def test_invalid_hedge_fraction_is_rejected() -> None:
    with pytest.raises(ModelInvariantError):
        FxExposure("USD", "100", "PAYABLE", Decimal("1.01"))


def test_invalid_risk_score_is_rejected() -> None:
    proposal = _proposal()
    kwargs = proposal.__dict__.copy()
    kwargs["risk_score"] = Decimal("1.1")
    with pytest.raises(ModelInvariantError):
        ProductiveProjectProposal(**kwargs)
