import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.financing_experiments import compare_financing_modes


def test_financing_modes_share_paired_environment_and_preserve_invariants():
    report = compare_financing_modes([11, 12], days=18, shock_regime="volatile")
    assert report["model_id"] == "SYNERGY_V6.6.3D_PAIRED_FINANCING_EXPERIMENT"
    assert len(report["observations"]["cash_only"]) == 2
    for pair in report["paired_environment_hashes"]:
        assert len(set(pair["environment_hashes"].values())) == 1
    for mode_rows in report["observations"].values():
        for row in mode_rows:
            assert row["physical_balance_error"] < 1e-7
            assert row["cash_conservation_error"] < 1e-6
            assert row["regional_pool_net_position_error"] < 1e-7
            assert row["regional_pool_utilization_max"] <= 1.0 + 1e-9
            assert 0.0 <= row["service_level"] <= 1.0
            assert row["defaulted_cells"] >= 0.0
    assert set(report["summary"]) == {
        "unconstrained_reference", "cash_only", "bank_only", "mutual_credit", "hybrid"
    }
    assert set(report["paired_deltas_vs_unconstrained_reference"]) == {
        "cash_only", "bank_only", "mutual_credit", "hybrid"
    }
    for mode, rows in report["paired_deltas_vs_unconstrained_reference"].items():
        assert [row["seed"] for row in rows] == [11, 12]
        assert all("service_level" in row for row in rows)
        assert "service_level" in report["paired_delta_summary_vs_unconstrained_reference"][mode]


def test_financing_experiment_is_deterministic():
    first = compare_financing_modes([2026], days=12, shock_regime="severe")
    second = compare_financing_modes([2026], days=12, shock_regime="severe")
    assert first == second


def test_financing_experiment_rejects_invalid_seed_sets_and_regimes():
    with pytest.raises(ValueError):
        compare_financing_modes([], days=5)
    with pytest.raises(ValueError):
        compare_financing_modes([1, 1], days=5)
    with pytest.raises(ValueError):
        compare_financing_modes([1], days=0)
    with pytest.raises(ValueError):
        compare_financing_modes([1], days=5, shock_regime="not-a-regime")


def test_multi_regime_runner_covers_all_shock_regimes_with_paired_paths():
    from synergy_v66.financing_experiments import compare_all_shock_regimes

    report = compare_all_shock_regimes([31, 32], days=10)
    assert report["shock_regimes"] == ["normal", "volatile", "severe"]
    for regime, subreport in report["reports_by_regime"].items():
        assert subreport["shock_regime"] == regime
        for pair in subreport["paired_environment_hashes"]:
            assert len(set(pair["environment_hashes"].values())) == 1
        for rows in subreport["observations"].values():
            for row in rows:
                assert row["physical_balance_error"] < 1e-7
                assert row["cash_conservation_error"] < 1e-6
                assert row["regional_pool_net_position_error"] < 1e-7


def test_regional_pool_sensitivity_grid_respects_caps_and_common_paths():
    from synergy_v66.financing_experiments import compare_regional_pool_sensitivities

    report = compare_regional_pool_sensitivities(
        [42], days=12, shock_regime="severe",
        pool_limits=[0.0, 100.0], member_limits=[0.0, 50.0],
    )
    assert report["model_id"] == "SYNERGY_V6.6.4B_REGIONAL_POOL_SENSITIVITY"
    assert len(report["sensitivity_reports"]) == 4
    for case in report["sensitivity_reports"]:
        assert case["pool_limit_per_region"] in {0.0, 100.0}
        assert case["member_debit_and_credit_limit_per_cell"] in {0.0, 50.0}
        for pair in case["paired_environment_hashes"]:
            assert len(set(pair["environment_hashes"].values())) == 1
        for rows in case["observations"].values():
            for row in rows:
                assert row["physical_balance_error"] < 1e-7
                assert row["cash_conservation_error"] < 1e-6
                assert row["regional_pool_net_position_error"] < 1e-7
                assert row["regional_pool_utilization_max"] <= 1.0 + 1e-9


