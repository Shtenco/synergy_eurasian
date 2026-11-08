from __future__ import annotations

import pytest

from synergy_v66.continuous_default_experiments import (
    Q3_CLAIM_AMOUNT,
    Q3_CYCLES,
    Q3_RECOVERY_RULES,
    _build_scenario,
    _run_one,
    run_continuous_production_default_experiment,
)


def test_seeded_invoice_paths_are_distinct_but_preserve_aggregate_claim_oracle():
    first = _build_scenario(11)
    second = _build_scenario(23)
    first_amounts = [invoice["amount"] for invoice in first["invoices"]]
    second_amounts = [invoice["amount"] for invoice in second["invoices"]]

    assert len(first_amounts) == Q3_CYCLES
    assert len(second_amounts) == Q3_CYCLES
    assert first["path_fingerprint"] != second["path_fingerprint"]
    assert first_amounts != second_amounts
    assert sum(first_amounts) == pytest.approx(Q3_CLAIM_AMOUNT * Q3_CYCLES, abs=1e-7)
    assert sum(second_amounts) == pytest.approx(Q3_CLAIM_AMOUNT * Q3_CYCLES, abs=1e-7)
    assert min(first_amounts + second_amounts) > 10.0


def test_no_replenishment_path_matches_exact_9000_claim_590_payout_oracle():
    result = _run_one(_build_scenario(11), "no_replenishment")

    assert result["cycle_count"] == 100
    assert result["invoice_count"] == 100
    assert result["defaulted_borrower_count"] == 100
    assert result["invoice_amount_total"] == pytest.approx(10_000.0, abs=1e-7)
    assert result["total_claim_requested"] == pytest.approx(9_000.0, abs=1e-7)
    assert result["total_claim_paid"] == pytest.approx(590.0, abs=1e-7)
    assert result["total_claim_uncovered"] == pytest.approx(8_410.0, abs=1e-7)
    assert result["claim_coverage_ratio"] == pytest.approx(590.0 / 9_000.0)
    assert all(result["invariants"].values())


def test_recovery_policies_share_same_seed_path_and_enforce_cycle_invariants():
    report = run_continuous_production_default_experiment(
        seeds=(37,),
        recovery_rules=("no_replenishment", "equal", "adaptive_liquidity"),
    )

    assert report["cycles_per_path"] == 100
    assert len(report["results"]) == 3
    assert len({row["path_fingerprint"] for row in report["results"]}) == 1
    for row in report["results"]:
        assert row["cycle_count"] == 100
        assert row["defaulted_borrower_count"] == 100
        assert row["invoice_amount_total"] == pytest.approx(10_000.0, abs=1e-7)
        assert all(row["invariants"].values())
        assert row["max_30_day_cap_excess"] <= 1e-7
        assert row["reserve_member_cash_floor_breaches"] == 0


def test_all_supported_recovery_rules_are_declared():
    assert set(Q3_RECOVERY_RULES) == {
        "no_replenishment",
        "equal",
        "production_capacity",
        "opening_cash",
        "adaptive_liquidity",
    }
