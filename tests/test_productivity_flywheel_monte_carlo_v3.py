from pathlib import Path
import copy
import pytest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_productivity_flywheel_monte_carlo_v3 import (
    build_report,
    load_config,
    simulate_paths,
)


def test_monte_carlo_is_reproducible_and_probabilities_are_bounded():
    cfg = load_config()
    cfg["paths"] = 500
    a = simulate_paths(cfg, 0.03)
    b = simulate_paths(cfg, 0.03)
    assert a == b
    assert 0.0 <= a["reserve_exhaustion_probability"] <= 1.0
    assert a["paths"] == 500


def test_no_correlated_shocks_has_no_reserve_exhaustion_in_reference_seed():
    cfg = load_config()
    cfg["paths"] = 1000
    result = simulate_paths(cfg, 0.0)
    assert result["reserve_exhaustion_probability"] == 0.0
    assert result["probability_of_any_unfunded_gap"] == 0.0


def test_shock_probability_increases_tail_risk_in_reference_seed():
    cfg = load_config()
    cfg["paths"] = 2000
    low = simulate_paths(cfg, 0.0)
    high = simulate_paths(cfg, 0.10)
    assert high["reserve_exhaustion_probability"] > low["reserve_exhaustion_probability"]
    assert high["cumulative_unfunded_gap_usd_quantiles"]["p95"] >= low["cumulative_unfunded_gap_usd_quantiles"]["p95"]


def test_report_contains_five_shock_scenarios():
    cfg = load_config()
    cfg["paths"] = 100
    report = build_report(cfg)
    assert len(report["shock_sensitivity"]) == 5


def test_monte_carlo_rejects_invalid_dimensions_distributions_and_overflow():
    cfg = load_config()
    with pytest.raises(ValueError, match="finite"):
        simulate_paths(cfg, float("nan"))
    with pytest.raises(ValueError, match="finite JSON number"):
        simulate_paths(cfg, True)

    bad = copy.deepcopy(cfg)
    bad["paths"] = 10.5
    with pytest.raises(ValueError, match="integer"):
        simulate_paths(bad, 0.01)

    bad = copy.deepcopy(cfg)
    bad["horizon_years"] = 0
    with pytest.raises(ValueError, match="integer"):
        simulate_paths(bad, 0.01)

    bad = copy.deepcopy(cfg)
    bad["annual_uncertainty"]["cashflow_growth_std"] = -0.1
    with pytest.raises(ValueError, match="standard deviations"):
        simulate_paths(bad, 0.01)

    bad = copy.deepcopy(cfg)
    bad["annual_uncertainty"]["replacement_inflation_min"] = -1.1
    with pytest.raises(ValueError, match="bounds cannot be below"):
        simulate_paths(bad, 0.01)

    bad = copy.deepcopy(cfg)
    bad["rd_projects"]["independent_projects_per_year"] = 0
    with pytest.raises(ValueError, match="integer"):
        simulate_paths(bad, 0.01)

    bad = copy.deepcopy(cfg)
    bad["starting_point"]["productive_capital_usd"] = -1
    with pytest.raises(ValueError, match="must be positive"):
        simulate_paths(bad, 0.01)

    bad = copy.deepcopy(cfg)
    bad["random_seed"] = 10**10000
    with pytest.raises(ValueError, match="random_seed"):
        simulate_paths(bad, 0.01)



def test_monte_carlo_rejects_unknown_funds_and_labels_non_ten_year_horizons():
    cfg = load_config()
    bad = copy.deepcopy(cfg)
    bad["fund_allocation"]["unmodeled_fund"] = 0.1
    bad["fund_allocation"]["resilience_reserve"] -= 0.1
    with pytest.raises(ValueError, match="exactly the three modeled funds"):
        simulate_paths(bad, 0.01)

    short = copy.deepcopy(cfg)
    short["paths"] = 100
    short["horizon_years"] = 5
    result = simulate_paths(short, 0.0)
    assert result["horizon_years"] == 5
    assert result["final_year_residual_usd_quantiles"]
    assert result["year_10_residual_usd_quantiles"] is None


def test_monte_carlo_rejects_overflowing_annual_path_values():
    cfg = load_config()
    cfg["paths"] = 2
    cfg["starting_point"]["gross_cashflow_after_opex_before_replacement_usd"] = 1e308
    cfg["annual_uncertainty"]["cashflow_growth_mean"] = 1e308
    cfg["annual_uncertainty"]["cashflow_growth_std"] = 0.0
    cfg["annual_uncertainty"]["cashflow_growth_min"] = 1e308
    cfg["annual_uncertainty"]["cashflow_growth_max"] = 1e308
    with pytest.raises(ValueError, match="gross cashflow"):
        simulate_paths(cfg, 0.0)
