from decimal import Decimal

import pytest

from sinergy_eurasian import (
    FxExposure,
    ModelInvariantError,
    MoneyAmount,
    ProductiveProjectProposal,
)


def _project(**changes) -> ProductiveProjectProposal:
    kwargs = {
        "project_id": "project-v2",
        "jurisdiction": "KZ",
        "sector": "energy",
        "capex": (MoneyAmount("KZT", "100"),),
        "requested_funding": (MoneyAmount("KZT", "70"),),
        "private_capital": (MoneyAmount("KZT", "30"),),
        "maturity_weeks": 52,
        "expected_cash_flows": (),
        "evidence_status": "MODEL_ESTIMATE",
        "fx_exposures": (FxExposure("USD", "10", "PAYABLE", "0.75"),),
        "risk_score": Decimal("0.25"),
        "metadata": {"scenario": "base", "revision": 2},
    }
    kwargs.update(changes)
    return ProductiveProjectProposal(**kwargs)


def test_v1_export_is_preserved_for_provenance() -> None:
    project = _project()
    payload = project.to_federation_dict()
    assert payload["schema"] == "project.proposal/v1"
    assert payload["risk_score"] == 0.25
    assert payload["fx_exposures"][0]["hedged_fraction"] == 0.75
    assert "evidence_bundle_digest" not in payload


def test_v2_export_uses_decimal_strings_for_fractional_economics() -> None:
    project = _project()
    payload = project.to_federation_dict_v2()
    assert payload["schema"] == "project.proposal/v2"
    assert payload["risk_score"] == "0.25"
    assert payload["fx_exposures"][0]["hedged_fraction"] == "0.75"
    assert payload["requested_funding"][0]["amount"] == "70"
    assert payload["maturity_weeks"] == 52


def test_v2_normalizes_equivalent_decimal_representations_uniquely() -> None:
    project = _project(
        capex=(MoneyAmount("KZT", "100.000"),),
        requested_funding=(MoneyAmount("KZT", "70.00"),),
        private_capital=(MoneyAmount("KZT", "30.0"),),
        fx_exposures=(FxExposure("USD", "10.000", "PAYABLE", "0.7500"),),
        risk_score=Decimal("0.2500"),
    )
    payload = project.to_federation_dict_v2()
    assert payload["capex"][0]["amount"] == "100"
    assert payload["requested_funding"][0]["amount"] == "70"
    assert payload["private_capital"][0]["amount"] == "30"
    assert payload["fx_exposures"][0]["amount"] == "10"
    assert payload["fx_exposures"][0]["hedged_fraction"] == "0.75"
    assert payload["risk_score"] == "0.25"


def test_v2_normalizes_signed_or_quantized_zero_to_zero() -> None:
    project = _project(
        risk_score=Decimal("-0.000"),
        fx_exposures=(FxExposure("USD", "0.00", "PAYABLE", "0.000"),),
    )
    payload = project.to_federation_dict_v2()
    assert payload["risk_score"] == "0"
    assert payload["fx_exposures"][0]["amount"] == "0"
    assert payload["fx_exposures"][0]["hedged_fraction"] == "0"


def test_v2_rejects_float_hidden_in_metadata() -> None:
    project = _project(metadata={"model_score": 0.25})
    with pytest.raises(ModelInvariantError, match="contains float"):
        project.to_federation_dict_v2()


def test_v2_rejects_float_hidden_in_milestones() -> None:
    project = _project(milestones=({"completion": 0.5},))
    with pytest.raises(ModelInvariantError, match="contains float"):
        project.to_federation_dict_v2()


def test_v2_accepts_decimal_text_in_metadata_when_explicitly_stringified() -> None:
    project = _project(metadata={"model_score": "0.25"})
    payload = project.to_federation_dict_v2()
    assert payload["metadata"]["model_score"] == "0.25"


def test_v2_observed_claim_requires_evidence_digest_but_v1_remains_exportable() -> None:
    project = _project(evidence_status="OBSERVED_OPERATIONAL")
    assert project.to_federation_dict()["evidence_status"] == "OBSERVED_OPERATIONAL"
    with pytest.raises(ModelInvariantError, match="requires evidence_bundle_digest"):
        project.to_federation_dict_v2()

    bound = _project(
        evidence_status="OBSERVED_OPERATIONAL",
        evidence_bundle_digest="ab" * 32,
    )
    assert bound.to_federation_dict_v2()["evidence_bundle_digest"] == "ab" * 32


def test_v2_duplicate_dependencies_fail_closed() -> None:
    project = _project(dependencies=("grid", "grid"))
    with pytest.raises(ModelInvariantError, match="dependencies must be unique"):
        project.to_federation_dict_v2()


def test_maturity_weeks_rejects_cross_language_unsafe_integer() -> None:
    with pytest.raises(ModelInvariantError, match="safe integer"):
        _project(maturity_weeks=9_007_199_254_740_992)
