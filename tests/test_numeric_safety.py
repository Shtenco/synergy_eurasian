from decimal import Decimal

import pytest

from sinergy_eurasian import (
    CashFlow,
    FxExposure,
    ModelInvariantError,
    MoneyAmount,
    ProductiveProjectProposal,
)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", Decimal("NaN")])
def test_money_amount_rejects_non_finite_values(bad) -> None:
    with pytest.raises(ModelInvariantError):
        MoneyAmount("KZT", bad)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_cash_flow_rejects_non_finite_values(bad: str) -> None:
    with pytest.raises(ModelInvariantError):
        CashFlow("2027-Q1", "USD", bad)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_fx_exposure_rejects_non_finite_amount_and_hedge(bad: str) -> None:
    with pytest.raises(ModelInvariantError):
        FxExposure("USD", bad, "PAYABLE", "0.5")
    with pytest.raises(ModelInvariantError):
        FxExposure("USD", "100", "PAYABLE", bad)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_project_risk_score_rejects_non_finite_values(bad: str) -> None:
    with pytest.raises(ModelInvariantError):
        ProductiveProjectProposal(
            project_id="project-1",
            jurisdiction="KZ",
            sector="energy",
            capex=(MoneyAmount("KZT", "100"),),
            requested_funding=(MoneyAmount("KZT", "70"),),
            private_capital=(MoneyAmount("KZT", "30"),),
            maturity_weeks=52,
            expected_cash_flows=(),
            evidence_status="MODEL_ESTIMATE",
            risk_score=bad,
        )
