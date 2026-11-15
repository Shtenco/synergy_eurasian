from __future__ import annotations

import pytest

from synergy_v66.continuous_default_experiments import (
    Q3_CYCLES,
    _build_scenario,
    _run_one,
    run_continuous_production_default_experiment,
)


def test_q3_scenario_contains_100_distinct_borrowers_and_invoices():
    scenario = _build_scenario(11)
    buyers = [row["buyer"] for row in scenario["invoices"]]
    invoice_ids = [row["invoice_id"] for row in scenario["invoices"]]
    assert len(scenario["invoices"]) == Q3_CYCLES
    assert len(set(buyers)) == Q3_CYCLES
    assert len(set(invoice_ids)) == Q3_CYCLES
    assert len(scenario["cells"]) == 210


def test_no_replenishment_runs_100_real_production_defaults_continuously():
    scenario = _build_scenario(11)
    result = _run_one(scenario, "no_replenishment")
    assert result["cycle_count"] == 100
    assert result["invoice_count"] == 100
    assert result["defaulted_borrower_count"] == 100
    assert result["total_claim_requested"] == pytest.approx(9000.0)
    assert result["total_member_contributions"] == pytest.approx(0.0)
    assert result["total_claim_paid"] == pytest.approx(590.0)
    assert result["total_claim_uncovered"] == pytest.approx(8410.0)
    assert all(result["invariants"].values())


def test_recovery_policy_preserves_production_default_and_accounting_invariants():
    scenario = _build_scenario(23)
    result = _run_one(scenario, "equal")
    assert result["cycle_count"] == 100
    assert result["defaulted_borrower_count"] == 100
    assert result["total_member_contributions"] > 0.0
    assert result["total_claim_requested"] == pytest.approx(9000.0)
    assert result["total_claim_paid"] + result["total_claim_uncovered"] == pytest.approx(9000.0)
    assert all(result["invariants"].values())


def test_paired_recovery_policies_share_the_same_exogenous_invoice_path():
    report = run_continuous_production_default_experiment(
        seeds=(37,),
        recovery_rules=("no_replenishment", "equal"),
    )
    results = report["results"]
    assert len(results) == 2
    assert results[0]["path_fingerprint"] == results[1]["path_fingerprint"]
    assert all(all(row["invariants"].values()) for row in results)


def test_recovery_cannot_charge_defaulted_borrowers_or_exceed_shared_period_cap():
    scenario = _build_scenario(41)
    result = _run_one(scenario, "adaptive_liquidity")
    assert result["max_30_day_cap_excess"] <= 1e-7
    assert result["reserve_member_cash_floor_breaches"] == 0
    assert result["total_member_contributions"] > 0.0
    assert result["invariants"]["no_defaulted_borrower_contributes"]