def test_regional_pool_sensitivity_rejects_empty_limit_grids():
    from synergy_v66.financing_experiments import compare_regional_pool_sensitivities

    with pytest.raises(ValueError):
        compare_regional_pool_sensitivities([1], pool_limits=[])
    with pytest.raises(ValueError):
        compare_regional_pool_sensitivities([1], member_limits=[])


def test_reserve_contribution_scheme_comparison_uses_paired_paths_and_fixed_reserve_size():
    from synergy_v66.financing_experiments import compare_reserve_contribution_schemes

    report = compare_reserve_contribution_schemes(
        [51], days=8, shock_regime="severe", reserve_per_region=12.0,
    )
    assert report["model_id"] == "SYNERGY_V6.6.4D_RESERVE_CONTRIBUTION_FAIRNESS"
    schemes = report["reports_by_contribution_scheme"]
    assert set(schemes) == {
        "equal_all_members", "production_capacity_weighted", "opening_cash_weighted"
    }
    for scheme, payload in schemes.items():
        contributions = payload["contributions_by_cell"]
        for region in ("WEST", "EAST"):
            assert sum(v for k, v in contributions.items() if k.startswith(region + "-")) == pytest.approx(12.0)
        comparison = payload["comparison"]
        assert comparison["base_config"]["regional_pool_reserve_per_region"] == pytest.approx(12.0)
        assert len(set(comparison["paired_environment_hashes"][0]["environment_hashes"].values())) == 1
        for mode in ("mutual_credit", "hybrid"):
            row = comparison["observations"][mode][0]
            assert row["cash_conservation_error"] < 1e-6
            assert row["regional_pool_reserve_balance"] <= 24.0 + 1e-9
        assert comparison["observations"]["cash_only"][0]["regional_pool_reserve_balance"] == pytest.approx(0.0)
        assert comparison["observations"]["bank_only"][0]["regional_pool_reserve_balance"] == pytest.approx(0.0)


def test_reserve_contribution_scheme_rejects_unknown_rule():
    from synergy_v66.financing_experiments import build_regional_reserve_contributions

    with pytest.raises(ValueError):
        build_regional_reserve_contributions("equal_but_not_equal")


def test_regional_loss_waterfall_comparison_keeps_paired_environments_and_cash_balance():
    from synergy_v66.financing_experiments import compare_regional_loss_waterfalls

    report = compare_regional_loss_waterfalls(
        [61], days=10, shock_regime="severe",
        reserve_per_region=10.0, assessment_rate=0.10,
        assessment_limit_per_cell=1.0,
    )
    assert report["model_id"] == "SYNERGY_V6.6.4E_REGIONAL_LOSS_WATERFALL"
    cases = report["reports_by_waterfall"]
    assert set(cases) == {"reserve_only", "reserve_plus_capped_assessment"}
    for case in cases.values():
        for pair in case["paired_environment_hashes"]:
            assert len(set(pair["environment_hashes"].values())) == 1
        for mode in ("mutual_credit", "hybrid"):
            for row in case["observations"][mode]:
                assert row["cash_conservation_error"] < 1e-6
                assert row["regional_pool_net_position_error"] < 1e-7
    assessment = cases["reserve_plus_capped_assessment"]["observations"]["mutual_credit"][0]
    assert assessment["regional_member_assessment_paid"] >= 0.0


def test_regional_loss_waterfall_rejects_non_finite_assessment_parameters():
    from synergy_v66.financing_experiments import compare_regional_loss_waterfalls

    with pytest.raises(ValueError):
        compare_regional_loss_waterfalls([1], assessment_rate=float("nan"))
    with pytest.raises(ValueError):
        compare_regional_loss_waterfalls([1], assessment_limit_per_cell=float("inf"))


