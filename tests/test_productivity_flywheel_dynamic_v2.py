from pathlib import Path
import copy
import pytest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_productivity_flywheel_dynamic_v2 import (
    build_report,
    break_even_cashflow_growth,
    load_config,
    simulate_case,
)


def test_ten_year_moderate_growth_scenario_reconciles():
    cfg = load_config()
    result = simulate_case(cfg, 0.025, 0.02)
    assert abs(result["year_10_residual_usd"] - 133184.86560877494) < 1e-5
    assert abs(result["final_reserve_usd"] - 1836141.3030361512) < 1e-5
    assert abs(result["cumulative_automation_contributions_usd"] - 382282.606072302) < 1e-5
    assert abs(result["cumulative_rd_contributions_usd"] - 191141.303036151) < 1e-5
    assert result["cumulative_unfunded_gap_usd"] == 0


def test_severe_replacement_inflation_exhausts_reserve_and_reports_gap():
    result = simulate_case(load_config(), 0.05, 0.10)
    assert abs(result["final_reserve_usd"]) < 1e-8
    assert abs(result["cumulative_reserve_draws_usd"] - 1645000) < 1e-5
    assert abs(result["cumulative_unfunded_gap_usd"] - 2586184.4783417303) < 1e-5


def test_stagnation_uses_reserve_instead_of_faking_positive_fund_inflows():
    result = simulate_case(load_config(), 0.0, 0.02)
    assert result["cumulative_reserve_draws_usd"] > 1_000_000
    assert result["cumulative_automation_contributions_usd"] < 1_000
    assert result["cumulative_rd_contributions_usd"] < 1_000


def test_break_even_growth_thresholds():
    start = load_config()["starting_point"]
    cash = start["gross_cashflow_after_opex_before_replacement_usd"]
    repl = start["replacement_capex_usd"]
    assert abs(break_even_cashflow_growth(cash, repl, 0.02, 10) - 0.017870165227696466) < 1e-10
    assert abs(break_even_cashflow_growth(cash, repl, 0.05, 10) - 0.0478075230285111) < 1e-10
    assert abs(break_even_cashflow_growth(cash, repl, 0.10, 10) - 0.09770311936320208) < 1e-10


def test_report_contains_all_six_macro_scenarios():
    report = build_report(load_config())
    assert len(report["macro_scenarios"]) == 6
    assert len(report["break_even_cashflow_growth_without_project_returns"]) == 3


def test_sector_reconciliation_exposes_hidden_sector_gaps():
    from synergy_productivity_flywheel_dynamic_v2 import sector_reconciliation
    cfg = load_config()
    moderate = sector_reconciliation(cfg, 0.025, 0.02)
    strong_cost_pressure = sector_reconciliation(cfg, 0.05, 0.05)
    assert abs(moderate["net_residual_usd"] - 92175.65049759479) < 1e-5
    assert abs(moderate["negative_sector_gap_usd"] - 158607.7956229701) < 1e-5
    sectors = {x["sector"]: x for x in moderate["sectors"]}
    assert sectors["EDUCATION"]["year_n_residual_usd"] < -56000
    assert sectors["MOBILITY"]["year_n_residual_usd"] < -87000
    assert abs(strong_cost_pressure["net_residual_usd"] - 35986.35454208049) < 1e-5
    assert abs(strong_cost_pressure["reconciliation_error_usd"]) < 1e-7



def test_deterministic_flywheel_accepts_recession_and_replacement_deflation():
    cfg = load_config()
    recession = simulate_case(cfg, -0.05, 0.02)
    deflation = simulate_case(cfg, 0.02, -0.01)
    assert recession["cumulative_unfunded_gap_usd"] > 0
    assert deflation["year_10_residual_usd"] > recession["year_10_residual_usd"]
    try:
        simulate_case(cfg, -1.01, 0.02)
    except ValueError as exc:
        assert "at least -100%" in str(exc)
    else:
        raise AssertionError("Cashflow decline below -100% must be rejected")


def test_dynamic_flywheel_rejects_invalid_financial_and_horizon_inputs():
    cfg = load_config()
    with pytest.raises(ValueError, match="finite"):
        simulate_case(cfg, float("nan"), 0.02)
    with pytest.raises(ValueError, match="finite JSON number"):
        simulate_case(cfg, True, 0.02)
    with pytest.raises(ValueError, match="non-negative"):
        simulate_case(cfg, 0.02, 0.02, automation_yield=-0.1)
    with pytest.raises(ValueError, match="between 0 and 1"):
        simulate_case(cfg, 0.02, 0.02, rd_success_probability=1.1)

    bad = copy.deepcopy(cfg)
    bad["starting_point"]["productive_capital_usd"] = -1
    with pytest.raises(ValueError, match="must be positive"):
        simulate_case(bad, 0.02, 0.02)

    bad = copy.deepcopy(cfg)
    bad["horizon_years"] = True
    with pytest.raises(ValueError, match="integer"):
        simulate_case(bad, 0.02, 0.02)

    bad = copy.deepcopy(cfg)
    bad["technology_projects"]["automation_deployment_lag_years"] = -1
    with pytest.raises(ValueError, match="integer"):
        simulate_case(bad, 0.02, 0.02)


def test_break_even_and_sector_reconciliation_reject_invalid_inputs():
    cfg = load_config()
    with pytest.raises(ValueError, match="integer"):
        break_even_cashflow_growth(100, 90, 0.02, True)
    with pytest.raises(ValueError, match="positive"):
        break_even_cashflow_growth(0, 90, 0.02, 10)
    with pytest.raises(ValueError, match="at least -100%"):
        from synergy_productivity_flywheel_dynamic_v2 import sector_reconciliation
        sector_reconciliation(cfg, 0.02, -1.01)


def test_dynamic_model_labels_non_ten_year_horizons_correctly():
    cfg = load_config()
    cfg["horizon_years"] = 5
    result = simulate_case(cfg, 0.02, 0.02)
    assert result["final_year"] == 5
    assert result["final_year_residual_usd"] == result["annual"][-1]["residual_after_replacement_and_project_returns_usd"]
    assert result["year_10_residual_usd"] is None



def test_dynamic_flywheel_rejects_unknown_allocation_funds_and_derived_overflow():
    cfg = load_config()
    bad = copy.deepcopy(cfg)
    bad["allocation"]["unmodeled_fund"] = 0.1
    bad["allocation"]["resilience_reserve"] -= 0.1
    with pytest.raises(ValueError, match="exactly productive_automation"):
        simulate_case(bad, 0.02, 0.02)

    bad = copy.deepcopy(cfg)
    bad["starting_point"]["gross_cashflow_after_opex_before_replacement_usd"] = 1e308
    with pytest.raises(ValueError, match="year 1 gross cashflow"):
        simulate_case(bad, 1e308, 0.02)

    with pytest.raises(ValueError, match="Break-even projection"):
        break_even_cashflow_growth(100, 1e308, 1e308, 10)
