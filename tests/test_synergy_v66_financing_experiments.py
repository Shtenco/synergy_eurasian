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