def test_targeted_default_stress_exercises_local_reserve_assessment_and_cross_region_boundary():
    from synergy_v66.financing_experiments import run_targeted_regional_default_stress_cases

    report = run_targeted_regional_default_stress_cases()
    cases = report["cases"]
    reserve_only = cases["local_reserve_only"]
    assert reserve_only["guarantee_paid"] == pytest.approx(5.0)
    assert reserve_only["member_assessment_paid"] == pytest.approx(0.0)
    assert reserve_only["written_off"] == pytest.approx(5.5)

    assessed = cases["local_reserve_plus_assessment"]
    assert assessed["guarantee_paid"] == pytest.approx(5.0)
    assert assessed["member_assessment_paid"] == pytest.approx(5.5)
    assert assessed["written_off"] == pytest.approx(0.0)
    assert assessed["regional_assessment_attempt_count"] == 1
    assert assessed["regional_assessment_requested_by_region"]["WEST"] == pytest.approx(5.5)
    assert assessed["regional_assessment_eligible_capacity_by_region"]["WEST"] == pytest.approx(15.6)
    assert assessed["cash_conservation_error"] == pytest.approx(0.0)

    capped = cases["local_tightly_capped_assessment"]
    assert capped["member_assessment_paid"] == pytest.approx(2.0)
    assert capped["written_off"] == pytest.approx(3.5)
    assert capped["cash_conservation_error"] == pytest.approx(0.0)

    cross = cases["cross_region_assessment_ineligible"]
    assert cross["guarantee_paid"] == pytest.approx(0.0)
    assert cross["member_assessment_paid"] == pytest.approx(0.0)
    assert cross["written_off"] == pytest.approx(10.5)
    assert cross["regional_assessment_attempt_count"] == 0
    assert cross["trade_bad_debt_by_cell"]["EAST-AG1"] == pytest.approx(10.5)
    assert cross["cash_conservation_error"] == pytest.approx(0.0)

    federated = cases["cross_region_federation_pool"]
    assert federated["guarantee_paid"] == pytest.approx(0.0)
    assert federated["federation_guarantee_paid"] == pytest.approx(5.0)
    assert federated["member_assessment_paid"] == pytest.approx(0.0)
    assert federated["written_off"] == pytest.approx(5.75)
    assert federated["federation_pool_reserve_balance"] == pytest.approx(0.0)
    assert federated["cash_conservation_error"] == pytest.approx(0.0)


def test_liquidity_capped_reserve_allocation_respects_each_member_cap_and_region_total():
    from synergy_v66.financing_experiments import build_liquidity_capped_reserve_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 40.0 + index * 2.0 for index, cell in enumerate(CELLS)}
    contributions = build_liquidity_capped_reserve_contributions(
        "production_capacity_weighted", 10.0, cash, max_contribution_fraction=0.10,
    )
    for cell_id, contribution in contributions.items():
        assert contribution <= cash[cell_id] * 0.10 + 1e-9
    for region in ("WEST", "EAST"):
        assert sum(contributions[cell.cell_id] for cell in CELLS if cell.region == region) == pytest.approx(10.0)


def test_liquidity_capped_reserve_allocation_rejects_insufficient_funding_capacity():
    from synergy_v66.financing_experiments import build_liquidity_capped_reserve_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 1.0 for cell in CELLS}
    with pytest.raises(ValueError):
        build_liquidity_capped_reserve_contributions(
            "equal_all_members", 1.0, cash, max_contribution_fraction=0.01,
        )


def test_liquidity_capped_reserve_experiment_uses_heterogeneous_cash_and_paired_paths():
    from synergy_v66.financing_experiments import compare_liquidity_capped_reserve_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 80.0 + index * 5.0 for index, cell in enumerate(CELLS)}
    report = compare_liquidity_capped_reserve_contributions(
        [71], cash, days=6, reserve_per_region=10.0,
        max_contribution_fraction=0.10,
    )
    assert report["model_id"] == "SYNERGY_V6.6.4F_LIQUIDITY_CAPPED_RESERVE"
    assert report["initial_cash_by_cell"] == cash
    for cell_id, contribution in report["contributions_by_cell"].items():
        assert contribution <= cash[cell_id] * 0.10 + 1e-9
    for pair in report["comparison"]["paired_environment_hashes"]:
        assert len(set(pair["environment_hashes"].values())) == 1
    for mode in ("mutual_credit", "hybrid"):
        for row in report["comparison"]["observations"][mode]:
            assert row["cash_conservation_error"] < 1e-6


def test_liquidity_capped_reserve_allocation_rejects_boolean_and_invalid_cash():
    from synergy_v66.financing_experiments import build_liquidity_capped_reserve_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 50.0 for cell in CELLS}
    cash[CELLS[0].cell_id] = True
    with pytest.raises(ValueError):
        build_liquidity_capped_reserve_contributions("equal_all_members", 5.0, cash)


