from pathlib import Path
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
