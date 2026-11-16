from __future__ import annotations

import pytest

from synergy_v66.default_batch_experiments import (
    run_paired_production_default_batch_experiment,
)


def _row(report, clearing, recovery):
    return report["observations"][f"{clearing}|{recovery}"][0]


def test_100_invoice_cohort_uses_real_default_waterfall_and_reconciles_claims():
    report = run_paired_production_default_batch_experiment(
        seeds=[11],
        clearing_rules=["first_come_first_served"],
        recovery_rules=["no_replenishment"],
    )
    row = _row(report, "first_come_first_served", "no_replenishment")

    assert report["invoice_cohort_size"] == 100
    assert row["invoice_count"] == 100
    assert row["default_resolution_invoice_count"] > 0
    assert row["defaulted_buyer_count"] == 10
    assert row["defaulted_seller_count"] == 0
    assert row["total_claim_requested"] > 0
    assert row["local_guarantee_paid"] > 0
    assert row["federation_guarantee_paid"] > 0
    assert row["claim_reconciliation_error"] <= 1e-8
    assert row["seller_bad_debt_reconciliation_error"] <= 1e-8
    assert row["seller_trade_bad_debt_total"] == pytest.approx(row["total_claim_uncovered"])
    assert row["external_supplier_bad_debt"] == pytest.approx(0.0)
    assert row["total_claim_requested"] == pytest.approx(
        row["total_claim_paid"] + row["total_claim_uncovered"]
    )
    assert row["bank_draws"] == pytest.approx(0.0)
    assert row["external_inflows"] == pytest.approx(0.0)
    assert row["external_outflows"] == pytest.approx(0.0)
    assert row["max_cash_conservation_error"] <= 1e-8
    assert abs(row["system_cash_change"]) <= 1e-8
    assert all(report["invariants"].values())


def test_fcfs_and_batch_pro_rata_reconcile_same_losses_but_change_seller_distribution():
    report = run_paired_production_default_batch_experiment(
        seeds=[23],
        clearing_rules=["first_come_first_served", "batch_pro_rata"],
        recovery_rules=["no_replenishment"],
    )
    fcfs = _row(report, "first_come_first_served", "no_replenishment")
    batch = _row(report, "batch_pro_rata", "no_replenishment")

    assert batch["total_claim_requested"] == pytest.approx(fcfs["total_claim_requested"])
    assert batch["total_claim_paid"] == pytest.approx(fcfs["total_claim_paid"])
    assert batch["total_claim_uncovered"] == pytest.approx(fcfs["total_claim_uncovered"])
    assert sum(batch["seller_guarantee_payout_by_cell"].values()) == pytest.approx(
        sum(fcfs["seller_guarantee_payout_by_cell"].values())
    )
    assert batch["seller_guarantee_payout_by_cell"] != fcfs["seller_guarantee_payout_by_cell"]


def test_real_default_batch_replenishment_respects_cash_floor_and_period_cap():
    report = run_paired_production_default_batch_experiment(
        seeds=[37],
        clearing_rules=["batch_pro_rata"],
    )
    for recovery in ("equal", "production_capacity", "opening_cash", "adaptive_liquidity"):
        row = _row(report, "batch_pro_rata", recovery)
        assert row["recovery_requested"] == pytest.approx(80.0)
        assert row["recovered"] == pytest.approx(80.0)
        assert row["recovery_unfunded"] == pytest.approx(0.0)
        assert row["total_member_contributions"] == pytest.approx(80.0)
        assert row["contributor_cash_floor_breach_count"] == 0
        assert row["minimum_contributor_cash"] >= 20.0 - 1e-8
        assert row["max_contribution_opening_cash_ratio"] <= 0.10 + 1e-8
        assert row["max_period_cap_excess"] <= 1e-8
        assert row["max_cash_conservation_error"] <= 1e-8
        assert abs(row["system_cash_change"]) <= 1e-8