def test_synthetic_heterogeneous_cash_fixture_is_deterministic_and_validated():
    from synergy_v66.financing_experiments import make_synthetic_heterogeneous_cash_fixture
    from synergy_v66.network_topology import CELLS

    first = make_synthetic_heterogeneous_cash_fixture(75.0, 2.5)
    second = make_synthetic_heterogeneous_cash_fixture(75.0, 2.5)
    assert first == second
    assert set(first) == {cell.cell_id for cell in CELLS}
    assert len(set(first.values())) == len(CELLS)
    with pytest.raises(ValueError):
        make_synthetic_heterogeneous_cash_fixture(float("nan"), 1.0)


def test_regional_reserve_size_sensitivity_uses_paired_paths_and_reports_liquidity_cost():
    from synergy_v66.financing_experiments import compare_regional_reserve_size_sensitivities

    report = compare_regional_reserve_size_sensitivities(
        seeds=[81, 82], reserve_levels_per_region=[0.0, 5.0, 10.0],
        days=8, shock_regime="severe",
    )
    assert report["model_id"] == "SYNERGY_V6.6.4G_REGIONAL_RESERVE_ADEQUACY"
    assert [x["reserve_per_region"] for x in report["sensitivity_reports"]] == [0.0, 5.0, 10.0]
    for item in report["sensitivity_reports"]:
        assert item["total_initial_reserve"] == pytest.approx(2.0 * item["reserve_per_region"])
        for pair in item["comparison"]["paired_environment_hashes"]:
            assert len(set(pair["environment_hashes"].values())) == 1
        for mode in ("mutual_credit", "hybrid"):
            diagnostics = item["diagnostics"][mode]
            assert diagnostics["cash_conservation_error_max"] < 1e-6
            assert diagnostics["reserve_remaining_mean"] >= -1e-9
            assert 0.0 <= diagnostics["reserve_exhaustion_rate"] <= 1.0


def test_regional_reserve_size_sensitivity_supports_liquidity_caps_and_rejects_invalid_levels():
    from synergy_v66.financing_experiments import (
        compare_regional_reserve_size_sensitivities,
        make_synthetic_heterogeneous_cash_fixture,
    )

    cash = make_synthetic_heterogeneous_cash_fixture()
    report = compare_regional_reserve_size_sensitivities(
        seeds=[83], reserve_levels_per_region=[5.0], days=5,
        max_contribution_fraction=0.10,
        base_config={"initial_cash_by_cell": cash},
    )
    assert report["sensitivity_reports"][0]["total_initial_reserve"] == pytest.approx(10.0)
    with pytest.raises(ValueError):
        compare_regional_reserve_size_sensitivities([1], [float("nan")])


def test_opening_cash_weighted_reserve_contributions_scale_with_member_liquidity():
    from synergy_v66.financing_experiments import build_regional_reserve_contributions
    from synergy_v66.network_topology import CELLS

    cash = {
        cell.cell_id: (100.0 if cell.cell_id.endswith(("AG1", "AG2", "PR1", "PR2", "MF1", "MF2")) else 20.0)
        for cell in CELLS
    }
    contributions = build_regional_reserve_contributions(
        "opening_cash_weighted", 20.0, cash
    )
    for region in ("WEST", "EAST"):
        members = [cell for cell in CELLS if cell.region == region]
        assert sum(contributions[cell.cell_id] for cell in members) == pytest.approx(20.0)
        ratios = [
            contributions[cell.cell_id] / cash[cell.cell_id]
            for cell in members
        ]
        assert max(ratios) == pytest.approx(min(ratios))
    assert contributions["WEST-AG1"] > contributions["WEST-WH"]
    assert contributions["WEST-AG1"] / cash["WEST-AG1"] == pytest.approx(
        contributions["WEST-WH"] / cash["WEST-WH"]
    )


