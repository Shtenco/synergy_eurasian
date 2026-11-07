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
    assert set(schemes) == {"equal_all_members", "production_capacity_weighted"}
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