def test_opening_cash_weighted_reserve_rejects_zero_capacity_and_bad_member_cash():
    from synergy_v66.financing_experiments import build_regional_reserve_contributions
    from synergy_v66.network_topology import CELLS

    zero_cash = {cell.cell_id: 0.0 for cell in CELLS}
    with pytest.raises(ValueError):
        build_regional_reserve_contributions("opening_cash_weighted", 1.0, zero_cash)
    incomplete = {cell.cell_id: 10.0 for cell in CELLS}
    incomplete.pop(CELLS[0].cell_id)
    with pytest.raises(ValueError):
        build_regional_reserve_contributions("opening_cash_weighted", 1.0, incomplete)
    invalid = {cell.cell_id: 10.0 for cell in CELLS}
    invalid[CELLS[0].cell_id] = float("nan")
    with pytest.raises(ValueError):
        build_regional_reserve_contributions("opening_cash_weighted", 1.0, invalid)


def test_reserve_allocation_experiment_accepts_heterogeneous_member_cash_and_reconciles():
    from synergy_v66.financing_experiments import compare_reserve_contribution_schemes
    from synergy_v66.network_topology import CELLS

    opening_cash = {
        cell.cell_id: (120.0 if cell.sector in {"primary", "processing", "manufacturing"} else 40.0)
        for cell in CELLS
    }
    report = compare_reserve_contribution_schemes(
        [71], days=5, shock_regime="severe", reserve_per_region=10.0,
        base_config={"initial_cash_by_cell": opening_cash},
    )
    schemes = report["reports_by_contribution_scheme"]
    assert set(schemes) == {
        "equal_all_members", "production_capacity_weighted", "opening_cash_weighted"
    }
    for scheme in schemes.values():
        comparison = scheme["comparison"]
        assert comparison["base_config"]["initial_cash_by_cell"] == opening_cash
        for mode in ("mutual_credit", "hybrid"):
            row = comparison["observations"][mode][0]
            assert row["cash_conservation_error"] < 1e-6


def test_federation_reserve_allocator_respects_combined_regional_and_federal_member_cap():
    from synergy_v66.financing_experiments import (
        build_liquidity_capped_federation_contributions,
        build_liquidity_capped_reserve_contributions,
    )
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 100.0 + 3.0 * index for index, cell in enumerate(CELLS)}
    regional = build_liquidity_capped_reserve_contributions(
        "equal_all_members", 5.0, cash, max_contribution_fraction=0.10,
    )
    federal = build_liquidity_capped_federation_contributions(
        10.0, cash, max_combined_contribution_fraction=0.10,
        scheme="production_capacity_weighted",
        regional_contributions_by_cell=regional,
    )
    for cell in CELLS:
        assert regional[cell.cell_id] + federal[cell.cell_id] <= cash[cell.cell_id] * 0.10 + 1e-9
    assert sum(federal.values()) == pytest.approx(10.0)


def test_federation_reserve_allocator_rejects_insufficient_remaining_cap_and_bad_maps():
    from synergy_v66.financing_experiments import build_liquidity_capped_federation_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 10.0 for cell in CELLS}
    with pytest.raises(ValueError):
        build_liquidity_capped_federation_contributions(
            2.01, cash, max_combined_contribution_fraction=0.01,
        )
    regional = {cell.cell_id: 0.0 for cell in CELLS}
    regional[CELLS[0].cell_id] = 2.0
    with pytest.raises(ValueError):
        build_liquidity_capped_federation_contributions(
            1.0, cash, max_combined_contribution_fraction=0.10,
            regional_contributions_by_cell=regional,
        )
    regional.pop(CELLS[0].cell_id)
    with pytest.raises(ValueError):
        build_liquidity_capped_federation_contributions(
            1.0, cash, regional_contributions_by_cell=regional,
        )


def test_liquidity_capped_federation_experiment_uses_paired_paths_and_cash_conservation():
    from synergy_v66.financing_experiments import (
        compare_liquidity_capped_federation_contributions,
        make_synthetic_heterogeneous_cash_fixture,
    )

    cash = make_synthetic_heterogeneous_cash_fixture()
    report = compare_liquidity_capped_federation_contributions(
        [91], cash, reserve_total=8.0, max_combined_contribution_fraction=0.10,
        scheme="production_capacity_weighted", days=7,
    )
    assert report["model_id"] == "SYNERGY_V6.6.4I_LIQUIDITY_CAPPED_FEDERATION_RESERVE"
    assert sum(report["federation_contributions_by_cell"].values()) == pytest.approx(8.0)
    for cell_id, federal in report["federation_contributions_by_cell"].items():
        regional = report["regional_contributions_by_cell"][cell_id]
        assert federal + regional <= cash[cell_id] * 0.10 + 1e-9
    for pair in report["comparison"]["paired_environment_hashes"]:
        assert len(set(pair["environment_hashes"].values())) == 1
    for mode in ("mutual_credit", "hybrid"):
        for row in report["comparison"]["observations"][mode]:
            assert row["cash_conservation_error"] < 1e-6
            assert row["federation_pool_reserve_balance"] <= 8.0 + 1e-9


def test_federation_liquidity_capped_allocator_rejects_invalid_scheme_and_nonfinite_caps():
    from synergy_v66.financing_experiments import build_liquidity_capped_federation_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 100.0 for cell in CELLS}
    with pytest.raises(ValueError):
        build_liquidity_capped_federation_contributions(1.0, cash, scheme="risk-based")
    with pytest.raises(ValueError):
        build_liquidity_capped_federation_contributions(1.0, cash, max_combined_contribution_fraction=float("nan"))


def test_liquidity_capped_regional_allocator_preserves_absolute_member_cash_floor():
    from synergy_v66.financing_experiments import build_liquidity_capped_reserve_contributions
    from synergy_v66.network_topology import CELLS

    cash = {
        cell.cell_id: (100.0 if cell.sector in {"primary", "processing", "manufacturing"} else 40.0)
        for cell in CELLS
    }
    contributions = build_liquidity_capped_reserve_contributions(
        "equal_all_members", 12.0, cash,
        max_contribution_fraction=0.20,
        minimum_post_contribution_cash=39.0,
    )
    for cell in CELLS:
        amount = contributions[cell.cell_id]
        assert cash[cell.cell_id] - amount >= 39.0 - 1e-9
        assert amount <= cash[cell.cell_id] * 0.20 + 1e-9
    for region in ("WEST", "EAST"):
        assert sum(v for k, v in contributions.items() if k.startswith(region + "-")) == pytest.approx(12.0)


def test_liquidity_capped_regional_allocator_rejects_floor_incompatible_reserve():
    from synergy_v66.financing_experiments import build_liquidity_capped_reserve_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 10.0 for cell in CELLS}
    with pytest.raises(ValueError):
        build_liquidity_capped_reserve_contributions(
            "equal_all_members", 2.0, cash,
            max_contribution_fraction=0.5,
            minimum_post_contribution_cash=9.9,
        )
    with pytest.raises(ValueError):
        build_liquidity_capped_reserve_contributions(
            "equal_all_members", 1.0, cash,
            max_contribution_fraction=0.5,
            minimum_post_contribution_cash=float("nan"),
        )


def test_liquidity_capped_federation_allocator_preserves_floor_after_regional_contributions():
    from synergy_v66.financing_experiments import build_liquidity_capped_federation_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 100.0 for cell in CELLS}
    regional = {cell.cell_id: 0.5 for cell in CELLS}
    federal = build_liquidity_capped_federation_contributions(
        10.0, cash, max_combined_contribution_fraction=0.20,
        scheme="equal_all_members",
        regional_contributions_by_cell=regional,
        minimum_post_contribution_cash=99.0,
    )
    for cell in CELLS:
        combined = regional[cell.cell_id] + federal[cell.cell_id]
        assert cash[cell.cell_id] - combined >= 99.0 - 1e-9
        assert combined <= cash[cell.cell_id] * 0.20 + 1e-9
    assert sum(federal.values()) == pytest.approx(10.0)


def test_federation_allocator_rejects_existing_regional_contribution_below_cash_floor():
    from synergy_v66.financing_experiments import build_liquidity_capped_federation_contributions
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 100.0 for cell in CELLS}
    regional = {cell.cell_id: 0.0 for cell in CELLS}
    regional["WEST-AG1"] = 2.0
    with pytest.raises(ValueError):
        build_liquidity_capped_federation_contributions(
            0.0, cash, max_combined_contribution_fraction=0.5,
            regional_contributions_by_cell=regional,
            minimum_post_contribution_cash=99.0,
        )


def test_federation_reserve_fcfs_and_batch_pro_rata_rules_conserve_and_allocate_same_claim_batch():
    from synergy_v66.financing_experiments import compare_federation_reserve_allocation_rules

    claims = [
        {"invoice_id": "C-3", "due_day": 2, "eligible_amount": 30.0},
        {"invoice_id": "C-1", "due_day": 1, "eligible_amount": 10.0},
        {"invoice_id": "C-2", "due_day": 1, "eligible_amount": 20.0},
    ]
    report = compare_federation_reserve_allocation_rules(claims, reserve_available=25.0)
    fcfs = report["reports_by_rule"]["first_come_first_served"]
    pro_rata = report["reports_by_rule"]["batch_pro_rata"]
    assert fcfs["allocation_order"] == ["C-1", "C-2", "C-3"]
    assert fcfs["allocations_by_invoice"] == {
        "C-1": pytest.approx(10.0),
        "C-2": pytest.approx(15.0),
        "C-3": pytest.approx(0.0),
    }
    assert pro_rata["allocations_by_invoice"]["C-1"] == pytest.approx(25.0 / 60.0 * 10.0)
    assert pro_rata["allocations_by_invoice"]["C-2"] == pytest.approx(25.0 / 60.0 * 20.0)
    assert pro_rata["allocations_by_invoice"]["C-3"] == pytest.approx(25.0 / 60.0 * 30.0)
    for row in (fcfs, pro_rata):
        assert row["allocated_total"] <= 25.0 + 1e-9
        assert row["reserve_remaining"] + row["allocated_total"] == pytest.approx(25.0)
        assert sum(row["uncovered_by_invoice"].values()) == pytest.approx(60.0 - row["allocated_total"])
        assert row["allocation_conservation_error"] == pytest.approx(0.0)


def test_federation_reserve_batch_allocation_validates_claims_and_reserve():
    from synergy_v66.financing_experiments import allocate_federation_reserve_claims

    with pytest.raises(ValueError):
        allocate_federation_reserve_claims([{"invoice_id": "X", "eligible_amount": float("nan")}], 10.0)
    with pytest.raises(ValueError):
        allocate_federation_reserve_claims(
            [{"invoice_id": "X", "eligible_amount": 1.0}, {"invoice_id": "X", "eligible_amount": 2.0}],
            10.0,
        )
    with pytest.raises(ValueError):
        allocate_federation_reserve_claims([], -1.0)
    with pytest.raises(ValueError):
        allocate_federation_reserve_claims([], 10.0, rule="priority-by-favor")


def test_regional_reserve_sizing_respects_absolute_post_contribution_cash_floor():
    from synergy_v66.financing_experiments import compare_regional_reserve_size_sensitivities
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 80.0 + index * 5.0 for index, cell in enumerate(CELLS)}
    report = compare_regional_reserve_size_sensitivities(
        seeds=[101], reserve_levels_per_region=[20.0], days=4,
        max_contribution_fraction=0.10,
        base_config={"initial_cash_by_cell": cash},
        minimum_post_contribution_cash=79.0,
    )
    item = report["sensitivity_reports"][0]
    assert report["minimum_post_contribution_cash"] == pytest.approx(79.0)
    for cell_id, contribution in item["contributions_by_cell"].items():
        assert cash[cell_id] - contribution >= 79.0 - 1e-9


def test_reserve_sizing_can_apply_absolute_cash_floor_without_fractional_cap():
    from synergy_v66.financing_experiments import compare_regional_reserve_size_sensitivities
    from synergy_v66.network_topology import CELLS

    cash = {cell.cell_id: 80.0 for cell in CELLS}
    report = compare_regional_reserve_size_sensitivities(
        seeds=[102], reserve_levels_per_region=[10.0], days=3,
        base_config={"initial_cash_by_cell": cash},
        minimum_post_contribution_cash=79.0,
    )
    for cell_id, contribution in report["sensitivity_reports"][0]["contributions_by_cell"].items():
        assert cash[cell_id] - contribution >= 79.0 - 1e-9
